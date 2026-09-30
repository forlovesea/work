"""Run with --help. Firebase delivery optionally uses firebase-admin."""
import argparse
import asyncio
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import secrets
import signal
from receiver import Receiver, load_config, identifier
from storage import Storage
from mobile_api import MobileApi, configure_api
from alarms import AlarmEngine, configure as configure_alarms, monitor
from push import FirebaseSender, Dispatcher, deliver


def initialize(path, site, device):
    path=Path(path).resolve()
    credentials=path.parent/'client-connection.local.json'
    if path.exists() or credentials.exists():
        raise ValueError('Existing configuration/credentials will not be overwritten')
    if not identifier(site) or not identifier(device): raise ValueError('Invalid site/device ID')
    token=secrets.token_urlsafe(32)
    config=dict(host='127.0.0.1',port=9443,database='data/batterywatch.sqlite3',tls={},
                max_connections=32,idle_timeout=3700,frame_timeout=15,max_frame_bytes=16*1024*1024,
                collectors=[dict(id='collector-01',token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                                 devices=[dict(site_id=site,device_id=device)])])
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f: json.dump(config,f,ensure_ascii=False,indent=2)
    with credentials.open('x',encoding='utf-8') as f:
        json.dump(dict(host='127.0.0.1',port=9443,tls=False,token=token,site_id=site,device_id=device,interval=5),f,ensure_ascii=False,indent=2)
    return credentials


async def serve(config, demo_data=False):
    storage=Storage(config['database'])
    engine=AlarmEngine(storage,config)
    push_config=config.get('push',{})
    sender=FirebaseSender(push_config) if push_config.get('enabled') else None
    receiver=await Receiver(config,storage).start()
    api=MobileApi(config,storage)
    try:
        await api.start()
    except Exception:
        await receiver.close()
        raise
    if api.server: logging.info('Android API listening on %s',api.server.sockets[0].getsockname())
    stop=asyncio.Event()
    from retention import monitor as retain
    jobs=[asyncio.create_task(monitor(engine,stop)), asyncio.create_task(retain(storage,config,stop))]
    if demo_data:
        from smartphone_demo import feed
        logging.warning('SIMULATED DEMO: 10 modules, updates every 5 seconds; database=%s; real uploads rejected; push disabled',config['database'])
        jobs.append(asyncio.create_task(feed(storage,stop)))
    if sender: jobs.append(asyncio.create_task(deliver(Dispatcher(storage,config,sender),stop)))
    loop=asyncio.get_running_loop()
    previous={}
    def terminate(signum,frame): loop.call_soon_threadsafe(stop.set)
    for signum in (signal.SIGINT,signal.SIGTERM):
        previous[signum]=signal.signal(signum,terminate)
    try:
        await stop.wait()
    finally:
        stop.set()
        await asyncio.gather(*jobs,return_exceptions=True)
        await api.close()
        await receiver.close()
        for signum,handler in previous.items(): signal.signal(signum,handler)


def main():
    parser=argparse.ArgumentParser(description='BatteryWatch TCP/TLS storage server')
    parser.add_argument('--config',default=str(Path(__file__).with_name('server.local.json')))
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init',help='Create local configuration and client credentials')
    init.add_argument('--site',default='site-01'); init.add_argument('--device',default='battery-01')
    sub.add_parser('check',help='Validate configuration')
    doctor=sub.add_parser('doctor',help='Read-only deployment checks; no credentials are printed')
    doctor.add_argument('--android-config',help='Optional Android google-services.json path')
    sub.add_parser('self-test',help='Isolated TCP/API/alarm integration checks; no configuration required')
    run=sub.add_parser('run',help='Run TCP receiver until Ctrl+C')
    run.add_argument('--demo-data',action='store_true',help='Serve 10 simulated modules using a separate demo database and existing API credentials')
    run.add_argument('--debug',action='store_true',help='Log communication metadata without tokens or payloads')
    mobile=sub.add_parser('enable-api',help='Create a separate read-only Android credential')
    mobile.add_argument('--site',default='site-01'); mobile.add_argument('--device',default='battery-01')
    inspect=sub.add_parser('inspect',help='Print saved history, latest snapshots and sessions as JSON')
    inspect.add_argument('--site'); inspect.add_argument('--device')
    inspect.add_argument('--limit',type=int,default=20)
    backup=sub.add_parser('backup',help='Create a consistent SQLite backup')
    backup.add_argument('output')
    args=parser.parse_args()
    try:
        if args.command=='self-test':
            from local_demo import self_test
            print(json.dumps(asyncio.run(self_test()),indent=2))
            return
        if args.command=='doctor':
            from diagnostics import inspect_config
            report=inspect_config(args.config,args.android_config)
            print(json.dumps(report,indent=2))
            if not report['ok']: parser.exit(1)
            return
        if args.command=='init':
            credentials=initialize(args.config,args.site,args.device)
            print('Configuration created:',Path(args.config).resolve())
            print('Client connection values (contains secret token):',credentials)
            return
        config=load_config(args.config)
        if args.command=='enable-api':
            path=Path(args.config).resolve()
            credentials=path.parent/'android-connection.local.json'
            raw=json.loads(path.read_text(encoding='utf-8-sig'))
            if credentials.exists() or raw.get('api'): raise ValueError('Existing Android API settings will not be overwritten')
            grant=dict(site_id=args.site,device_id=args.device)
            if not any(grant in c['devices'] for c in config['collectors']): raise ValueError('Register the collector site/device first')
            token=secrets.token_urlsafe(32)
            raw['api']=dict(enabled=True,host='127.0.0.1',port=8443,viewers=[dict(id='android-01',token_sha256=hashlib.sha256(token.encode()).hexdigest(),devices=[grant])])
            scheme='https' if config['tls'].get('certfile') else 'http'
            with credentials.open('x',encoding='utf-8') as f:
                json.dump(dict(server_url=scheme+'://127.0.0.1:8443',token=token),f,indent=2)
            temporary=path.with_suffix('.local.json.tmp')
            temporary.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(path)
            print('Android API enabled. Connection settings:',credentials)
            return
        if args.command=='run' and args.demo_data:
            from smartphone_demo import prepare
            config=prepare(config)
        configure_api(config)
        configure_alarms(config)
        if args.command=='check':
            print('Configuration OK; collectors:',len(config['collectors']))
            return
        if args.command=='run':
            logs=Path(args.config).resolve().parent/'logs'; logs.mkdir(exist_ok=True)
            logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',
                                handlers=[logging.StreamHandler(),RotatingFileHandler(logs/'server.log',maxBytes=5*1024*1024,backupCount=5,encoding='utf-8')])
            logging.getLogger('batterywatch').setLevel(logging.DEBUG if args.debug else logging.INFO)
            logging.info('Communication debug=%s; log=%s',args.debug,logs/'server.log')
            asyncio.run(serve(config, demo_data=args.demo_data))
        else:
            if not Path(config['database']).is_file(): raise ValueError('Database not created yet; run the receiver first')
            storage=Storage(config['database'])
            if args.command=='inspect':
                if not 1<=args.limit<=1000: raise ValueError('limit must be 1..1000')
                print(json.dumps(storage.inspect(args.site,args.device,args.limit),ensure_ascii=False,indent=2))
            elif args.command=='backup':
                storage.backup(args.output); print('Backup created:',args.output)
    except (ValueError,OSError) as exc:
        parser.exit(1,str(exc)+'\n')


if __name__=='__main__': main()
