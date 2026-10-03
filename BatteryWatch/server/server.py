"""Run with --help. Firebase delivery optionally uses firebase-admin."""
import atexit
import argparse
import asyncio
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from receiver import Receiver, load_config, identifier
from storage import Storage
from mobile_api import MobileApi, configure_api
from alarms import AlarmEngine, configure as configure_alarms, monitor
from push import FirebaseSender, Dispatcher, deliver


def parse_grant(value):
    site, separator, device = value.partition('/')
    if not separator or not identifier(site) or not identifier(device):
        raise ValueError('Device grant must be SITE_ID/DEVICE_ID')
    return dict(site_id=site, device_id=device)


def unique_grants(grants):
    result=[]
    for grant in grants:
        if grant not in result:
            result.append(grant)
    return result


def initialize(path, site, device, grants=None):
    path=Path(path).resolve()
    credentials=path.parent/'client-connection.local.json'
    if path.exists() or credentials.exists():
        raise ValueError('Existing configuration/credentials will not be overwritten')
    configured_grants=unique_grants(grants or [dict(site_id=site,device_id=device)])
    if not configured_grants or any(not all(identifier(g.get(k)) for k in ('site_id','device_id')) for g in configured_grants):
        raise ValueError('Invalid site/device grant')
    token=secrets.token_urlsafe(32)
    config=dict(host='127.0.0.1',port=9443,database='data/batterywatch.sqlite3',tls={},
                max_connections=32,idle_timeout=3700,frame_timeout=15,max_frame_bytes=16*1024*1024,
                collectors=[dict(id='collector-01',token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                                 devices=configured_grants)])
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f: json.dump(config,f,ensure_ascii=False,indent=2)
    with credentials.open('x',encoding='utf-8') as f:
        grant=configured_grants[0]
        json.dump(dict(host='127.0.0.1',port=9443,tls=False,token=token,site_id=grant['site_id'],device_id=grant['device_id'],interval=5),f,ensure_ascii=False,indent=2)
    return credentials


async def serve(config, demo_data=False, debug_control=None, ready_file=None):
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
    if debug_control is not None:
        from communication_log import watch
        jobs.append(asyncio.create_task(watch(debug_control,stop)))
    if demo_data:
        from smartphone_demo import feed
        logging.warning('SIMULATED DEMO: 10 modules, updates every 5 seconds; database=%s; real uploads rejected; push disabled',config['database'])
        jobs.append(asyncio.create_task(feed(storage,stop)))
    if sender: jobs.append(asyncio.create_task(deliver(Dispatcher(storage,config,sender),stop)))
    loop=asyncio.get_running_loop()
    previous={}
    def terminate(_signum,_frame): loop.call_soon_threadsafe(stop.set)
    for signum in (signal.SIGINT,signal.SIGTERM):
        previous[signum]=signal.signal(signum,terminate)
    if ready_file is not None:
        Path(ready_file).touch()
    try:
        await stop.wait()
    finally:
        stop.set()
        await asyncio.gather(*jobs,return_exceptions=True)
        await api.close()
        await receiver.close()
        for signum,handler in previous.items(): signal.signal(signum,handler)


def pid_file_for(config_path):
    return Path(config_path).resolve().with_suffix('.pid')


def read_pid_record(pid_file):
    try:
        record=json.loads(pid_file.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except (OSError,json.JSONDecodeError) as exc:
        raise ValueError('Cannot read server PID file: '+str(pid_file)) from exc
    if not isinstance(record,dict) or type(record.get('pid')) is not int or record['pid'] <= 1:
        raise ValueError('Invalid server PID file: '+str(pid_file))
    return record


def managed_process_matches(pid, config_path):
    if not sys.platform.startswith('linux'):
        raise ValueError('Managed background process control is supported on Linux only')
    proc=Path('/proc')/str(pid)
    try:
        if (proc/'stat').read_text(encoding='ascii').split(') ',1)[1].split()[0]=='Z':
            return False
        command=(proc/'cmdline').read_bytes().decode(errors='replace').split('\0')
    except (FileNotFoundError,ProcessLookupError,IndexError):
        return False
    expected_script=str(Path(__file__).resolve())
    expected_config=str(Path(config_path).resolve())
    try:
        config_index=command.index('--config')
    except ValueError:
        return False
    return (
        expected_script in command
        and '--daemon-child' in command
        and 'run' in command
        and config_index+1 < len(command)
        and str(Path(command[config_index+1]).resolve())==expected_config
    )


def remove_daemon_files(pid_file, ready_file):
    try:
        record=read_pid_record(pid_file)
        if record is not None and record['pid']==os.getpid():
            pid_file.unlink(missing_ok=True)
    except (OSError,ValueError):
        logging.exception('Unable to remove server PID file %s',pid_file)
    if ready_file is not None:
        Path(ready_file).unlink(missing_ok=True)


def stop_background(config_path, timeout=15):
    pid_file=pid_file_for(config_path)
    record=read_pid_record(pid_file)
    if record is None:
        print('No managed background server is running for '+str(Path(config_path).resolve()))
        return False
    pid=record['pid']
    if not managed_process_matches(pid,config_path):
        pid_file.unlink(missing_ok=True)
        print('Removed stale PID file; no matching server process was running.')
        return False
    os.kill(pid,signal.SIGTERM)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if not managed_process_matches(pid,config_path):
            pid_file.unlink(missing_ok=True)
            print('Server stopped (PID '+str(pid)+').')
            return True
        time.sleep(0.1)
    log_path=Path(config_path).resolve().parent/'logs'/'server.log'
    raise TimeoutError('Server PID '+str(pid)+' did not stop within '+str(timeout)+' seconds; inspect '+str(log_path)+'.')


def start_background(config_path, debug=False, demo_data=False, timeout=15):
    if not sys.platform.startswith('linux'):
        raise ValueError('--background is supported on Linux only; use --foreground on this platform')
    config_path=Path(config_path).resolve()
    pid_file=pid_file_for(config_path)
    ready_file=pid_file.with_suffix('.ready')
    pid_file.parent.mkdir(parents=True,exist_ok=True)
    record=read_pid_record(pid_file)
    if record is not None:
        if managed_process_matches(record['pid'],config_path):
            raise ValueError('Server is already running (PID '+str(record['pid'])+').')
        pid_file.unlink(missing_ok=True)
    ready_file.unlink(missing_ok=True)
    log_dir=config_path.parent/'logs'
    log_dir.mkdir(exist_ok=True)
    command=[
        sys.executable,str(Path(__file__).resolve()),
        '--config',str(config_path),'run','--daemon-child','--ready-file',str(ready_file),
    ]
    if debug:
        command.append('--debug')
    if demo_data:
        command.append('--demo-data')
    console_log=log_dir/'server-daemon.log'
    with console_log.open('ab',buffering=0) as output:
        process=subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).resolve().parent),
            start_new_session=True,
            close_fds=True,
        )
    record=dict(pid=process.pid,debug=bool(debug),demo_data=bool(demo_data))
    temporary=pid_file.with_name(pid_file.name+'.tmp')
    temporary.write_text(json.dumps(record),encoding='utf-8')
    temporary.replace(pid_file)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if ready_file.exists() and managed_process_matches(process.pid,config_path):
            print('Server started in background (PID '+str(process.pid)+').')
            print('PID file: '+str(pid_file))
            print('Log: '+str(log_dir/'server.log'))
            return process.pid
        if process.poll() is not None:
            pid_file.unlink(missing_ok=True)
            ready_file.unlink(missing_ok=True)
            raise RuntimeError('Server exited during startup; inspect '+str(console_log))
        time.sleep(0.1)
    if managed_process_matches(process.pid,config_path):
        os.kill(process.pid,signal.SIGTERM)
    raise TimeoutError('Server did not become ready within '+str(timeout)+' seconds; inspect '+str(console_log))


def restart_background(config_path, debug=None, demo_data=None, timeout=15):
    pid_file=pid_file_for(config_path)
    record=read_pid_record(pid_file)
    previous_debug=record.get('debug',False) if record else False
    previous_demo=record.get('demo_data',False) if record else False
    stop_background(config_path,timeout)
    return start_background(
        config_path,
        previous_debug if debug is None else debug,
        previous_demo if demo_data is None else demo_data,
        timeout,
    )


def main():
    parser=argparse.ArgumentParser(description='BatteryWatch TCP/TLS storage server')
    parser.add_argument('--config',default=str(Path(__file__).with_name('server.local.json')))
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init',help='Create local configuration and client credentials')
    init.add_argument('--site'); init.add_argument('--device')
    init.add_argument('--grant',action='append',default=[],metavar='SITE_ID/DEVICE_ID',
                      help='Additional authorized site/device pair; repeat for multiple pairs')
    sub.add_parser('check',help='Validate configuration')
    doctor=sub.add_parser('doctor',help='Read-only deployment checks; no credentials are printed')
    doctor.add_argument('--android-config',help='Optional Android google-services.json path')
    sub.add_parser('self-test',help='Isolated TCP/API/alarm integration checks; no configuration required')
    run=sub.add_parser('run',help='Run TCP receiver')
    run_mode=run.add_mutually_exclusive_group()
    run_mode.add_argument('--background',action='store_true',help='Start a detached Linux background process')
    run_mode.add_argument('--foreground',action='store_true',help='Run in this terminal (the default)')
    run.add_argument('--demo-data',action='store_true',help='Serve 10 simulated modules using a separate demo database and existing API credentials')
    run.add_argument('--debug',action='store_true',help='Log communication metadata without tokens or payloads')
    run.add_argument('--daemon-child',action='store_true',help=argparse.SUPPRESS)
    run.add_argument('--ready-file',help=argparse.SUPPRESS)
    stop=sub.add_parser('stop',help='Gracefully stop a managed background server')
    stop.add_argument('--timeout',type=float,default=15,help='Seconds to wait for graceful shutdown (default: 15)')
    restart=sub.add_parser('restart',help='Gracefully restart a managed background server')
    debug_mode=restart.add_mutually_exclusive_group()
    debug_mode.add_argument('--debug',action='store_const',const=True,default=None,help='Enable communication metadata logging')
    debug_mode.add_argument('--no-debug',action='store_const',const=False,help='Disable communication metadata logging')
    demo_mode=restart.add_mutually_exclusive_group()
    demo_mode.add_argument('--demo-data',action='store_const',const=True,default=None,help='Restart with simulated demo data')
    demo_mode.add_argument('--no-demo-data',action='store_const',const=False,help='Restart without simulated demo data')
    restart.add_argument('--timeout',type=float,default=15,help='Seconds to wait for graceful shutdown (default: 15)')
    debug=sub.add_parser('debug',help='Change communication logging in a running server')
    debug.add_argument('state',choices=('on','off'))
    mobile=sub.add_parser('enable-api',help='Create a separate read-only Android credential')
    mobile.add_argument('--site'); mobile.add_argument('--device')
    mobile.add_argument('--grant',action='append',default=[],metavar='SITE_ID/DEVICE_ID',
                        help='Limit the viewer to this authorized pair; repeat for multiple pairs (default: all collector grants)')
    inspect=sub.add_parser('inspect',help='Print saved history, latest snapshots and sessions as JSON')
    inspect.add_argument('--site'); inspect.add_argument('--device')
    inspect.add_argument('--limit',type=int,default=20)
    backup=sub.add_parser('backup',help='Create a consistent SQLite backup')
    backup.add_argument('output')
    args=parser.parse_args()
    try:
        if args.command=='run' and args.daemon_child:
            if not args.ready_file:
                raise ValueError('Managed child requires a readiness file')
            atexit.register(remove_daemon_files,pid_file_for(args.config),args.ready_file)
        if args.command=='stop':
            if args.timeout<=0: raise ValueError('--timeout must be positive')
            stop_background(args.config,args.timeout)
            return
        if args.command=='restart':
            if args.timeout<=0: raise ValueError('--timeout must be positive')
            restart_background(args.config,args.debug,args.demo_data,args.timeout)
            return
        if args.command=='debug':
            from communication_log import control_path, write_control
            target=control_path(args.config)
            write_control(target,args.state=='on')
            print('Debug '+args.state+' requested. A running server using this config applies it within about 1 second: '+str(target))
            return
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
            grants=[parse_grant(value) for value in args.grant]
            if args.site is not None or args.device is not None:
                if args.site is None or args.device is None:
                    raise ValueError('--site and --device must be provided together')
                grants.append(dict(site_id=args.site,device_id=args.device))
            if not grants:
                grants=[dict(site_id=args.site or 'site-01',device_id=args.device or 'battery-01')]
            credentials=initialize(args.config,args.site,args.device,grants)
            print('Configuration created:',Path(args.config).resolve())
            print('Client connection values (contains secret token):',credentials)
            return
        config=load_config(args.config)
        if args.command=='enable-api':
            path=Path(args.config).resolve()
            credentials=path.parent/'android-connection.local.json'
            raw=json.loads(path.read_text(encoding='utf-8-sig'))
            if credentials.exists() or raw.get('api'): raise ValueError('Existing Android API settings will not be overwritten')
            registered=unique_grants(g for c in config['collectors'] for g in c['devices'])
            requested=[parse_grant(value) for value in args.grant]
            if args.site is not None or args.device is not None:
                if args.site is None or args.device is None:
                    raise ValueError('--site and --device must be provided together')
                requested.append(dict(site_id=args.site,device_id=args.device))
            grants=unique_grants(requested or registered)
            if any(grant not in registered for grant in grants):
                raise ValueError('Every viewer grant must be registered for a collector')
            token=secrets.token_urlsafe(32)
            raw['api']=dict(enabled=True,host='127.0.0.1',port=8443,viewers=[dict(id='android-01',token_sha256=hashlib.sha256(token.encode()).hexdigest(),devices=grants)])
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
            if args.background:
                start_background(args.config,args.debug,args.demo_data)
                return
            logs=Path(args.config).resolve().parent/'logs'; logs.mkdir(exist_ok=True)
            logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',
                                handlers=[logging.StreamHandler(),RotatingFileHandler(logs/'server.log',maxBytes=5*1024*1024,backupCount=5,encoding='utf-8')])
            logging.getLogger('batterywatch').setLevel(logging.DEBUG if args.debug else logging.INFO)
            logging.info('Communication debug=%s; log=%s',args.debug,logs/'server.log')
            from communication_log import control_path, write_control
            control=control_path(args.config)
            write_control(control,args.debug)
            asyncio.run(serve(config, demo_data=args.demo_data, debug_control=control,ready_file=args.ready_file))
        else:
            if not Path(config['database']).is_file(): raise ValueError('Database not created yet; run the receiver first')
            storage=Storage(config['database'])
            if args.command=='inspect':
                if not 1<=args.limit<=1000: raise ValueError('limit must be 1..1000')
                print(json.dumps(storage.inspect(args.site,args.device,args.limit),ensure_ascii=False,indent=2))
            elif args.command=='backup':
                storage.backup(args.output); print('Backup created:',args.output)
    except (ValueError,OSError,RuntimeError,TimeoutError,subprocess.SubprocessError) as exc:
        parser.exit(1,str(exc)+'\n')


if __name__=='__main__': main()
