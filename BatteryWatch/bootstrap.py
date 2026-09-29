"""Recreate an isolated BatteryWatch runtime from the checked-in lock files."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=('server', 'client'))
    parser.add_argument('--with-push', action='store_true', help='Install optional server Firebase dependencies')
    parser.add_argument('--test', action='store_true', help='Run the component tests after setup')
    args = parser.parse_args()
    if args.component == 'client' and sys.version_info[:2] != (3, 10):
        parser.error('The SNMP client requires Python 3.10. Run with py -3.10 or uv run --python 3.10.')
    if sys.version_info < (3, 10):
        parser.error('Server requires Python >=3.10; Python 3.12 is recommended.')
    if args.with_push and args.component != 'server':
        parser.error('--with-push is only for the server; keep server and SNMP dependencies isolated.')
    root = Path(__file__).resolve().parent
    folder = root / ('server' if args.component == 'server' else 'monitoring-client')
    env = folder / '.venv'
    python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if env.exists() and not python.exists():
        parser.error('Existing .venv is incomplete. Rename it before retrying; no files were removed.')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(env)
    actual = subprocess.check_output([str(python), '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], text=True).strip()
    if actual != f'{sys.version_info.major}.{sys.version_info.minor}':
        parser.error('Existing .venv uses a different Python version; rename it before recreating.')
    requirements = folder / ('requirements-push.txt' if args.with_push else 'requirements-lock.txt')
    if args.component == 'client' or args.with_push:
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], check=True)
        subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    if args.test:
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1')
        if args.component == 'server':
            subprocess.run([str(python), 'server.py', 'self-test'], cwd=folder, env=environment, check=True)
        subprocess.run([str(python), '-m', 'unittest', 'discover', '-s', 'tests'], cwd=folder, env=environment, check=True)
    print('Runtime ready:', python)
    print('Local credentials and device profiles must be restored separately; see docs/reproduce.md.')


if __name__ == '__main__':
    main()
