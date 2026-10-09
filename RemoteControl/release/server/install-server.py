#!/usr/bin/env python3
"""RemoteControl Ubuntu 20.04+ installer; Python 3.8+, no pip dependencies."""
import argparse
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys


def port_value(value):
    port = int(value)
    if not 55000 <= port <= 60000:
        raise argparse.ArgumentTypeError("port must be 55000..60000")
    return port


def run(*args):
    subprocess.run(args, check=True)


def write_file(path, data, mode, gid=0):
    # Files contain secrets: create with restrictive mode before writing.
    path = Path(path)
    temp = path.with_name(path.name + ".install-new")
    fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.chown(str(temp), 0, gid)
        os.chmod(str(temp), mode)
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            temp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cert", required=True, help="PEM full certificate chain")
    parser.add_argument("--key", required=True, help="PEM unencrypted private key")
    parser.add_argument("--port", type=port_value, default=55000)
    parser.add_argument("--refresh-certificate", action="store_true",
                        help="replace certificate on an existing installation and restart")
    args = parser.parse_args()
    if sys.version_info < (3, 8) or sys.platform != "linux" or os.geteuid() != 0:
        parser.error("run with sudo python3 on Ubuntu 20.04+ (Python 3.8+)")
    release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    if release.get("ID", "").strip('"') != "ubuntu" or float(release.get("VERSION_ID", "0").strip('"')) < 20.04:
        parser.error("Ubuntu 20.04 or later is required")
    if not Path("/run/systemd/system").is_dir():
        parser.error("systemd must be running; containers without systemd are not supported")
    cert, key = Path(args.cert).resolve(), Path(args.key).resolve()
    # Validate certificate/key pairing before changing the installation.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key), password=lambda: "")
    cert_data, key_data = cert.read_bytes(), key.read_bytes()
    source = Path(__file__).resolve().parent
    service = Path("/etc/systemd/system/remotecontrol-relay.service")
    config = Path("/etc/remotecontrol")
    app = Path("/opt/remotecontrol")
    if args.refresh_certificate:
        if not service.is_file() or not (config / "access.key").is_file():
            parser.error("install the server first")
    else:
        if service.exists() or app.exists() or config.exists():
            parser.error("existing installation found; use update-server.sh instead (see manual)")
        compile((source / "relay.py").read_text(encoding="utf-8"), "relay.py", "exec")
        template = (source / "remotecontrol-relay.service").read_text(encoding="utf-8")
        if "--port 55000" not in template:
            parser.error("invalid service template")
    import grp
    import pwd
    try:
        grp.getgrnam("remotecontrol")
    except KeyError:
        run("groupadd", "--system", "remotecontrol")
    try:
        user = pwd.getpwnam("remotecontrol")
        if user.pw_uid == 0 or user.pw_shell not in ("/usr/sbin/nologin", "/sbin/nologin", "/bin/false"):
            parser.error("existing remotecontrol account is not a dedicated service account")
    except KeyError:
        run("useradd", "--system", "--no-create-home", "--gid", "remotecontrol", "--shell", "/usr/sbin/nologin", "remotecontrol")
    gid = grp.getgrnam("remotecontrol").gr_gid
    config.mkdir(mode=0o750, exist_ok=True)
    os.chown(str(config), 0, gid)
    os.chmod(str(config), 0o750)
    if args.refresh_certificate:
        for name in ("fullchain.pem", "privkey.pem"):
            old = config / name
            if old.exists():
                write_file(config / (name + ".previous"), old.read_bytes(), 0o640, gid)
    write_file(config / "fullchain.pem", cert_data, 0o640, gid)
    write_file(config / "privkey.pem", key_data, 0o640, gid)
    if not args.refresh_certificate:
        write_file(config / "access.key", (secrets.token_hex(32) + "\n").encode("ascii"), 0o640, gid)
        app.mkdir(mode=0o755)
        os.chown(str(app), 0, 0)
        os.chmod(str(app), 0o755)
        write_file(app / "relay.py", (source / "relay.py").read_bytes(), 0o644)
        write_file(service, template.replace("--port 55000", "--port " + str(args.port)).encode("utf-8"), 0o644)
        run("systemctl", "daemon-reload")
        run("systemctl", "enable", "remotecontrol-relay")
    run("systemctl", "restart", "remotecontrol-relay")
    run("systemctl", "is-active", "--quiet", "remotecontrol-relay")
    print("Service started. Check: sudo systemctl status remotecontrol-relay")
    print("Read the shared key locally: sudo cat /etc/remotecontrol/access.key")
    print("Open the selected TCP port in your firewall/cloud security group. See installation manual.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("Installation failed: " + str(error), file=sys.stderr)
        print("Review service logs and the installation manual before retrying.", file=sys.stderr)
        sys.exit(1)
