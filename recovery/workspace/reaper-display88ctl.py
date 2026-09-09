#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DISPLAY_NUM = 88
DEFAULT_ROOT = Path('/mnt/data/ubuntu-desktop-workspace')
DEFAULT_HANDOFF_ROOT = Path('/mnt/data/reaper-display-88-handoff')
EXPECTED_REAPER_SHA = 'cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4'
EXPECTED_TITLE_FRAGMENT = 'ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None, timeout: float = 10.0, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=str(cwd) if cwd else None, timeout=timeout, check=check)


def paths(root: Path) -> dict[str, Path]:
    return {
        'root': root,
        'project': root / 'projects/ASIO-Routing-Project/ASIO-Routing-Project.RPP',
        'reaper': root / 'apps/REAPER/reaper',
        'reaper_ini': root / 'config/REAPER/reaper.ini',
        'start_desktop': root / 'start-desktop.sh',
        'home': root / 'home',
        'xdg': root / 'config',
        'logs': root / 'logs',
        'run': root / 'run',
    }


def display_value(display_num: int) -> str:
    return f':{display_num}'


def af_unix_probe() -> dict[str, object]:
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.close()
        return {'allowed': True, 'errno': None, 'error': None}
    except OSError as exc:
        return {'allowed': False, 'errno': exc.errno, 'error': str(exc)}


def proc_status() -> dict[str, int | None]:
    out: dict[str, int | None] = {'seccomp': None, 'no_new_privs': None}
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith('Seccomp:'):
                out['seccomp'] = int(line.split(':', 1)[1].strip())
            elif line.startswith('NoNewPrivs:'):
                out['no_new_privs'] = int(line.split(':', 1)[1].strip())
    except OSError:
        pass
    return out


def display_reachable(display_num: int) -> bool:
    xdpyinfo = shutil.which('xdpyinfo')
    if not xdpyinfo:
        return False
    cp = run([xdpyinfo, '-display', display_value(display_num)], timeout=3)
    return cp.returncode == 0


def pgrep_lines(pattern: str) -> list[tuple[int, str]]:
    pgrep = shutil.which('pgrep')
    if not pgrep:
        return []
    cp = run([pgrep, '-af', pattern], timeout=3)
    if cp.returncode not in (0, 1):
        return []
    result = []
    for line in cp.stdout.splitlines():
        if not line.strip():
            continue
        first, _, rest = line.partition(' ')
        try:
            result.append((int(first), rest))
        except ValueError:
            continue
    return result


def process_display(pid: int) -> str | None:
    try:
        raw = Path(f'/proc/{pid}/environ').read_bytes()
    except OSError:
        return None
    for item in raw.split(b'\0'):
        if item.startswith(b'DISPLAY='):
            return item.split(b'=', 1)[1].decode('utf-8', errors='replace')
    return None


def owner_xvfb(display_num: int) -> tuple[int | None, str | None]:
    prefix = f'Xvfb :{display_num} '
    for pid, cmd in pgrep_lines(f'^Xvfb :{display_num} '):
        if cmd.startswith(prefix):
            return pid, cmd
    return None, None


def find_display_process(pattern: str, display_num: int) -> tuple[int | None, str | None]:
    wanted = display_value(display_num)
    for pid, cmd in pgrep_lines(pattern):
        if process_display(pid) == wanted:
            return pid, cmd
    return None, None


def reaper_pid(root: Path, display_num: int) -> tuple[int | None, str | None]:
    binary = str(paths(root)['reaper'])
    return find_display_process(f'^{binary}( |$)', display_num)


def window_tree(display_num: int) -> str:
    xwininfo = shutil.which('xwininfo')
    if not xwininfo:
        return ''
    env = os.environ.copy()
    env['DISPLAY'] = display_value(display_num)
    cp = run([xwininfo, '-root', '-tree'], env=env, timeout=5)
    return cp.stdout if cp.returncode == 0 else ''


def canonical_window(display_num: int) -> str | None:
    for line in window_tree(display_num).splitlines():
        if EXPECTED_TITLE_FRAGMENT in line:
            start = line.find('"')
            end = line.find('"', start + 1)
            if start >= 0 and end > start:
                return line[start + 1:end]
            return EXPECTED_TITLE_FRAGMENT
    return None


def workspace_hashes(root: Path) -> dict[str, str | None]:
    p = paths(root)
    result: dict[str, str | None] = {}
    for key in ('project', 'reaper', 'reaper_ini'):
        path = p[key]
        result[key] = sha256(path) if path.is_file() else None
    return result


def status(root: Path, display_num: int) -> dict[str, object]:
    reachable = display_reachable(display_num)
    xvfb_pid, xvfb_cmd = owner_xvfb(display_num)
    openbox_pid, openbox_cmd = find_display_process(f'^openbox --config-file {root}/config/openbox/rc.xml$', display_num)
    desktop_pid, desktop_cmd = find_display_process(f'^python3 {root}/desktop_shell.py$', display_num)
    rp, rc = reaper_pid(root, display_num)
    return {
        'schema_version': 1,
        'logical_monitor_id': 'reaper-x11-display-88-v1' if display_num == 88 else f'reaper-x11-display-{display_num}-v1',
        'display': display_value(display_num),
        'geometry': '1440x900x24',
        'transport': 'local-af-unix',
        'reachable': reachable,
        'owner_xvfb': {'pid': xvfb_pid, 'command': xvfb_cmd},
        'openbox': {'pid': openbox_pid, 'command': openbox_cmd},
        'desktop_shell': {'pid': desktop_pid, 'command': desktop_cmd},
        'reaper': {'pid': rp, 'command': rc, 'window_title': canonical_window(display_num) if reachable else None},
        'workspace': str(root),
        'hashes': workspace_hashes(root),
        'sandbox': proc_status() | {'af_unix': af_unix_probe()},
    }


def require_workspace(root: Path) -> None:
    p = paths(root)
    if not p['project'].is_file():
        raise RuntimeError('REAPER project is missing')
    if not p['reaper'].is_file() or sha256(p['reaper']) != EXPECTED_REAPER_SHA:
        raise RuntimeError('REAPER binary hash mismatch or missing')


def checkpoint(root: Path, display_num: int, handoff_root: Path) -> Path:
    require_workspace(root)
    st = status(root, display_num)
    if not st['reachable']:
        raise RuntimeError(f'{display_value(display_num)} is not reachable in this runtime')
    if not st['owner_xvfb']['pid']:
        raise RuntimeError(f'{display_value(display_num)} is reachable but not owned by the expected Xvfb process')
    if not st['reaper']['window_title']:
        raise RuntimeError('canonical REAPER window is not visible on the display')

    handoff_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix='.checkpoint-', dir=str(handoff_root)))
    try:
        overlay = temp_dir / 'overlay'
        overlay.mkdir(parents=True)
        p = paths(root)
        shutil.copy2(p['project'], overlay / 'ASIO-Routing-Project.RPP')
        shutil.copy2(p['reaper_ini'], overlay / 'reaper.ini')

        tree = window_tree(display_num)
        (temp_dir / 'window-tree.txt').write_text(tree, encoding='utf-8')
        process_lines = []
        for name, item in (('xvfb', st['owner_xvfb']), ('openbox', st['openbox']), ('desktop_shell', st['desktop_shell']), ('reaper', st['reaper'])):
            process_lines.append(f"{name}\t{item.get('pid')}\t{item.get('command')}\n")
        (temp_dir / 'processes.txt').write_text(''.join(process_lines), encoding='utf-8')

        frame = temp_dir / 'frame.png'
        scrot = shutil.which('scrot')
        if not scrot:
            raise RuntimeError('scrot is required for genuine display checkpoint capture')
        env = os.environ.copy()
        env['DISPLAY'] = display_value(display_num)
        cp = run([scrot, str(frame)], env=env, timeout=15)
        if cp.returncode != 0 or not frame.is_file() or frame.stat().st_size == 0:
            raise RuntimeError(f'scrot failed: {cp.stderr.strip()}')

        files = [
            overlay / 'ASIO-Routing-Project.RPP', overlay / 'reaper.ini',
            temp_dir / 'window-tree.txt', temp_dir / 'processes.txt', frame,
        ]
        manifest = {
            'schema_version': 1,
            'logical_monitor_id': st['logical_monitor_id'],
            'strategy': 'attach-if-visible-otherwise-reconstruct',
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'display': st['display'],
            'geometry': st['geometry'],
            'transport': st['transport'],
            'source_runtime': {
                'xvfb_pid_advisory': st['owner_xvfb']['pid'],
                'sandbox': st['sandbox'],
            },
            'continuity_locks': {
                'project_sha256': sha256(p['project']),
                'reaper_ini_sha256': sha256(p['reaper_ini']),
                'reaper_sha256': EXPECTED_REAPER_SHA,
                'window_title': st['reaper']['window_title'],
                'evaluation_ui_preserved': 'EVALUATION LICENSE' in (st['reaper']['window_title'] or ''),
            },
            'overlay': {
                'project': 'overlay/ASIO-Routing-Project.RPP',
                'reaper_ini': 'overlay/reaper.ini',
            },
            'artifacts': {str(f.relative_to(temp_dir)): {'sha256': sha256(f), 'bytes': f.stat().st_size} for f in files},
            'next_chat_command': 'python3 recovery/workspace/reaper-display88ctl.py acquire --display 88',
        }
        (temp_dir / 'DISPLAY-HANDOFF.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        files.append(temp_dir / 'DISPLAY-HANDOFF.json')
        sums = ''.join(f"{sha256(f)}  {f.relative_to(temp_dir)}\n" for f in sorted(files, key=lambda x: str(x.relative_to(temp_dir))))
        (temp_dir / 'SHA256SUMS').write_text(sums, encoding='utf-8')

        current = handoff_root / 'current'
        previous = handoff_root / 'previous'
        if previous.exists():
            shutil.rmtree(previous)
        if current.exists():
            current.rename(previous)
        temp_dir.rename(current)

        bundle_tmp = handoff_root / '.reaper-display-88-handoff.tar.gz.tmp'
        bundle = handoff_root / 'reaper-display-88-handoff.tar.gz'
        if bundle_tmp.exists():
            bundle_tmp.unlink()
        with tarfile.open(bundle_tmp, 'w:gz', compresslevel=9) as tf:
            for f in sorted(current.rglob('*')):
                if f.is_file():
                    info = tf.gettarinfo(str(f), arcname=str(Path('current') / f.relative_to(current)))
                    info.uid = 0
                    info.gid = 0
                    info.uname = ''
                    info.gname = ''
                    info.mtime = 0
                    with f.open('rb') as src:
                        tf.addfile(info, src)
        os.replace(bundle_tmp, bundle)
        (handoff_root / 'BUNDLE.sha256').write_text(f"{sha256(bundle)}  {bundle.name}\n", encoding='utf-8')
        return current
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def overlay_checkpoint(root: Path, handoff_root: Path) -> None:
    current = handoff_root / 'current'
    manifest_path = current / 'DISPLAY-HANDOFF.json'
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    artifacts = manifest.get('artifacts', {})
    for rel, meta in artifacts.items():
        path = current / rel
        if not path.is_file() or sha256(path) != meta['sha256']:
            raise RuntimeError(f'checkpoint artifact hash mismatch: {rel}')
    p = paths(root)
    pairs = [
        (current / manifest['overlay']['project'], p['project']),
        (current / manifest['overlay']['reaper_ini'], p['reaper_ini']),
    ]
    backup_dir = handoff_root / 'restore-backup'
    backup_dir.mkdir(parents=True, exist_ok=True)
    for src, dst in pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and sha256(dst) == sha256(src):
            continue
        if dst.exists():
            shutil.copy2(dst, backup_dir / (dst.name + '.pre-restore'))
        tmp = dst.with_name(dst.name + '.display88ctl.tmp')
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
        if sha256(dst) != sha256(src):
            raise RuntimeError(f'postwrite hash mismatch: {dst}')


def terminate_pid(pid: int, timeout: float = 2.0) -> None:
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not Path(f'/proc/{pid}').exists():
            return
        time.sleep(0.05)
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass


def clear_stale_display_clients(root: Path, display_num: int) -> list[int]:
    killed: list[int] = []
    candidates = [
        find_display_process(f'^openbox --config-file {root}/config/openbox/rc.xml$', display_num),
        find_display_process(f'^python3 {root}/desktop_shell.py$', display_num),
        reaper_pid(root, display_num),
    ]
    for pid, _ in candidates:
        if pid is not None:
            terminate_pid(pid)
            killed.append(pid)
    return killed


def launch_reaper(root: Path, display_num: int) -> int:
    p = paths(root)
    p['logs'].mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['DISPLAY'] = display_value(display_num)
    env['HOME'] = str(p['home'])
    env['XDG_CONFIG_HOME'] = str(p['xdg'])
    log = (p['logs'] / 'reaper-display88ctl.log').open('ab', buffering=0)
    proc = subprocess.Popen([str(p['reaper']), str(p['project'])], cwd=str(p['reaper'].parent), env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return proc.pid


def acquire(root: Path, display_num: int, handoff_root: Path, no_overlay: bool = False) -> dict[str, object]:
    require_workspace(root)
    if display_reachable(display_num):
        st = status(root, display_num)
        if not st['owner_xvfb']['pid']:
            raise RuntimeError(f'{display_value(display_num)} is reachable but owner process is not the expected Xvfb; refusing to attach')
        if st['reaper']['window_title']:
            checkpoint(root, display_num, handoff_root)
            st['acquire_mode'] = 'attached-existing-runtime'
            return st

    stale_clients = clear_stale_display_clients(root, display_num)
    probe = af_unix_probe()
    if not probe['allowed']:
        raise RuntimeError(f"native display reconstruction blocked: AF_UNIX denied errno={probe['errno']} error={probe['error']}")
    if not no_overlay:
        overlay_checkpoint(root, handoff_root)
    p = paths(root)
    if not p['start_desktop'].is_file():
        raise RuntimeError(f'missing desktop launcher: {p["start_desktop"]}')
    env = os.environ.copy()
    env['DISPLAY_NUM'] = str(display_num)
    cp = run(['bash', str(p['start_desktop'])], env=env, timeout=20)
    if cp.returncode != 0:
        raise RuntimeError(f'desktop reconstruction failed: {cp.stdout.strip()} {cp.stderr.strip()}')

    rp, _ = reaper_pid(root, display_num)
    if rp is None:
        launch_reaper(root, display_num)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if display_reachable(display_num) and canonical_window(display_num):
            break
        time.sleep(0.25)
    st = status(root, display_num)
    st['stale_clients_terminated'] = stale_clients
    if not st['reachable'] or not st['owner_xvfb']['pid'] or not st['reaper']['window_title']:
        raise RuntimeError('reconstructed display did not reach canonical REAPER-ready state')
    checkpoint(root, display_num, handoff_root)
    st['acquire_mode'] = 'reconstructed-in-current-runtime'
    return st


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='reaper-display88ctl', description='Cross-chat continuity controller for the logical REAPER X11 display :88.')
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--handoff-root', type=Path, default=DEFAULT_HANDOFF_ROOT)
    parser.add_argument('--display', type=int, default=DEFAULT_DISPLAY_NUM)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    sub.add_parser('preflight')
    sub.add_parser('checkpoint')
    acq = sub.add_parser('acquire')
    acq.add_argument('--no-overlay', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'preflight':
            result = {'sandbox': proc_status(), 'af_unix': af_unix_probe(), 'display': display_value(args.display), 'display_reachable': display_reachable(args.display)}
        elif args.command == 'status':
            result = status(args.root, args.display)
        elif args.command == 'checkpoint':
            current = checkpoint(args.root, args.display, args.handoff_root)
            result = {'ok': True, 'checkpoint': str(current), 'bundle': str(args.handoff_root / 'reaper-display-88-handoff.tar.gz'), 'bundle_sha256': sha256(args.handoff_root / 'reaper-display-88-handoff.tar.gz')}
        elif args.command == 'acquire':
            result = acquire(args.root, args.display, args.handoff_root, no_overlay=args.no_overlay)
        else:
            raise AssertionError(args.command)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc), 'display': display_value(args.display), 'sandbox': proc_status(), 'af_unix': af_unix_probe()}, indent=2, sort_keys=True), file=sys.stderr)
        return 73 if 'AF_UNIX denied' in str(exc) else 1


if __name__ == '__main__':
    raise SystemExit(main())
