"""Read-only deployment checks. Never print tokens, private keys or file contents."""
import importlib.util
import json
from pathlib import Path
import ssl

from receiver import load_config
from mobile_api import configure_api
from alarms import configure as configure_alarms


def inspect_config(path, android_config=None):
    checks = []
    def record(name, level, message):
        checks.append(dict(name=name, level=level, message=message))
    path = Path(path)
    if not path.is_file():
        record('configuration', 'error', 'Server configuration is missing. Run: python server.py init; then enable-api.')
        return dict(ok=False, checks=checks)
    try:
        config = load_config(path)
        api = configure_api(config)
        alarms = configure_alarms(config)
    except Exception as exc:
        record('configuration', 'error', 'Configuration validation failed (' + type(exc).__name__ + '). Run server.py check for details.')
        return dict(ok=False, checks=checks)
    record('configuration', 'ok', 'Configuration and alarm rules validated.')
    record('android_api', 'ok' if api else 'warning', 'Android API enabled.' if api else 'Android API disabled. Run enable-api before connecting the app.')
    if api and api['host'] == config['host'] and api['port'] == config['port']:
        record('ports', 'error', 'Receiver and Android API cannot use the same address and port.')
    else:
        record('ports', 'ok', 'Receiver/API port settings do not conflict with each other.')
    tls = config['tls']
    if tls.get('certfile'):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(tls['certfile'], tls['keyfile'], password=lambda: '')
            record('tls', 'ok', 'Certificate and private key can be loaded. Hostname and trust still require client verification.')
        except Exception as exc:
            record('tls', 'error', 'Cannot load TLS certificate/key (' + type(exc).__name__ + ').')
    else:
        record('tls', 'warning', 'Loopback-only plaintext configuration. Public access requires a valid TLS certificate.')
    enabled = [r for r in alarms['rules'] if r.get('enabled', True)]
    record('thresholds', 'ok' if enabled else 'warning',
           f'{len(enabled)} numeric alarm rules enabled.' if enabled else 'Numeric alarms disabled. Set thresholds for your battery specifications.')
    push = config.get('push', {})
    project = None
    if not push.get('enabled'):
        record('firebase', 'warning', 'FCM delivery disabled; real push notifications will not be sent.')
    else:
        record('firebase_library', 'ok' if importlib.util.find_spec('firebase_admin') else 'error',
               'Firebase Admin SDK installed.' if importlib.util.find_spec('firebase_admin') else 'Install requirements-push.txt.')
        credential = push.get('service_account')
        if credential:
            try:
                data = json.loads(Path(credential).read_text(encoding='utf-8-sig'))
                if data.get('type') != 'service_account' or not all(isinstance(data.get(k), str) and data[k] for k in ('project_id','client_email','private_key')):
                    raise ValueError()
                project = data['project_id']
                record('firebase_credentials', 'ok', 'Service account metadata is present. FCM authorization requires a live test.')
            except Exception:
                record('firebase_credentials', 'error', 'Service account file is missing or invalid.')
        else:
            record('firebase_credentials', 'warning', 'Using Application Default Credentials; verify them on the deployment host.')
    if android_config:
        try:
            data = json.loads(Path(android_config).read_text(encoding='utf-8-sig'))
            android_project = data['project_info']['project_id']
            packages = {c['client_info']['android_client_info']['package_name'] for c in data['client']}
            supported = {'com.batterywatch.monitor', 'com.batterywatch.monitor.debug'}
            if not packages & supported:
                raise ValueError()
            if project and android_project != project:
                record('android_firebase', 'error', 'Android and server Firebase project IDs do not match.')
            else:
                record('android_firebase', 'ok', 'Android Firebase metadata and package name validated.')
        except Exception:
            record('android_firebase', 'error', 'Android google-services.json is missing or has no matching app package.')
    elif push.get('enabled'):
        record('android_firebase', 'warning', 'Pass --android-config to verify the Android Firebase project/package.')
    return dict(ok=not any(c['level'] == 'error' for c in checks),
                warnings=sum(c['level'] == 'warning' for c in checks), checks=checks,
                note='Configuration checks only; does not prove live device connectivity or FCM delivery.')
