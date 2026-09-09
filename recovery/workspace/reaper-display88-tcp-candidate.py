#!/usr/bin/env python3
from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path('/mnt/data/ubuntu-desktop-workspace')
DEFAULT_DISPLAY = 88
TCP_HOST = '127.0.0.1'
EXPECTED_REAPER_SHA = 'cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4'
EXPECTED_TITLE_FRAGMENT = 'ASIO-Routing-Project - REAPER v7.79 - EVALUATION LICENSE'
BASE_CTL = Path(__file__).with_name('reaper-display88ctl.py')


def run(cmd: list[str], *, env: dict[str, str] | None = None, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=timeout)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def tcp_display(display: int) -> str:
    return f'{TCP_HOST}:{display}'


def tcp_port(display: int) -> int:
    return 6000 + display


def af_probe(family: int, name: str) -> dict[str, object]:
    try:
        s = socket.socket(family, socket.SOCK_STREAM)
        if family == socket.AF_INET:
            s.bind((TCP_HOST, 0))
        s.close()
        return {'name': name, 'allowed': True, 'errno': None, 'error': None}
    except OSError as exc:
        return {'name': name, 'allowed': False, 'errno': exc.errno, 'error': str(exc)}


def proc_status() -> dict[str, int | None]:
    result: dict[str, int | None] = {'seccomp': None, 'no_new_privs': None}
    try:
        for line in Path('/proc/self/status').read_text(encoding='utf-8').splitlines():
            if line.startswith('Seccomp:'):
                result['seccomp'] = int(line.split(':', 1)[1].strip())
            elif line.startswith('NoNewPrivs:'):
                result['no_new_privs'] = int(line.split(':', 1)[1].strip())
    except OSError:
        pass
    return result


def candidate_preflight(display: int) -> dict[str, object]:
    return {
        'schema_version': 1,
        'candidate': 'display-88-tcp-fallback-v1',
        'display': f':{display}',
        'tcp_display': tcp_display(display),
        'tcp_endpoint': f'{TCP_HOST}:{tcp_port(display)}',
        'sandbox': proc_status(),
        'af_unix': af_probe(socket.AF_UNIX, 'AF_UNIX'),
        'af_inet': af_probe(socket.AF_INET, 'AF_INET'),
        'listener_policy': 'candidate-required-explicit-owner-approval',
        'listener_scope': 'loopback-ipv4-only',
        'xauthority_required': True,
        'xvfb_own_listener_creation': False,
    }


def ensure_tools() -> None:
    missing = [name for name in ('Xvfb', 'xauth', 'xdpyinfo') if not shutil.which(name)]
    if missing:
        raise RuntimeError('missing required tools: ' + ', '.join(missing))


def make_xauthority(path: Path, display: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cookie = secrets.token_hex(16)
    tmp = path.with_name(path.name + '.tmp')
    if tmp.exists():
        tmp.unlink()
    tmp.touch(mode=0o600)
    os.chmod(tmp, 0o600)
    cp = run(['xauth', '-f', str(tmp), 'add', tcp_display(display), '.', cookie], timeout=5)
    if cp.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError('xauth failed: ' + cp.stderr.strip())
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    return cookie


def _exec_xvfb_from_inherited_fd(args: argparse.Namespace) -> int:
    fd = int(os.environ['REAPER_X11_LISTEN_FD'])
    if fd != 3:
        os.dup2(fd, 3)
        os.close(fd)
    os.set_inheritable(3, True)
    os.environ['LISTEN_PID'] = str(os.getpid())
    os.environ['LISTEN_FDS'] = '1'
    os.environ['LISTEN_FDNAMES'] = 'x11-tcp-loopback'
    argv = [
        'Xvfb', f':{args.display}', '-screen', '0', args.geometry,
        '-nolisten', 'unix', '-nolisten', 'tcp', '-auth', str(args.auth_file),
    ]
    os.execvp('Xvfb', argv)
    return 127


def start_loopback_xvfb(display: int, auth_file: Path, log_file: Path, geometry: str = '1440x900x24') -> int:
    ensure_tools()
    port = tcp_port(display)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((TCP_HOST, port))
    listener.listen(128)
    listener.set_inheritable(True)
    env = os.environ.copy()
    env['REAPER_X11_LISTEN_FD'] = str(listener.fileno())
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log = log_file.open('ab', buffering=0)
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), '_exec-xvfb', '--display', str(display), '--geometry', geometry, '--auth-file', str(auth_file)],
        env=env,
        pass_fds=(listener.fileno(),),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    listener.close()
    return proc.pid


def xenv(display: int, auth_file: Path, root: Path = ROOT) -> dict[str, str]:
    env = os.environ.copy()
    env['DISPLAY'] = tcp_display(display)
    env['XAUTHORITY'] = str(auth_file)
    env['HOME'] = str(root / 'home')
    env['XDG_CONFIG_HOME'] = str(root / 'config')
    return env


def xdpyinfo_ok(display: int, auth_file: Path) -> bool:
    cp = run(['xdpyinfo', '-display', tcp_display(display)], env=xenv(display, auth_file), timeout=3)
    return cp.returncode == 0


def unix_socket_present(display: int) -> bool:
    return Path(f'/tmp/.X11-unix/X{display}').exists()


def listener_rows(port: int) -> list[str]:
    ss = shutil.which('ss')
    if not ss:
        return []
    cp = run([ss, '-ltnp'], timeout=3)
    if cp.returncode != 0:
        return []
    needle = f':{port}'
    return [line.strip() for line in cp.stdout.splitlines() if needle in line]


def wait_x(display: int, auth_file: Path, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if xdpyinfo_ok(display, auth_file):
            return
        time.sleep(0.1)
    raise RuntimeError(f'authenticated X11/TCP did not become ready at {tcp_display(display)}')


def terminate(pid: int) -> None:
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if not Path(f'/proc/{pid}').exists():
            return
        time.sleep(0.05)
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass


def selftest(display: int) -> dict[str, object]:
    if display == 88:
        raise RuntimeError('selftest refuses canonical :88; use a throwaway display such as :89')
    pf = candidate_preflight(display)
    if not pf['af_inet']['allowed']:
        raise OSError(errno.EPERM, 'AF_INET loopback bind denied')
    tmp = Path(tempfile.mkdtemp(prefix=f'reaper-x11-tcp-selftest-{display}-'))
    auth = tmp / 'Xauthority'
    log = tmp / 'xvfb.log'
    pid: int | None = None
    try:
        make_xauthority(auth, display)
        pid = start_loopback_xvfb(display, auth, log, geometry='320x200x24')
        wait_x(display, auth)
        rows = listener_rows(tcp_port(display))
        if unix_socket_present(display):
            raise RuntimeError('security failure: Unix X11 socket unexpectedly exists')
        if rows and any(f'{TCP_HOST}:{tcp_port(display)}' not in row for row in rows):
            raise RuntimeError('security failure: X11/TCP listener is not loopback-only')
        bad_env = os.environ.copy()
        bad_env['DISPLAY'] = tcp_display(display)
        bad_env['XAUTHORITY'] = '/dev/null'
        unauth = run(['xdpyinfo', '-display', tcp_display(display)], env=bad_env, timeout=3)
        if unauth.returncode == 0:
            raise RuntimeError('security failure: unauthenticated X11 client was accepted')
        return {
            'ok': True,
            'candidate': 'display-88-tcp-fallback-v1',
            'display': f':{display}',
            'tcp_display': tcp_display(display),
            'endpoint': f'{TCP_HOST}:{tcp_port(display)}',
            'xvfb_pid_advisory': pid,
            'authenticated_xdpyinfo': 'PASS',
            'unauthenticated_xdpyinfo': 'DENIED',
            'unix_socket': 'ABSENT',
            'listener_rows': rows,
            'listener_scope': 'loopback-ipv4-only',
            'xauthority_mode': oct(auth.stat().st_mode & 0o777),
        }
    finally:
        if pid is not None:
            terminate(pid)
        shutil.rmtree(tmp, ignore_errors=True)


def load_base_controller():
    if not BASE_CTL.is_file():
        raise RuntimeError(f'missing base controller: {BASE_CTL}')
    spec = importlib.util.spec_from_file_location('reaper_display88_base', BASE_CTL)
    if spec is None or spec.loader is None:
        raise RuntimeError('unable to load base display controller')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_window(display: int, auth_file: Path, root: Path) -> str | None:
    xwininfo = shutil.which('xwininfo')
    if not xwininfo:
        return None
    cp = run([xwininfo, '-root', '-tree'], env=xenv(display, auth_file, root), timeout=5)
    if cp.returncode != 0:
        return None
    for line in cp.stdout.splitlines():
        if EXPECTED_TITLE_FRAGMENT in line:
            start = line.find('"')
            end = line.find('"', start + 1)
            return line[start + 1:end] if start >= 0 and end > start else EXPECTED_TITLE_FRAGMENT
    return None


def launch_client(cmd: list[str], env: dict[str, str], log_path: Path, cwd: Path | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open('ab', buffering=0)
    proc = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return proc.pid


def acquire_tcp_candidate(root: Path, display: int, handoff_root: Path) -> dict[str, object]:
    if display != 88:
        raise RuntimeError('candidate acquisition is scoped to canonical display :88')
    pf = candidate_preflight(display)
    if pf['af_inet']['allowed'] is not True:
        err = pf['af_inet']
        raise RuntimeError(f"TCP fallback blocked: AF_INET denied errno={err['errno']} error={err['error']}")
    if pf['af_unix']['allowed'] is True:
        raise RuntimeError('candidate TCP activation refused: AF_UNIX is available; use the admitted local transport')

    base = load_base_controller()
    base.require_workspace(root)
    base.overlay_checkpoint(root, handoff_root)
    if sha256(root / 'apps/REAPER/reaper') != EXPECTED_REAPER_SHA:
        raise RuntimeError('REAPER binary hash mismatch')

    run_root = root / 'run'
    logs = root / 'logs'
    run_root.mkdir(parents=True, exist_ok=True)
    auth = run_root / 'display-88-tcp.Xauthority'
    make_xauthority(auth, display)
    xvfb_pid = start_loopback_xvfb(display, auth, logs / 'xvfb-tcp-88.log')
    try:
        wait_x(display, auth)
        rows = listener_rows(tcp_port(display))
        if unix_socket_present(display):
            raise RuntimeError('security failure: Unix X11 socket exists in TCP fallback mode')
        if rows and any(f'{TCP_HOST}:{tcp_port(display)}' not in row for row in rows):
            raise RuntimeError('security failure: TCP listener escaped loopback')
        env = xenv(display, auth, root)
        openbox_pid = launch_client(['openbox', '--config-file', str(root / 'config/openbox/rc.xml')], env, logs / 'openbox-tcp-88.log')
        desktop_pid = launch_client(['python3', str(root / 'desktop_shell.py')], env, logs / 'desktop-shell-tcp-88.log')
        reaper_pid = launch_client([str(root / 'apps/REAPER/reaper'), str(root / 'projects/ASIO-Routing-Project/ASIO-Routing-Project.RPP')], env, logs / 'reaper-tcp-88.log', root / 'apps/REAPER')
        deadline = time.monotonic() + 20
        title = None
        while time.monotonic() < deadline:
            title = canonical_window(display, auth, root)
            if title:
                break
            time.sleep(0.25)
        if not title:
            raise RuntimeError('TCP fallback did not reach canonical REAPER-ready state')
        for name, pid in [('xvfb-tcp.pid', xvfb_pid), ('openbox-tcp.pid', openbox_pid), ('desktop-shell-tcp.pid', desktop_pid), ('reaper-tcp.pid', reaper_pid)]:
            (run_root / name).write_text(str(pid) + '\n', encoding='utf-8')
        return {
            'ok': True,
            'candidate': 'display-88-tcp-fallback-v1',
            'acquire_mode': 'reconstructed-in-current-runtime-over-authenticated-loopback-tcp',
            'display': tcp_display(display),
            'endpoint': f'{TCP_HOST}:{tcp_port(display)}',
            'listener_rows': rows,
            'unix_socket': 'ABSENT',
            'xauthority': str(auth),
            'xauthority_mode': oct(auth.stat().st_mode & 0o777),
            'reaper_window_title': title,
            'hashes': {
                'project': sha256(root / 'projects/ASIO-Routing-Project/ASIO-Routing-Project.RPP'),
                'reaper': sha256(root / 'apps/REAPER/reaper'),
            },
            'pids_advisory': {'xvfb': xvfb_pid, 'openbox': openbox_pid, 'desktop_shell': desktop_pid, 'reaper': reaper_pid},
        }
    except Exception:
        terminate(xvfb_pid)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Candidate authenticated loopback TCP fallback for logical REAPER display :88.')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('preflight')
    p.add_argument('--display', type=int, default=DEFAULT_DISPLAY)
    s = sub.add_parser('selftest')
    s.add_argument('--display', type=int, default=89)
    a = sub.add_parser('acquire-candidate')
    a.add_argument('--display', type=int, default=DEFAULT_DISPLAY)
    a.add_argument('--root', type=Path, default=ROOT)
    a.add_argument('--handoff-root', type=Path, default=ROOT / 'handoff/display-88')
    x = sub.add_parser('_exec-xvfb')
    x.add_argument('--display', type=int, required=True)
    x.add_argument('--geometry', required=True)
    x.add_argument('--auth-file', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'preflight':
            result = candidate_preflight(args.display)
        elif args.command == 'selftest':
            result = selftest(args.display)
        elif args.command == 'acquire-candidate':
            result = acquire_tcp_candidate(args.root, args.display, args.handoff_root)
        elif args.command == '_exec-xvfb':
            return _exec_xvfb_from_inherited_fd(args)
        else:
            raise AssertionError(args.command)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        message = str(exc)
        print(json.dumps({'ok': False, 'candidate': 'display-88-tcp-fallback-v1', 'error': message, 'preflight': candidate_preflight(getattr(args, 'display', DEFAULT_DISPLAY))}, indent=2, sort_keys=True), file=sys.stderr)
        if 'AF_INET denied' in message:
            return 74
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
