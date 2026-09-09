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
import stat
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
        'candidate': 'display-89-privacy-review-v2',
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
        'listener_scope_verified': False,
    }


def ensure_tools() -> None:
    missing = [name for name in ('Xvfb', 'xauth', 'xdpyinfo') if not shutil.which(name)]
    if missing:
        raise RuntimeError('missing required tools: ' + ', '.join(missing))


def make_xauthority(path: Path, display: int) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = path.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o077:
        raise RuntimeError('authority parent must be a private owned directory')
    if path.exists() or path.is_symlink():
        raise RuntimeError('refusing to replace existing authority target')
    cookie = secrets.token_hex(16)
    fd, name = tempfile.mkstemp(prefix='.authority-', dir=path.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        try:
            cp = subprocess.run(['xauth', '-f', str(tmp), '-q'],
                                input=f'add {tcp_display(display)} MIT-MAGIC-COOKIE-1 {cookie}\n',
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError('xauth execution failed; secret-bearing output suppressed') from None
        if cp.returncode != 0:
            raise RuntimeError('xauth failed; secret-bearing output suppressed')
        os.chmod(tmp, 0o600)
        os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
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
    if not 1 <= display <= 59535:
        raise RuntimeError('display outside supported TCP port range')
    ensure_tools()
    if not shutil.which('xhost'):
        raise RuntimeError('missing required tool: xhost')
    if unix_socket_present(display) or Path(f'/tmp/.X{display}-lock').exists() or abstract_socket_present(display) or tcp_records(tcp_port(display)):
        raise RuntimeError('throwaway display is occupied; no resources changed')
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
        rows = tcp_records(tcp_port(display))
        verify_listener(rows, pid)
        if unix_socket_present(display) or abstract_socket_present(display):
            raise RuntimeError('security failure: Unix X11 socket unexpectedly exists')
        host_env = xenv(display, auth)
        host_env['LC_ALL'] = 'C'
        hosts = run(['xhost'], env=host_env, timeout=3)
        if hosts.returncode != 0 or hosts.stdout.strip() != 'access control enabled, only authorized clients can connect':
            raise RuntimeError('host access control is disabled, populated, or unverified')
        authority_stat = auth.stat()
        if stat.S_IMODE(authority_stat.st_mode) != 0o600 or authority_stat.st_uid != os.getuid():
            raise RuntimeError('invalid authority ownership or mode')
        empty = tmp / 'empty.Xauthority'
        empty.touch(mode=0o600)
        bad_env = xenv(display, empty)
        bad_env['LC_ALL'] = 'C'
        unauth = run(['xdpyinfo', '-display', tcp_display(display)], env=bad_env, timeout=3)
        if unauth.returncode == 0 or 'Authorization required' not in unauth.stderr:
            raise RuntimeError('unauthenticated probe did not prove authorization rejection')
        recheck = run(['xdpyinfo', '-display', tcp_display(display)], env=xenv(display, auth), timeout=3)
        if recheck.returncode != 0:
            raise RuntimeError('authenticated recheck failed')
        result = {
            'ok': True,
            'candidate': 'display-89-privacy-review-v2',
            'display': f':{display}',
            'tcp_display': tcp_display(display),
            'endpoint': f'{TCP_HOST}:{tcp_port(display)}',
            'xvfb_pid_advisory': pid,
            'authenticated_xdpyinfo': 'PASS',
            'unauthenticated_xdpyinfo': 'DENIED',
            'authenticated_exit_code': recheck.returncode,
            'unauthenticated_exit_code': unauth.returncode,
            'authenticated_recheck': 'PASS',
            'unix_socket': 'ABSENT',
            'abstract_unix_socket': 'ABSENT',
            'host_access_rules': 'enabled-empty',
            'listener_rows': rows,
            'listener_scope': 'loopback-ipv4-only',
            'xauthority_mode': oct(auth.stat().st_mode & 0o777),
        }
    finally:
        if pid is not None:
            terminate(pid)
            os.waitpid(pid, 0)
            if Path(f'/proc/{pid}').exists() or tcp_records(tcp_port(display)) or unix_socket_present(display) or abstract_socket_present(display):
                raise RuntimeError('cleanup unverified; private authority retained')
        shutil.rmtree(tmp, ignore_errors=True)
    if tmp.exists():
        raise RuntimeError('private selftest directory cleanup failed')
    result['cleanup'] = 'PASS'
    return result


def abstract_socket_present(display: int) -> bool:
    name = f'@/tmp/.X11-unix/X{display}'
    return any(line.split()[-1:] == [name] for line in Path('/proc/net/unix').read_text().splitlines()[1:])


def tcp_records(port: int) -> list[dict[str, str]]:
    records = []
    for family, filename in [('IPv4', '/proc/net/tcp'), ('IPv6', '/proc/net/tcp6')]:
        for line in Path(filename).read_text().splitlines()[1:]:
            fields = line.split()
            address, port_hex = fields[1].split(':')
            if fields[3] == '0A' and int(port_hex, 16) == port:
                records.append({'family': family, 'address_hex': address, 'inode': fields[9]})
    return records


def verify_listener(records: list[dict[str, str]], pid: int) -> None:
    if len(records) != 1 or records[0]['family'] != 'IPv4' or records[0]['address_hex'] != '0100007F':
        raise RuntimeError('listener must be exactly one loopback IPv4 socket')
    owned = {os.readlink(fd) for fd in Path(f'/proc/{pid}/fd').iterdir()}
    if f"socket:[{records[0]['inode']}]" not in owned:
        raise RuntimeError('listener ownership could not be verified')


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
    raise RuntimeError('activation disabled in privacy review candidate; only preflight and throwaway selftest are admitted')


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
        print(json.dumps({'ok': False, 'candidate': 'display-89-privacy-review-v2', 'error': message, 'preflight': candidate_preflight(getattr(args, 'display', DEFAULT_DISPLAY))}, indent=2, sort_keys=True), file=sys.stderr)
        if 'AF_INET denied' in message:
            return 74
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
