"""Explicit offline, backup-first SQLite to empty PostgreSQL migration.

No import-time settings, database or filesystem operations. Public failures never
include URLs, row data, hashes or paths; private recovery metadata stays in backup.
"""
import argparse
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from backend.config import REPOSITORY_ROOT
from backend.database import Base
from backend.models import CATEGORIES
from backend import models
from backend.images import ImageStorage

TABLES = ('categories','users','email_codes','refresh_sessions','listings','listing_photos','listing_reports')
SEQUENCES = ('users','email_codes','listings','listing_photos','listing_reports')
MAX_ROWS = 100000
MAX_STORED_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024

class MigrationError(Exception):
    pass


def fail(message):
    raise MigrationError(message)


def safe_path(value, *, exists=None):
    if not Path(value).is_absolute():fail('Explicit absolute storage paths are required.')
    path=Path(value).absolute()
    if path.resolve()!=path or any(part in {'.','..'} for part in Path(value).parts):
        fail('Unsafe storage path.')
    for part in (path,*path.parents):
        if part.is_symlink() or getattr(part,'is_junction',lambda:False)():fail('Unsafe storage path.')
    if exists is True and not path.exists():fail('Required source storage is missing.')
    if exists is False and path.exists():fail('Run-owned destination must not already exist.')
    return path


def digest_bytes(path):
    # All copied files are bounded before reads; never follow a final symlink.
    safe_path(path,exists=True)
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(65536),b''):digest.update(chunk)
    return digest.hexdigest()


def canonical(value):
    if isinstance(value,datetime):
        if value.tzinfo is None:fail('Source timestamp is not UTC-aware.')
        return value.astimezone(timezone.utc).isoformat(timespec='microseconds')
    if isinstance(value,Decimal):return format(value.quantize(Decimal('.01')),'f')
    if isinstance(value,uuid.UUID):return str(value)
    return value


def row_digest(rows):
    return hashlib.sha256(json.dumps([{k:canonical(v) for k,v in row.items()} for row in rows],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def rows_from(connection):
    rows={}
    for name in TABLES:
        table=Base.metadata.tables[name]
        rows[name]=[dict(row) for row in connection.execute(select(table).order_by(*table.primary_key.columns).limit(MAX_ROWS+1)).mappings()]
        if len(rows[name])>MAX_ROWS:fail('Migration exceeds bounded row limit.')
    return rows


def schema_signature(connection):
    inspector=inspect(connection)
    names=sorted(inspector.get_table_names(schema='public'))
    result={}
    for name in names:
        result[name]={
            'columns':[{k:(str(v) if k=='type' else v) for k,v in column.items() if k in {'name','type','nullable','default'}} for column in inspector.get_columns(name,schema='public')],
            'pk':inspector.get_pk_constraint(name,schema='public'),
            'fk':inspector.get_foreign_keys(name,schema='public'),
            'unique':inspector.get_unique_constraints(name,schema='public'),
            'checks':inspector.get_check_constraints(name,schema='public'),
            'indexes':inspector.get_indexes(name,schema='public'),
        }
    # Inspector may return SQLAlchemy text wrappers in dialect options.
    return json.loads(json.dumps(result,default=str,sort_keys=True))


def validate_sqlite_schema(raw):
    if raw.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:fail('Source integrity check failed.')
    if raw.execute('PRAGMA foreign_key_check').fetchall():fail('Source foreign-key check failed.')
    if raw.execute('SELECT version_num FROM alembic_version_sqlite').fetchall()!=[('sqlite_0001',)]:fail('Unsupported source schema head.')
    # Resolve the published snapshot by its unique revision filename, not caller input.
    files=list((REPOSITORY_ROOT/'migrations_sqlite/versions').glob('sqlite_0001*.py'))
    if len(files)!=1:fail('Published source schema is unavailable.')
    spec=importlib.util.spec_from_file_location('published_sqlite',files[0]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with closing(sqlite3.connect(':memory:')) as expected:
        expected.create_function('regexp',2,lambda p,v:bool(re.search(p,v or '')))
        for statement in module.DDL:expected.execute(statement)
        def shape(db):
            return sorted((kind,name,table,re.sub(r'\s+',' ',sql or '').strip()) for kind,name,table,sql in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name!='alembic_version_sqlite'"))
        if shape(raw)!=shape(expected):fail('Unsupported or changed source schema.')
    if raw.execute('PRAGMA table_info(alembic_version_sqlite)').fetchall()!=[(0,'version_num','VARCHAR(32)',1,None,1)]:fail('Unsupported migration metadata.')


def require_checkpointed_source(source):
    for suffix in ('-wal','-shm','-journal'):
        sidecar=Path(str(source)+suffix)
        if sidecar.exists() or sidecar.is_symlink() or getattr(sidecar,'is_junction',lambda:False)():
            fail('Checkpoint and close source; sidecars must be absent.')


@contextmanager
def source_snapshot(source):
    # Immutable is safe ONLY after rejecting every WAL/journal/SHM sidecar and
    # requiring operator quiescence; it avoids SQLite creating dry-run sidecars.
    require_checkpointed_source(source)
    before=digest_bytes(source)
    uri=source.as_uri()+'?mode=ro&immutable=1'
    def readonly_connection():
        connection=sqlite3.connect(uri,uri=True)
        connection.create_function('regexp',2,lambda pattern,value:int(value is not None and re.search(pattern,value) is not None),deterministic=True)
        connection.create_function('lower',1,lambda value:value.lower() if value is not None else None,deterministic=True)
        connection.create_function('gen_random_uuid',0,lambda:uuid.uuid4().hex)
        return connection
    engine=create_engine('sqlite+pysqlite://',creator=readonly_connection,poolclass=StaticPool,hide_parameters=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('BEGIN')
            raw=connection.connection.driver_connection
            validate_sqlite_schema(raw)
            yield connection,raw,before
            require_checkpointed_source(source)
            if digest_bytes(source)!=before:fail('Source changed during offline migration.')
    finally:engine.dispose()


def file_manifest(rows,root):
    manifest=[];seen=set();total=0
    candidates=[('avatars',row['id'],row['avatar_path']) for row in rows['users'] if row['avatar_path']]
    candidates += [('listings',row['listing_id'],row['storage_path']) for row in rows['listing_photos']]
    for namespace,owner,relative in candidates:
        path=ImageStorage(root,namespace).path(relative,owner)
        safe_path(path,exists=True)
        if not path.is_file() or path.stat().st_size>MAX_STORED_BYTES or relative in seen:fail('Invalid source image manifest.')
        size=path.stat().st_size;total+=size
        if total>MAX_TOTAL_BYTES:fail('Image manifest exceeds bounded limit.')
        manifest.append({'path':relative,'owner':owner,'namespace':namespace,'size':size,'sha256':digest_bytes(path)});seen.add(relative)
    return sorted(manifest,key=lambda row:row['path'])


def verify_files(root,manifest):
    for item in manifest:
        path=ImageStorage(root,item['namespace']).path(item['path'],item['owner'])
        if not path.is_file() or path.stat().st_size!=item['size'] or digest_bytes(path)!=item['sha256']:fail('Image bytes changed or are unavailable.')


def copy_manifest(source,destination,manifest):
    for item in manifest:
        origin=ImageStorage(source,item['namespace']).path(item['path'],item['owner'])
        target=ImageStorage(destination,item['namespace']).path(item['path'],item['owner'])
        safe_path(origin,exists=True)
        target.parent.mkdir(parents=True,exist_ok=True)
        with origin.open('rb') as input_file,target.open('xb') as output:
            remaining=item['size']
            while remaining:
                chunk=input_file.read(min(65536,remaining))
                if not chunk:fail('Source image changed while copying.')
                output.write(chunk);remaining-=len(chunk)
            if input_file.read(1):fail('Source image changed while copying.')
            output.flush();os.fsync(output.fileno())
        if digest_bytes(target)!=item['sha256']:fail('Copied image verification failed.')
    verify_files(source,manifest);verify_files(destination,manifest)


def sync_directory(path):
    if os.name=='posix':
        descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


def write_private(path,value):
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as handle:
            os.chmod(temporary,0o600);json.dump(value,handle,sort_keys=True);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,path);sync_directory(path.parent)
    finally:
        if temporary.exists():temporary.unlink()


def clean_owned(root,manifest,run_id):
    # No recursive delete: ownership marker + exact manifest + empty known dirs.
    safe_path(root,exists=True)
    marker=root/'.migration-owner'
    safe_path(marker,exists=True)
    if not marker.is_file() or marker.read_text()!=run_id:fail('Owned cleanup requires reconciliation.')
    allowed={root/item['path'] for item in manifest}
    entries=list(root.rglob('*'))
    for entry in entries:safe_path(entry,exists=True)
    actual={p for p in entries if p.is_file() and p!=marker}
    allowed_directories={parent for path in allowed for parent in path.parents if parent!=root and root in parent.parents}
    if any(p.is_dir() and p not in allowed_directories for p in entries):fail('Unexpected destination directories require reconciliation.')
    if actual-allowed:fail('Unexpected destination files require reconciliation.')
    for path in actual:
        safe_path(path,exists=True);path.unlink()
    for directory in sorted((p for p in root.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        safe_path(directory,exists=True);directory.rmdir()
    marker.unlink();root.rmdir()


def validate_target_schema(connection):
    if connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()!=['0003_listings']:fail('Unsupported destination schema head.')
    expected=json.loads((Path(__file__).with_name('migration_pg_schema.json')).read_text())
    if schema_signature(connection)!=expected:fail('Unsupported or changed destination schema.')
    if inspect(connection).get_view_names(schema='public') or inspect(connection).get_materialized_view_names(schema='public'):fail('Unexpected destination schema.')
    if set(inspect(connection).get_sequence_names(schema='public'))!={name+'_id_seq' for name in SEQUENCES}:fail('Unexpected destination sequences.')
    if connection.scalar(text("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace)")):fail('Unexpected destination triggers.')


def validate_target(connection):
    validate_target_schema(connection)
    rows=rows_from(connection)
    if rows['categories']!=[{'id':id,'key':key,'name':name} for id,key,name in CATEGORIES] or any(rows[name] for name in TABLES if name!='categories'):fail('Destination must contain only exact fixed category seeds.')


def migrate(*,source,source_uploads,target_url,destination_uploads,backup=None,execute=False,confirm_source=None,confirm_target=None,quiesced=False,_fault=None):
    if not quiesced:fail('Explicit offline source confirmation is required.')
    source=safe_path(source,exists=True);source_uploads=safe_path(source_uploads,exists=True)
    destination=safe_path(destination_uploads,exists=False)
    if not source.is_file() or source.suffix not in {'.sqlite','.sqlite3','.db'} or not source_uploads.is_dir():fail('Explicit supported source storage is required.')
    if not destination.parent.is_dir():fail('Destination parent must already exist.')
    url=make_url(target_url)
    if url.drivername not in {'postgresql','postgresql+psycopg'} or not url.database:fail('Explicit PostgreSQL target is required.')
    if execute and (confirm_source!=source.name or confirm_target!=url.database or backup is None):fail('Source/target confirmations and backup location are required.')
    backup=safe_path(backup,exists=False) if backup is not None else None
    roots=[source,source_uploads,destination]+([backup] if backup else [])
    for i,left in enumerate(roots):
        for right in roots[i+1:]:
            if left==right or left in right.parents or right in left.parents:fail('Storage roots must be separate and nonoverlapping.')
    engine=create_engine(url.set(drivername='postgresql+psycopg'),hide_parameters=True,connect_args={'connect_timeout':3,'options':'-c statement_timeout=10000 -c lock_timeout=3000'})
    run_id=uuid.uuid4().hex;stage=destination.with_name(destination.name+'.migration-'+run_id)
    published=False;committed=False;commit_attempted=False;created=False;journal={}
    try:
        with source_snapshot(source) as (src,raw,source_hash):
            rows=rows_from(src);digests={name:row_digest(values) for name,values in rows.items()}
            if rows['categories']!=[{'id':id,'key':key,'name':name} for id,key,name in CATEGORIES]:fail('Source categories differ from supported seeds.')
            manifest=file_manifest(rows,source_uploads)
            with engine.connect() as target:
                transaction=target.begin()
                try:
                    target.exec_driver_sql('SET LOCAL search_path TO public, pg_catalog')
                    target.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                    if execute:
                        target.exec_driver_sql('LOCK TABLE '+','.join(TABLES)+',alembic_version IN ACCESS EXCLUSIVE MODE')
                    if target.scalar(text('SELECT current_database()'))!=url.database:fail('Connected target differs from confirmed database.')
                    validate_target(target)
                    result={'mode':'execute' if execute else 'dry-run','status':'validated','rows':{name:len(values) for name,values in rows.items()},'files':len(manifest)}
                    if not execute:
                        verify_files(source_uploads,manifest);transaction.rollback();return result
                    backup.mkdir(mode=0o700)
                    journal={'run_id':run_id,'state':'backing-up','destination':str(destination),'staging':str(stage),'source_sha256':source_hash,'row_digests':digests,'manifest':manifest}
                    write_private(backup/'recovery.json',journal)
                    with closing(sqlite3.connect(backup/'source.sqlite3')) as saved:raw.backup(saved)
                    os.chmod(backup/'source.sqlite3',0o600)
                    with source_snapshot(backup/'source.sqlite3') as (saved,_,_):
                        if {name:row_digest(values) for name,values in rows_from(saved).items()}!=digests:fail('Backup row verification failed.')
                    (backup/'uploads').mkdir()
                    copy_manifest(source_uploads,backup/'uploads',manifest)
                    journal['state']='backup-verified';write_private(backup/'recovery.json',journal)
                    if _fault:_fault('backup')
                    stage.mkdir(mode=0o700);created=True
                    with (stage/'.migration-owner').open('x') as marker:
                        marker.write(run_id);marker.flush();os.fsync(marker.fileno())
                    sync_directory(stage)
                    copy_manifest(backup/'uploads',stage,manifest)
                    for name in TABLES:
                        if name=='categories':continue
                        values=rows[name]
                        if name=='refresh_sessions':values=[dict(row,predecessor_id=None,successor_id=None) for row in values]
                        if values:target.execute(Base.metadata.tables[name].insert(),values)
                    refresh=Base.metadata.tables['refresh_sessions']
                    for row in rows['refresh_sessions']:
                        target.execute(update(refresh).where(refresh.c.id==row['id']).values(predecessor_id=row['predecessor_id'],successor_id=row['successor_id']))
                    if {name:row_digest(values) for name,values in rows_from(target).items()}!=digests:fail('Destination row/content verification failed.')
                    target.exec_driver_sql('SET CONSTRAINTS ALL IMMEDIATE')
                    for name in SEQUENCES:
                        maximum=max(0,max((row['id'] for row in rows[name]),default=0))
                        # Restart is transactional; setval would survive rollback.
                        if maximum>=9223372036854775807:fail('Destination sequence has no safe next value.')
                        target.exec_driver_sql(f'ALTER SEQUENCE {name}_id_seq RESTART WITH {maximum+1}')
                        actual=target.execute(text("SELECT last_value,is_called FROM "+name+'_id_seq')).one()
                        if tuple(actual)!=(maximum+1,False):fail('Sequence verification failed.')
                    verify_files(source_uploads,manifest)
                    if digest_bytes(source)!=source_hash:fail('Source changed during migration.')
                    if _fault:_fault('database')
                    safe_path(destination,exists=False)
                    journal['state']='publishing-before-db-commit';write_private(backup/'recovery.json',journal)
                    safe_path(stage,exists=True)
                    stage.rename(destination);published=True;sync_directory(destination.parent)
                    verify_files(destination,manifest)
                    if _fault:_fault('published')
                    require_checkpointed_source(source)
                    commit_attempted=True
                    transaction.commit()
                    if _fault:_fault('commit-acknowledgment')
                    committed=True
                    journal['state']='committed';write_private(backup/'recovery.json',journal)
                    return dict(result,status='committed-and-verified')
                except BaseException:
                    if transaction.is_active:transaction.rollback()
                    raise
    except BaseException:
        if created and not committed and commit_attempted:
            journal['state']='commit-outcome-unknown-reconciliation-required'
            if backup and backup.exists():write_private(backup/'recovery.json',journal)
        elif created and not committed:
            try:clean_owned(destination if published else stage,journal['manifest'],run_id)
            except Exception:
                journal['state']='reconciliation-required'
            else:journal['state']='rolled-back-owned-files-cleaned'
            if backup and backup.exists():write_private(backup/'recovery.json',journal)
        raise
    finally:engine.dispose()


def verify_migration(*,backup,target_url,destination_uploads,quiesced=False):
    """Read-only reconciliation, never cleanup/resume based on a journal guess."""
    if not quiesced:fail('Offline verification confirmation is required.')
    backup=safe_path(backup,exists=True);destination=safe_path(destination_uploads)
    journal_path=safe_path(backup/'recovery.json',exists=True)
    if journal_path.stat().st_size>64*1024*1024:fail('Recovery metadata exceeds limit.')
    journal=json.loads(journal_path.read_text())
    run_id=journal['run_id']
    if not re.fullmatch('[0-9a-f]{32}',run_id) or Path(journal['destination'])!=destination:fail('Recovery ownership does not match selected destination.')
    with source_snapshot(backup/'source.sqlite3') as (source,_,_):
        rows=rows_from(source);expected={name:row_digest(values) for name,values in rows.items()}
        manifest=file_manifest(rows,backup/'uploads')
    if expected!=journal['row_digests'] or manifest!=journal['manifest']:fail('Backup verification differs from private recovery record.')
    url=make_url(target_url)
    if url.drivername not in {'postgresql','postgresql+psycopg'}:fail('Explicit PostgreSQL target is required.')
    engine=create_engine(url.set(drivername='postgresql+psycopg'),hide_parameters=True,connect_args={'connect_timeout':3,'options':'-c statement_timeout=10000'})
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            if connection.scalar(text('SELECT current_database()'))!=url.database:fail('Connected target differs from selected database.')
            validate_target_schema(connection)
            actual=rows_from(connection)
            if {name:row_digest(values) for name,values in actual.items()}==expected:
                for name in SEQUENCES:
                    maximum=max(0,max((row['id'] for row in rows[name]),default=0))
                    if tuple(connection.execute(text('SELECT last_value,is_called FROM '+name+'_id_seq')).one())!=(maximum+1,False):fail('Sequence state differs from verified migration.')
                status='committed-and-verified'
            else:
                validate_target(connection);status='target-empty'
            if destination.exists():
                marker=safe_path(destination/'.migration-owner',exists=True)
                if marker.read_text()!=run_id:fail('Destination ownership differs from recovery record.')
                verify_files(destination,manifest)
                if status=='target-empty':status='target-empty-owned-files-retained'
            elif status=='committed-and-verified':fail('Committed target needs private file reconciliation.')
            return {'status':status,'rows':{name:len(values) for name,values in actual.items()},'files':len(manifest)}
    finally:engine.dispose()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Offline backup-first SQLite to empty PostgreSQL migration')
    for name in ('source','source-uploads','destination-uploads','backup','confirm-source','confirm-target'):parser.add_argument('--'+name,required=name in {'source','source-uploads','destination-uploads'})
    parser.add_argument('--source-quiesced',action='store_true')
    modes=parser.add_mutually_exclusive_group(required=True);modes.add_argument('--dry-run',action='store_true');modes.add_argument('--execute',action='store_true');modes.add_argument('--verify',action='store_true')
    args=parser.parse_args(argv)
    try:
        target=os.environ.get('MIGRATION_TARGET_DATABASE_URL')
        if not target:fail('Set destination configuration privately in MIGRATION_TARGET_DATABASE_URL.')
        if args.verify:
            if not args.backup:fail('Select a private backup to verify.')
            result=verify_migration(backup=args.backup,target_url=target,destination_uploads=args.destination_uploads,quiesced=args.source_quiesced)
        else:
            result=migrate(source=args.source,source_uploads=args.source_uploads,destination_uploads=args.destination_uploads,backup=args.backup,target_url=target,execute=args.execute,confirm_source=args.confirm_source,confirm_target=args.confirm_target,quiesced=args.source_quiesced)
    except (Exception,KeyboardInterrupt):
        print('Migration refused or failed; source/backup are preserved. Review private recovery journal before any retry.')
        return 1
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
