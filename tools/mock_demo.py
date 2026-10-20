"""Own a bounded frontend-only mock demo without touching an existing preview."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from tools.local_demo import ROOT,free_port,stop_process,wait_http


def main(argv=None):
    parser=argparse.ArgumentParser(description="Start a fresh owned local mock preview and run the existing browser checks")
    parser.add_argument("--confirm-disposable-demo",required=True,choices=["student-marketplace-mock-demo"])
    parser.add_argument("--node",default=shutil.which("node"))
    parser.add_argument("--browser-executable",type=Path)
    parser.add_argument("--evidence-dir",type=Path,default=ROOT/"_docs/evidence/final-compliance/mock")
    args=parser.parse_args(argv)
    if not args.node:raise SystemExit("Node and pinned frontend dependencies are required")
    evidence=args.evidence_dir.resolve();evidence.mkdir(parents=True,exist_ok=True)
    record=evidence/"mock-browser-result.json";record.write_text('{"result":"RUNNING"}\n',encoding="utf-8")
    frontend=None;result=1
    try:
        port=free_port()
        environment=os.environ|{"VITE_SERVICE_MODE":"mock","MOCK_WEB_URL":f"http://127.0.0.1:{port}","MOCK_EVIDENCE_DIR":str(evidence)}
        if args.browser_executable:environment["MOCK_BROWSER_EXECUTABLE"]=str(args.browser_executable.resolve(strict=True))
        frontend=subprocess.Popen([args.node,str(ROOT/"frontend/node_modules/vite/bin/vite.js"),"--host","127.0.0.1","--port",str(port),"--strictPort"],
            cwd=ROOT/"frontend",env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        wait_http(environment["MOCK_WEB_URL"],frontend)
        browser=subprocess.run([args.node,str(ROOT/"tools/mock_browser.mjs")],cwd=ROOT,env=environment,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if browser.returncode:raise RuntimeError("Owned mock browser checks failed")
        if json.loads(record.read_text(encoding="utf-8"))["result"]!="PASS":raise RuntimeError("No measured mock PASS")
        result=0
    except Exception:
        record.write_text('{"result":"FAIL","detail":"Owned mock browser did not pass; no raw exception or credentials exported."}\n',encoding="utf-8")
    finally:
        stop_process(frontend)
        data=json.loads(record.read_text(encoding="utf-8"));data.update(owned_frontend_stopped=frontend is None or frontend.poll() is not None,recorded_at=datetime.now(timezone.utc).isoformat())
        record.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
        print(("PASS" if result==0 else "FAIL")+" explicit mock browser; only owned frontend stopped.")
    return result


if __name__=="__main__":raise SystemExit(main())
