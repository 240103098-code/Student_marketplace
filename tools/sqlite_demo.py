"""Confirmed disposable real React/FastAPI/SQLite journey including restart."""
import argparse
from contextlib import ExitStack
import json
import hashlib
import platform
import sqlite3
from datetime import datetime,timezone
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from tools.local_demo import ROOT, free_port, run, stop_process, wait_http

CONFIRM="student-marketplace-sqlite-demo"


def main(argv=None):
    parser=argparse.ArgumentParser(description="Real SQLite smoke in a newly owned disposable directory only")
    parser.add_argument("--confirm-disposable-demo",required=True,choices=[CONFIRM])
    parser.add_argument("--node",default=shutil.which("node"))
    parser.add_argument("--browser-executable",type=Path)
    parser.add_argument("--storage",choices=["sqlite","memory"],default="sqlite")
    parser.add_argument("--evidence-dir",type=Path,default=ROOT/"_docs/evidence/sqlite-persistence")
    args=parser.parse_args(argv)
    if not args.node:raise SystemExit("Node and pinned frontend dependencies/browser are prerequisites.")
    parent=ROOT/".venv/tmp";parent.mkdir(parents=True,exist_ok=True)
    temporary=tempfile.TemporaryDirectory(prefix="sqlite-demo-",dir=parent)
    private=Path(temporary.name).resolve()
    if not private.is_relative_to(parent.resolve()):raise RuntimeError("Owned temporary directory escaped its parent")
    evidence=args.evidence_dir.resolve();evidence.mkdir(parents=True,exist_ok=True)
    restart_checks=[];api_instances=0
    frontend=browser=server=worker=None
    cleanup_ok=True;result=1;stage="prerequisites"
    try:
        from alembic import command
        from alembic.config import Config
        from backend.app import create_app
        from backend.config import load_settings
        from backend.mail import SmtpSender
        from PIL import Image
        import uvicorn
        sys.path.insert(0,str(ROOT/"tests"))
        from smtp_support import loopback_smtp, ExplicitTestSMTP
        if not (ROOT/"frontend/node_modules/playwright/package.json").is_file():raise RuntimeError("Install pinned frontend dependencies first")
        image=private/"synthetic.png";Image.new("RGB",(64,64),(72,112,155)).save(image)
        api_port=free_port();web_port=free_port()
        while web_port==api_port:web_port=free_port()
        with ExitStack() as stack:
            smtp=stack.enter_context(loopback_smtp())
            environment={"APP_ENV":"test","DATABASE_URL":("sqlite+pysqlite:///:memory:" if args.storage=="memory" else "sqlite+pysqlite:///"+str(private/"marketplace.sqlite3")),
                "JWT_SECRET_KEY":secrets.token_urlsafe(48),"UPLOAD_DIR":str(private/"uploads"),
                "FRONTEND_ORIGINS":json.dumps([f"http://127.0.0.1:{web_port}"]),
                "SMTP_HOST":"127.0.0.1","SMTP_PORT":str(smtp.server_address[1]),
                "SMTP_USERNAME":secrets.token_urlsafe(16),"SMTP_PASSWORD":secrets.token_urlsafe(24),"SMTP_FROM_EMAIL":"demo@example.invalid"}
            settings=load_settings(environ=environment,env_file=None)
            cfg=Config(str(ROOT/"alembic-sqlite.ini"));cfg.attributes["settings"]=settings
            if args.storage=="sqlite":
                stage="sqlite-migrations";command.upgrade(cfg,"head")
            def start_api():
                nonlocal api_instances
                api_instances+=1
                app=create_app(settings,sender=SmtpSender(settings,smtp_factory=ExplicitTestSMTP))
                server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=api_port,
                    access_log=False,log_config=None,log_level="critical",proxy_headers=False))
                thread=threading.Thread(target=server.run,daemon=True);thread.start()
                try:
                    wait_http(f"http://127.0.0.1:{api_port}/openapi.json")
                except BaseException:
                    server.should_exit=True;thread.join(timeout=10)
                    app.state.close_owned_resources()
                    raise
                return server,thread
            server,worker=start_api()
            stage="real-frontend-build"
            vite=ROOT/"frontend/node_modules/vite/bin/vite.js"
            node_env=os.environ|{"VITE_API_ORIGIN":f"http://127.0.0.1:{api_port}","VITE_SERVICE_MODE":"real"}
            run([args.node,vite,"build","--outDir",private/"frontend"],env=node_env,cwd=ROOT/"frontend")
            frontend=subprocess.Popen([args.node,str(vite),"preview","--host","127.0.0.1","--port",str(web_port),"--strictPort","--outDir",str(private/"frontend")],
                cwd=ROOT/"frontend",env=node_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            wait_http(f"http://127.0.0.1:{web_port}",frontend)
            node_env|={"SMOKE_WEB":f"http://127.0.0.1:{web_port}","SMOKE_API":f"http://127.0.0.1:{api_port}",
                "SMOKE_PASSWORD":secrets.token_urlsafe(24),"SMOKE_IMAGE":str(image),"SMOKE_EVIDENCE":str(evidence),"SMOKE_SQLITE_RESTART":("1" if args.storage=="sqlite" else "0"),"SMOKE_MEMORY_RESTART":("1" if args.storage=="memory" else "0")}
            stage="browser-prerequisites"
            if args.browser_executable:node_env["SMOKE_BROWSER_EXECUTABLE"]=str(args.browser_executable.resolve(strict=True))
            browser=subprocess.Popen([args.node,str(ROOT/"tools/demo_browser.mjs")],cwd=ROOT,env=node_env,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            events=queue.Queue()
            def read_events():
                for line in browser.stdout:events.put(line)
            threading.Thread(target=read_events,daemon=True).start()
            deadline=time.monotonic()+180;passed=False
            while time.monotonic()<deadline:
                try:event=json.loads(events.get(timeout=.25))
                except queue.Empty:
                    if browser.poll() is not None:break
                    continue
                if event.get("event")=="code":
                    email=event["email"]
                    if not re.fullmatch(r"demo-(seller|buyer|admin)@sdu[.]edu[.]kz",email):raise RuntimeError("Unexpected synthetic mailbox request")
                    messages=[m for _,recipient,m in reversed(smtp.messages) if recipient==email]
                    code=re.search(r"code is: ([0-9]{6})",messages[0].get_content()).group(1)
                    answer={"code":code}
                elif event.get("event")=="promote":
                    if args.storage=="memory":
                        from backend.admin import main as provision
                        from contextlib import redirect_stdout
                        from io import StringIO
                        with redirect_stdout(StringIO()):
                            if provision(["--email","demo-admin@sdu.edu.kz"],database=server.config.app.state.database):
                                raise RuntimeError("Eligible existing memory account promotion failed")
                    else:
                        run([sys.executable,"-m","backend.admin","--email","demo-admin@sdu.edu.kz"],env=os.environ|environment)
                    answer={"promoted":True}
                elif event.get("event") in {"restart","memory-restart"}:
                    from sqlalchemy import func,select
                    from backend.models import User,EmailCode,RefreshSession,Listing,ListingPhoto,ListingReport,Category
                    def snapshot(app):
                        with app.state.database.session() as session:
                            state={model.__tablename__:session.scalar(select(func.count()).select_from(model)) for model in [User,EmailCode,RefreshSession,Listing,ListingPhoto,ListingReport,Category]}
                            state["prices"]=list(session.scalars(select(Listing.price).order_by(Listing.id)))
                            state["prices"]=[str(price) for price in state["prices"]]
                            state["listing_states"]=list(session.scalars(select(Listing.status).order_by(Listing.id)))
                            state["reviewed_reports"]=session.scalar(select(func.count()).select_from(ListingReport).where(ListingReport.reviewed_at.is_not(None)))
                        state["image_sha256"]=sorted(hashlib.sha256(path.read_bytes()).hexdigest() for path in app.state.settings.upload_dir.rglob("*") if path.is_file())
                        return state
                    old_app=server.config.app;old_root=old_app.state.settings.upload_dir
                    before=snapshot(old_app)
                    if before["users"]<2 or not before["image_sha256"]:raise RuntimeError("Restart has no real records/private image to verify")
                    server.should_exit=True;worker.join(timeout=10)
                    if worker.is_alive():raise RuntimeError("Owned API shutdown timed out; files preserved")
                    images_removed=not old_root.exists()
                    server,worker=start_api();after=snapshot(server.config.app)
                    if args.storage=="memory":
                        if not images_removed or any(after[name] for name in ["users","email_codes","refresh_sessions","listings","listing_photos","listing_reports"]):raise RuntimeError("Volatile restart preserved private state")
                        if after["categories"]!=5 or after["image_sha256"]:raise RuntimeError("Fresh memory bootstrap is not empty")
                    elif before!=after or images_removed:raise RuntimeError("Persistent restart changed records/images")
                    restart_checks.append({"phase":event.get("phase","memory-loss"),"before":before,"after":after,"old_private_root_removed":images_removed})
                    answer={"restarted":True,"state_reset":args.storage=="memory","private_images_removed":images_removed}
                elif event.get("event")=="stage":
                    stage=event.get("name","")
                    if not re.fullmatch(r"[a-z-]{1,64}",stage):raise RuntimeError("Unexpected smoke stage")
                    print("SQLITE SMOKE "+stage,flush=True);continue
                elif event.get("event")=="pass":passed=True;break
                else:
                    if event.get("event")=="fail":print("Browser assertion: "+str(event.get("kind","unknown"))+" expected="+str(event.get("expected","n/a"))+" actual="+str(event.get("actual","n/a"))+" view="+json.dumps(event.get("view",{})),flush=True)
                    raise RuntimeError("Browser assertion failed at "+stage)
                browser.stdin.write(json.dumps(answer)+"\n");browser.stdin.flush()
            if not passed:raise RuntimeError("Browser journey did not pass before its deadline")
            browser.wait(timeout=10)
            if browser.returncode:raise RuntimeError("Browser runner did not exit cleanly")
            record=json.loads((evidence/"demo-result.json").read_text(encoding="utf-8"))
            record.update(storage="real volatile FastAPI memory" if args.storage=="memory" else "real persistent SQLite",
                restart_checks=restart_checks, migration="explicit metadata/categories" if args.storage=="memory" else "sqlite_0001",
                sqlite=sqlite3.sqlite_version,python=platform.python_version(),recorded_at=datetime.now(timezone.utc).isoformat(),api_instances=api_instances)
            (evidence/"demo-result.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
            result=0
    except Exception:
        # No raw exception/SMTP/environment/body/SQL/secret evidence.
        print("FAIL SQLite smoke at "+stage+"; no success claimed.",flush=True)
    finally:
        stop_process(browser);stop_process(frontend)
        if server is not None:server.should_exit=True
        if worker is not None:
            worker.join(timeout=10);cleanup_ok=not worker.is_alive()
        if cleanup_ok:temporary.cleanup()
        else:
            temporary._finalizer.detach() # preserve live owned data for operator review
            result=1
        if result:
            (evidence/"demo-result.json").write_text(json.dumps({"result":"FAIL","stage":stage,"owned_services_stopped":cleanup_ok,"disposable_data_removed":not private.exists(),"api_instances":api_instances,"storage":args.storage})+"\n",encoding="utf-8")
        else:
            record=json.loads((evidence/"demo-result.json").read_text(encoding="utf-8"));record["cleanup"]="complete"
            (evidence/"demo-result.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
            print("PASS real "+args.storage+" browser journey/restart; owned services stopped and disposable data removed.",flush=True)
    return result


if __name__=="__main__":raise SystemExit(main())
