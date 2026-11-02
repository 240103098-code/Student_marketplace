"""Bounded Compose-only startup and PostgreSQL readiness, without secret output."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading
import urllib.request

import psycopg
from sqlalchemy.engine import make_url
from backend.config import load_settings


class Readiness:
    def __init__(self, settings):
        self.settings=settings
        self.slots=threading.BoundedSemaphore(2)
        self.workers=ThreadPoolExecutor(max_workers=2,thread_name_prefix='readiness')

    def _check(self):
        try:
            url=make_url(self.settings.database_url.get_secret_value())
            if url.drivername not in {'postgresql','postgresql+psycopg'}:return False
            with psycopg.connect(url.set(drivername='postgresql').render_as_string(hide_password=False),connect_timeout=2,options='-c statement_timeout=1000 -c lock_timeout=1000 -c default_transaction_read_only=on') as connection:
                return connection.execute('SELECT version_num FROM alembic_version').fetchall()==[('0003_listings',)]
        except Exception:return False
        finally:self.slots.release()

    async def ready(self):
        if not self.slots.acquire(blocking=False):return False
        future=asyncio.get_running_loop().run_in_executor(self.workers,self._check)
        try:return await asyncio.wait_for(asyncio.shield(future),timeout=4)
        except asyncio.TimeoutError:return False

    def close(self):
        self.workers.shutdown(wait=False,cancel_futures=True)


def postgres_settings():
    settings=load_settings()
    if make_url(settings.database_url.get_secret_value()).drivername not in {'postgresql','postgresql+psycopg'}:
        raise ValueError('Compose requires explicit PostgreSQL')
    return settings


def main(argv=None):
    parser=argparse.ArgumentParser(description='Bounded local Compose runtime')
    parser.add_argument('action',choices=['migrate','prepare-uploads','serve','probe'])
    args=parser.parse_args(argv)
    try:
        if args.action=='prepare-uploads':
            # This command never accepts a caller path or walks existing files.
            root=Path('/data/uploads')
            if root.is_symlink() or root.resolve()!=root or not stat.S_ISDIR(root.lstat().st_mode):raise ValueError('Invalid mounted volume')
            os.chown(root,10001,10001);os.chmod(root,0o700)
        elif args.action=='probe':
            with urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=5) as response:
                if response.status!=200:return 1
        else:
            postgres_settings()
            if args.action=='migrate':
                result=subprocess.run([sys.executable,'-m','alembic','-c','alembic.ini','upgrade','head'],capture_output=True,timeout=60)
                if result.returncode:raise RuntimeError('Migration failed')
            else:
                import uvicorn
                uvicorn.run('backend.packaged:create_packaged_app',factory=True,host='0.0.0.0',port=8000,proxy_headers=False,access_log=False)
    except (Exception,KeyboardInterrupt):
        print('Compose operation failed; verify private configuration, database health and migration state.')
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
