"""Fresh local-only real-stack smoke; see _docs/demo.md for prerequisites."""
import argparse
from contextlib import ExitStack
import json
import os
import platform
from datetime import datetime,timezone
from pathlib import Path
import queue
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
CONFIRM='student-marketplace-local-demo'


def run(command,*,env=None,cwd=ROOT,timeout=60):
 result=subprocess.run([str(p) for p in command],cwd=cwd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode:raise RuntimeError('A local prerequisite/service command failed; check installed versions and available loopback ports.')
 return result


def free_port():
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def wait_http(url,process=None,timeout=20):
 import urllib.request
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  if process is not None and process.poll() is not None:raise RuntimeError('Owned frontend stopped before readiness.')
  try:
   with urllib.request.urlopen(url,timeout=1) as response:
    if response.status==200:return
  except Exception:time.sleep(.1)
 raise RuntimeError('Owned loopback service did not become ready before timeout.')


def stop_process(process):
 if process is None or process.poll() is not None:return
 process.terminate()
 try:process.wait(timeout=8)
 except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def main(argv=None):
 parser=argparse.ArgumentParser(description='Real local MVP smoke in a newly created disposable cluster only')
 parser.add_argument('--postgres-bin',type=Path,required=True)
 parser.add_argument('--confirm-disposable-demo',required=True,choices=[CONFIRM])
 parser.add_argument('--node',default=shutil.which('node'))
 parser.add_argument('--browser-executable',type=Path)
 parser.add_argument('--evidence-dir',type=Path,default=ROOT/'_docs/evidence')
 args=parser.parse_args(argv)
 private=None;pg_started=False;frontend=browser=None;server=None;server_thread=None;database=None
 evidence=args.evidence_dir.resolve();evidence.mkdir(parents=True,exist_ok=True)
 (evidence/'demo-result.json').write_text(json.dumps({'result':'RUNNING'}))
 stage='prerequisites';result=1;cleanup_ok=True
 try:
  # Exact executable paths; never attach to or reset an existing database/service.
  suffix='.exe' if os.name=='nt' else ''
  pg=args.postgres_bin.resolve(strict=True)
  binaries={name:pg/(name+suffix) for name in ['initdb','pg_ctl','createdb']}
  if not all(p.is_file() for p in binaries.values()) or not args.node:raise RuntimeError('PostgreSQL bin tools and Node are required.')
  if args.browser_executable is not None and not args.browser_executable.resolve(strict=True).is_file():raise RuntimeError('Browser executable is unavailable.')
  if not (ROOT/'frontend/node_modules/playwright/package.json').is_file():raise RuntimeError('Run pinned frontend npm ci first, including optional browser smoke dependency.')
  parent=ROOT/'.venv/tmp';parent.mkdir(parents=True,exist_ok=True)
  private=parent/('local-demo-'+secrets.token_hex(8));private.mkdir()
  marker=private/'owned-demo.json';marker.write_text(json.dumps({'confirmation':CONFIRM,'nonce':secrets.token_hex(16)}))
  ports=[]
  while len(ports)<3:
   port=free_port()
   if port not in ports:ports.append(port)
  pg_port,api_port,web_port=ports
  cluster=private/'postgres';uploads=private/'uploads';database_name='student_marketplace_test_demo'
  stage='fresh PostgreSQL';print('SMOKE fresh-postgresql',flush=True)
  run([binaries['initdb'],'-D',cluster,'-U','marketplace_demo','-A','trust','--encoding=UTF8','--no-locale'])
  pg_started=True
  run([binaries['pg_ctl'],'-D',cluster,'-l',private/'postgres.log','-o',f'-h 127.0.0.1 -p {pg_port}','-w','-t','20','start'])
  run([binaries['createdb'],'-h','127.0.0.1','-p',str(pg_port),'-U','marketplace_demo',database_name])
  from backend.config import load_settings
  from backend.database import Database
  from backend.app import create_app
  from backend.mail import SmtpSender
  from alembic import command
  from alembic.config import Config
  import uvicorn
  # SMTP helpers have no public code endpoint: messages stay in this process's memory.
  sys.path.insert(0,str(ROOT/'tests'))
  from smtp_support import loopback_smtp,ExplicitTestSMTP
  from PIL import Image
  image=private/'synthetic.png';Image.new('RGB',(64,64),(72,112,155)).save(image)
  with ExitStack() as stack:
   smtp=stack.enter_context(loopback_smtp())
   environment={'APP_ENV':'test','DATABASE_URL':f'postgresql+psycopg://marketplace_demo@127.0.0.1:{pg_port}/{database_name}',
    'JWT_SECRET_KEY':secrets.token_urlsafe(48),'FRONTEND_ORIGINS':json.dumps([f'http://127.0.0.1:{web_port}']),
    'UPLOAD_DIR':str(uploads),'SMTP_HOST':'127.0.0.1','SMTP_PORT':str(smtp.server_address[1]),
    'SMTP_USERNAME':secrets.token_urlsafe(16),'SMTP_PASSWORD':secrets.token_urlsafe(24),'SMTP_FROM_EMAIL':'demo@example.invalid'}
   settings=load_settings(environ=environment,env_file=None);database=Database(settings)
   cfg=Config(str(ROOT/'alembic.ini'));cfg.attributes['settings']=settings
   stage='fresh migrations';print('SMOKE fresh-migrations',flush=True);command.upgrade(cfg,'head')
   app=create_app(settings,database,sender=SmtpSender(settings,smtp_factory=ExplicitTestSMTP))
   server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=api_port,access_log=False,log_config=None,log_level='critical',proxy_headers=False))
   server_thread=threading.Thread(target=server.run,daemon=True);server_thread.start()
   wait_http(f'http://127.0.0.1:{api_port}/openapi.json')
   stage='React production build';print('SMOKE react-production-build',flush=True)
   vite=ROOT/'frontend/node_modules/vite/bin/vite.js'
   node_env=os.environ|{'VITE_API_ORIGIN':f'http://127.0.0.1:{api_port}','VITE_SERVICE_MODE':'real','SMOKE_MEMORY_RESTART':'0','SMOKE_SQLITE_RESTART':'0'}
   run([args.node,vite,'build','--outDir',private/'frontend'],env=node_env,cwd=ROOT/'frontend')
   frontend=subprocess.Popen([args.node,str(vite),'preview','--host','127.0.0.1','--port',str(web_port),'--strictPort','--outDir',str(private/'frontend')],cwd=ROOT/'frontend',env=node_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   wait_http(f'http://127.0.0.1:{web_port}',frontend)
   stage='browser journey'
   node_env|={'SMOKE_WEB':f'http://127.0.0.1:{web_port}','SMOKE_API':f'http://127.0.0.1:{api_port}','SMOKE_PASSWORD':secrets.token_urlsafe(24),'SMOKE_IMAGE':str(image),'SMOKE_EVIDENCE':str(evidence)}
   if args.browser_executable:node_env['SMOKE_BROWSER_EXECUTABLE']=str(args.browser_executable.resolve())
   browser=subprocess.Popen([args.node,str(ROOT/'tools/demo_browser.mjs')],cwd=ROOT,env=node_env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   events=queue.Queue()
   def read_events():
    for line in browser.stdout:events.put(line)
   threading.Thread(target=read_events,daemon=True).start()
   deadline=time.monotonic()+180;passed=False
   while time.monotonic()<deadline:
    try:line=events.get(timeout=.25)
    except queue.Empty:
     if browser.poll() is not None:break
     continue
    event=json.loads(line)
    if event.get('event')=='code':
     email=event['email']
     if not re.fullmatch(r'demo-(seller|buyer|admin)@sdu\.edu\.kz',email):raise RuntimeError('Unexpected smoke mailbox request.')
     end=time.monotonic()+10;code=None
     while time.monotonic()<end:
      for _,recipient,message in reversed(smtp.messages):
       if recipient==email:
        match=re.search(r'code is: ([0-9]{6})',message.get_content())
        if match:code=match.group(1);break
      if code:break
      time.sleep(.05)
     if code is None:raise RuntimeError('Controlled SMTP message did not arrive.')
     browser.stdin.write(json.dumps({'code':code})+'\n');browser.stdin.flush()
    elif event.get('event')=='promote':
     run([sys.executable,'-m','backend.admin','--email','demo-admin@sdu.edu.kz'],env=os.environ|environment)
     browser.stdin.write('{"promoted":true}\n');browser.stdin.flush()
    elif event.get('event')=='stage':
     # Only fixed stage identifiers, never browser errors/addresses/codes, reach the terminal.
     value=event.get('name','')
     if not re.fullmatch(r'[a-z-]{1,64}',value):raise RuntimeError('Unexpected smoke stage.')
     print('SMOKE '+value,flush=True)
    elif event.get('event')=='pass':passed=True;break
    elif event.get('event')=='fail':raise RuntimeError('Browser assertion failed at '+str(event.get('step','unknown')))
   if not passed:raise RuntimeError('Real browser journey did not pass before its deadline.')
   browser.wait(timeout=10)
   if browser.returncode:raise RuntimeError('Browser runner failed to close cleanly.')
   from sqlalchemy import select
   from backend.models import User,Listing
   with database.session() as session:
    if session.scalar(select(User.id).where(User.email=='demo-seller@sdu.edu.kz')) is not None or list(session.scalars(select(Listing.id))):raise RuntimeError('Account/content cleanup did not persist.')
    if len(list(session.scalars(select(User.id))))!=2:raise RuntimeError('Unrelated demo identities were not preserved.')
   if uploads.exists() and any(p.is_file() for p in uploads.rglob('*')):raise RuntimeError('Owned image cleanup left unexpected files.')
  result=0
 except Exception as error:
  # Never echo subprocess/browser exception text, environment, SQL, mail or credentials.
  safe=str(error) if isinstance(error,RuntimeError) else 'A prerequisite or assertion failed; no success is claimed.'
  print('FAIL local MVP smoke at '+stage+': '+safe,flush=True)
  result=1
 finally:
  stop_process(browser);stop_process(frontend)
  if server is not None:server.should_exit=True
  if server_thread is not None:
   server_thread.join(timeout=10)
   if server_thread.is_alive():cleanup_ok=False
  if database is not None:database.dispose()
  if pg_started:
   try:run([binaries['pg_ctl'],'-D',private/'postgres','-w','-t','15','stop'],timeout=20)
   except Exception:print('FAIL owned PostgreSQL shutdown requires operator review; artifacts preserved.',flush=True);cleanup_ok=False
  if private is not None and cleanup_ok:
   # Only our freshly generated direct child with marker; never user-supplied paths.
   expected=ROOT/'.venv/tmp'
   if private.parent==expected and re.fullmatch(r'local-demo-[0-9a-f]{16}',private.name) and (private/'owned-demo.json').is_file() and private.resolve()==private:
    try:shutil.rmtree(private)
    except OSError:cleanup_ok=False
   else:cleanup_ok=False
 if not cleanup_ok:
  print('FAIL owned demo cleanup remains pending; no overall PASS.',flush=True);result=1
 record=json.loads((evidence/'demo-result.json').read_text()) if result==0 else {}
 record.update(result='PASS' if result==0 else 'FAIL',cleanup='complete' if cleanup_ok else 'pending',python=platform.python_version(),recorded_at=datetime.now(timezone.utc).isoformat())
 if result==0:
  record['postgresql']=subprocess.run([str(pg/('postgres'+suffix)),'--version'],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stdout.strip()
 (evidence/'demo-result.json').write_text(json.dumps(record,indent=2)+'\n')
 if result==0:print('PASS real-stack local MVP smoke; owned services stopped and disposable data cleaned.',flush=True)
 return result

if __name__=='__main__':raise SystemExit(main())
