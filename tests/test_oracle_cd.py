"""Policy/rollback regressions; these never access cloud hosts or real credentials."""
import copy
import contextlib
import io
import json
import os
import stat
from pathlib import Path
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import oracle_cd as cd
from tools import oracle_cd_request as client

SOURCE='a'*40
PREVIOUS='b'*40
IMAGE='sha256:'+'c'*64
OLD_IMAGE='sha256:'+'d'*64


def trusted():
    run={'id':123,'run_attempt':2,'workflow_id':456,'event':'push','head_branch':'main',
         'head_sha':SOURCE,'path':cd.WORKFLOW,'repository':{'full_name':cd.REPOSITORY},
         'head_repository':{'full_name':cd.REPOSITORY},'status':'in_progress','conclusion':None}
    jobs=[{'name':name,'status':'completed','conclusion':'success','head_sha':SOURCE,
           'run_id':123,'run_attempt':2} for name in cd.REQUIRED]
    return run,jobs


def environment():
    return {'GITHUB_REPOSITORY':cd.REPOSITORY,'GITHUB_EVENT_NAME':'push',
            'GITHUB_REF':'refs/heads/main','IMPLEMENTED_RESULT':'success','GATE_RESULT':'success',
            'GITHUB_SHA':SOURCE,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'2'}


class Policy(unittest.TestCase):
    def test_exact_request_rejects_shell_payload_whitespace_truncation_and_huge_identifiers(self):
        self.assertEqual(cd.request(f'deploy {SOURCE} 123 2'),(SOURCE,123,2))
        for value in ('',f'deploy {SOURCE} 123 2\n',f'deploy {SOURCE} 123 2;id',
                      f'deploy {SOURCE.upper()} 123 2',f'deploy {SOURCE} 0 2',
                      f'deploy {SOURCE} 123 0',f'deploy {SOURCE} '+'9'*16+' 2',
                      f'deploy {SOURCE} 123 2\x00',f'deploy {SOURCE[:39]} 123 2'):
            with self.subTest(value=value[-10:]),self.assertRaises(cd.Rejected):cd.request(value)

    def test_runner_requires_canonical_push_main_both_success_and_exact_sha(self):
        self.assertEqual(cd.runner_gate(environment()),(SOURCE,123,2))
        changes={'GITHUB_REPOSITORY':['fork/repo',''], 'GITHUB_EVENT_NAME':['pull_request','workflow_dispatch','workflow_run'],
                 'GITHUB_REF':['refs/tags/main','refs/heads/other','refs/pull/1/merge'],
                 'IMPLEMENTED_RESULT':['failure','cancelled','skipped',''],
                 'GATE_RESULT':['failure','cancelled','skipped',''], 'GITHUB_SHA':['',SOURCE[:39],SOURCE+'0']}
        for key,values in changes.items():
            for value in values:
                with self.subTest(key=key,value=value),self.assertRaises(cd.Rejected):
                    cd.runner_gate(environment()|{key:value})

    def test_server_run_checks_every_trust_field(self):
        run,jobs=trusted();cd.validate_run(run,jobs,SOURCE,123,2,456)
        changes={'id':9,'run_attempt':1,'workflow_id':1,'event':'pull_request','head_branch':'other',
                 'head_sha':PREVIOUS,'path':'unknown.yml','repository':{'full_name':'wrong/repo'},
                 'head_repository':{'full_name':'fork/repo'},'status':'queued','conclusion':'failure'}
        for key,value in changes.items():
            with self.subTest(key=key),self.assertRaises(cd.Rejected):
                cd.validate_run(run|{key:value},jobs,SOURCE,123,2,456)
        with self.assertRaises(cd.Rejected):cd.validate_run(run,jobs,SOURCE,123,2,None)

    def test_required_jobs_missing_duplicate_failed_skipped_stale_or_wrong_attempt_are_denied(self):
        run,jobs=trusted()
        variants=[[],jobs[:1],jobs+[jobs[0]]]
        for field,value in (('status','queued'),('conclusion','failure'),('conclusion','skipped'),
                            ('conclusion','cancelled'),('head_sha',PREVIOUS),('run_id',999),('run_attempt',1)):
            changed=copy.deepcopy(jobs);changed[0][field]=value;variants.append(changed)
        for changed in variants:
            with self.subTest(jobs=len(changed)),self.assertRaises(cd.Rejected):
                cd.validate_run(run,changed,SOURCE,123,2,456)

    def test_incoherent_workflow_status_conclusion_pairs_fail_closed(self):
        run,jobs=trusted()
        for status,conclusion in (('completed',None),('in_progress','success'),('queued',None)):
            with self.subTest(status=status,conclusion=conclusion),self.assertRaises(cd.Rejected):
                cd.validate_run(run|{'status':status,'conclusion':conclusion},jobs,SOURCE,123,2,456)

    def test_bounded_stdin_and_trailing_payload_are_rejected_before_host_work(self):
        for payload in (b'x'*257,(f'deploy {SOURCE} 123 2\nid').encode()):
            stream=io.StringIO()
            with patch.object(cd.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(payload))),\
                 patch.object(cd.sys,'argv',['controller']),patch.object(cd,'installed') as installed,\
                 contextlib.redirect_stdout(stream):self.assertEqual(cd.main(),1)
            installed.assert_not_called();self.assertEqual(json.loads(stream.getvalue())['result'],'FAIL')

    def test_installed_controller_checks_nested_parents_and_fixed_backup_compose_wrapper(self):
        seen=[]
        def validate(path,**kwargs):
            seen.append(path)
            if path==cd.ROOT/'compose.sh':raise cd.Rejected('unsafe-installed-path')
        with patch.object(cd.os,'geteuid',return_value=0,create=True),patch.object(cd,'protected',side_effect=validate):
            with self.assertRaises(cd.Rejected):cd.installed()
        self.assertIn(cd.ROOT/'template/ops',seen);self.assertIn(cd.ROOT/'template/ops/oracle',seen)
        self.assertIn(cd.ROOT/'compose.sh',seen)

    def test_attempt_specific_job_pagination_and_installed_workflow_id(self):
        run,jobs=trusted();seen=[]
        def api(path):
            seen.append(path)
            if path=='actions/workflows/implemented-ci.yml':return {'id':456,'path':cd.WORKFLOW,'state':'active'}
            if path=='actions/runs/123/attempts/2':return run
            if path.endswith('page=1'):return {'total_count':2,'jobs':jobs[:1]}
            if path.endswith('page=2'):return {'total_count':2,'jobs':jobs[1:]}
            self.fail(path)
        with patch.object(cd,'public_json',side_effect=api):cd.github_gate(SOURCE,123,2,456)
        self.assertEqual(len(seen),4)
        with patch.object(cd,'public_json',side_effect=api),self.assertRaises(cd.Rejected):
            cd.github_gate(SOURCE,123,2,999)

    def test_stale_nonforward_and_idempotent_release_order(self):
        self.assertIsNone(cd.check_order(SOURCE,SOURCE,PREVIOUS,lambda old,new:True))
        with self.assertRaises(cd.Rejected):cd.check_order(SOURCE,PREVIOUS,PREVIOUS,lambda *_:True)
        with self.assertRaises(cd.Rejected):cd.check_order(SOURCE,SOURCE,PREVIOUS,lambda *_:False)
        self.assertIsNone(cd.check_order(SOURCE,SOURCE,SOURCE,lambda *_:self.fail('idempotent not ancestry change')))

    def archive(self,name,kind=tarfile.REGTYPE):
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w') as archive:
            member=tarfile.TarInfo(name);member.type=kind;member.mode=0o644
            if kind==tarfile.REGTYPE:member.size=4
            if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE):member.linkname='/etc/passwd'
            archive.addfile(member,io.BytesIO(b'safe') if kind==tarfile.REGTYPE else None)
        return output.getvalue()

    def test_real_archive_regular_source_extracts_but_links_devices_and_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);destination=root/'source';destination.mkdir()
            cd.extract_source(self.archive('backend/code.py'),destination)
            self.assertEqual((destination/'backend/code.py').read_bytes(),b'safe')
            for name,kind in (('../escape',tarfile.REGTYPE),('/absolute',tarfile.REGTYPE),
                              ('x\\escape',tarfile.REGTYPE),('C:/escape',tarfile.REGTYPE),
                              ('link',tarfile.SYMTYPE),('hard',tarfile.LNKTYPE),('device',tarfile.CHRTYPE)):
                with self.subTest(name=name),self.assertRaises(cd.Rejected):
                    cd.extract_source(self.archive(name,kind),destination)
            self.assertFalse((root/'escape').exists())

    def test_migration_change_is_rejected_before_any_runtime_action(self):
        with tempfile.TemporaryDirectory() as directory:
            roots=[Path(directory)/name for name in ('old','new')]
            for root in roots:
                for name in ('migrations','migrations_sqlite'):
                    (root/name).mkdir(parents=True);(root/name/'revision.py').write_text('same')
                for name in ('alembic.ini','alembic-sqlite.ini'):(root/name).write_text('same')
            cd.compatible_migrations(roots[1],roots[0])
            (roots[1]/'migrations/revision.py').write_text('new schema')
            with self.assertRaises(cd.Rejected):cd.compatible_migrations(roots[1],roots[0])

    def test_failed_release_retry_verifies_every_source_file_and_rejects_extra_or_changed_files(self):
        payload=self.archive('backend/code.py')
        with tempfile.TemporaryDirectory() as directory:
            release=Path(directory)/SOURCE
            cd.prepare_release(payload,release,SOURCE)
            with patch.object(cd,'protected'),patch.object(cd,'protected_source'):
                cd.prepare_release(payload,release,SOURCE)
                (release/'backend/code.py').write_text('modified')
                with self.assertRaises(cd.Rejected):cd.prepare_release(payload,release,SOURCE)
                (release/'backend/code.py').write_bytes(b'safe')
                (release/'unreviewed').write_text('not in archive')
                with self.assertRaises(cd.Rejected):cd.prepare_release(payload,release,SOURCE)

    def test_private_umask_normalizes_all_source_directories_and_allows_verified_retry(self):
        # Actual POSIX modes are checked on Linux CI; Windows does not emulate
        # those permission bits. Both platforms still execute extraction/retry.
        payload=self.archive('backend/nested/code.py')
        with tempfile.TemporaryDirectory() as directory:
            release=Path(directory)/SOURCE
            previous=os.umask(0o077)
            try:
                cd.prepare_release(payload,release,SOURCE)
                def validate_source(path,mode):
                    if os.name=='posix':self.assertEqual(stat.S_IMODE(path.lstat().st_mode),mode)
                with patch.object(cd,'protected'),patch.object(cd,'protected_source',side_effect=validate_source):
                    cd.prepare_release(payload,release,SOURCE)
            finally:os.umask(previous)
            self.assertEqual((release/'backend/nested/code.py').read_bytes(),b'safe')
            if os.name=='posix':
                self.assertEqual(stat.S_IMODE(release.stat().st_mode),0o700)
                for path in (release/'backend',release/'backend/nested'):
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o755)
                self.assertEqual(stat.S_IMODE((release/'backend/nested/code.py').stat().st_mode),0o644)
    def test_retry_source_mode_or_owner_change_is_rejected(self):
        from unittest.mock import Mock
        path=Mock();path.is_symlink.return_value=False
        for uid,mode in ((1000,0o100644),(0,0o100755),(0,0o100666)):
            path.lstat.return_value=SimpleNamespace(st_uid=uid,st_mode=mode)
            with self.assertRaises(cd.Rejected):cd.protected_source(path,0o644)
        path.lstat.return_value=SimpleNamespace(st_uid=0,st_mode=0o100644)
        cd.protected_source(path,0o644)

    def test_atomic_private_and_image_selection_preserve_all_other_configuration(self):
        original='JWT_SECRET_KEY=PRIVATE-SENTINEL\nMARKETPLACE_IMAGE='+OLD_IMAGE+'\nDATABASE_URL=PRIVATE-DB\n'
        value=cd.replace_image(original,IMAGE)
        self.assertEqual(value.replace(IMAGE,OLD_IMAGE),original)
        with self.assertRaises(cd.Rejected):cd.replace_image(original,'evil\nJWT_SECRET_KEY=changed')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';other=Path(directory)/'unrelated';other.write_text('keep')
            cd.atomic_json(path,{'sha':SOURCE});self.assertEqual(json.loads(path.read_text()),{'sha':SOURCE})
            self.assertEqual(other.read_text(),'keep');self.assertEqual(len(list(Path(directory).iterdir())),2)

    def test_workflow_has_same_chain_guard_environment_and_serialization(self):
        text=(Path(__file__).resolve().parents[1]/'.github/workflows/implemented-ci.yml').read_text()
        deploy=text.split('  deploy-oracle-demo:\n',1)[1]
        for required in ('needs: [implemented, gate]',"github.repository == '"+cd.REPOSITORY+"'",
                         "github.event_name == 'push'", "github.ref == 'refs/heads/main'",
                         "needs.implemented.result == 'success'", "needs.gate.result == 'success'",
                         'environment: oracle-demo','cancel-in-progress: false','ref: ${{ github.sha }}',
                         'persist-credentials: false','run: python -m tools.oracle_cd_request'):
            self.assertIn(required,deploy)
        self.assertNotIn('continue-on-error',deploy);self.assertNotIn('workflow_run',deploy)


class Transaction(unittest.TestCase):
    def adapter(self,fail=None,recovery_fail=False):
        class Adapter:
            def __init__(self):self.calls=[];self.image=OLD_IMAGE
            def action(self,name):
                self.calls.append((name,self.image))
                if name==fail and self.image==IMAGE:raise RuntimeError('PRIVATE-FAILURE')
                if recovery_fail and name=='start' and self.image==OLD_IMAGE:raise RuntimeError('PRIVATE-RECOVERY')
            def backup(self):self.action('backup')
            def select(self,image):self.image=image;self.action('select')
            def migrate(self):self.action('migrate')
            def start(self):self.action('start')
            def verify(self):self.action('verify')
        return Adapter()

    def test_success_keeps_candidate_only_after_backup_migration_start_health(self):
        adapter=self.adapter();cd.activate(adapter,IMAGE,OLD_IMAGE)
        self.assertEqual([name for name,_ in adapter.calls],['backup','select','migrate','start','verify'])
        self.assertEqual(adapter.image,IMAGE)

    def test_migration_start_or_health_failure_restores_previous_and_still_fails(self):
        for step in ('migrate','start','verify'):
            adapter=self.adapter(step)
            with self.subTest(step=step),self.assertRaisesRegex(cd.Rejected,'^activation-failed-rollback-restored$'):
                cd.activate(adapter,IMAGE,OLD_IMAGE)
            self.assertEqual(adapter.image,OLD_IMAGE)
            self.assertEqual(adapter.calls[-3:],[('select',OLD_IMAGE),('start',OLD_IMAGE),('verify',OLD_IMAGE)])

    def test_backup_partial_failure_also_attempts_recovery(self):
        adapter=self.adapter()
        def fail():raise RuntimeError('private dump path')
        adapter.backup=fail
        with self.assertRaisesRegex(cd.Rejected,'^activation-failed-rollback-restored$'):
            cd.activate(adapter,IMAGE,OLD_IMAGE)
        self.assertEqual(adapter.calls,[('select',OLD_IMAGE),('start',OLD_IMAGE),('verify',OLD_IMAGE)])

    def test_failed_rollback_has_distinct_failure_not_false_success(self):
        adapter=self.adapter('verify',recovery_fail=True)
        with self.assertRaisesRegex(cd.Rejected,'^activation-failed-rollback-failed$'):
            cd.activate(adapter,IMAGE,OLD_IMAGE)

    def test_obsolete_recovery_nonce_never_selects_or_starts_any_release(self):
        generation='123-2-'+SOURCE
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'pending.json').write_text(json.dumps({'generation':'999-1-'+PREVIOUS}))
            with patch.object(cd,'ROOT',root),patch.object(cd,'installed'),patch.object(cd,'protected'),\
                 patch.object(cd,'deployment_lock',contextlib.nullcontext),patch.object(cd,'Host') as host:
                self.assertEqual(cd.recover_generation(generation),{'result':'obsolete-recovery'})
                host.assert_not_called()

    def test_committed_release_fallback_verifies_retention_without_rolling_back(self):
        generation='123-2-'+SOURCE
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'pending.json').write_text(json.dumps({'generation':generation,'candidate':SOURCE}))
            (root/'state.json').write_text(json.dumps({'sha':SOURCE,'image':IMAGE}))
            (root/'pending-retained.json').write_bytes(b'private-retained-hashes')
            with patch.object(cd,'ROOT',root),patch.object(cd,'installed'),patch.object(cd,'protected'),\
                 patch.object(cd,'deployment_lock',contextlib.nullcontext),patch.object(cd,'Host') as host,\
                 patch.object(cd,'disarm_recovery') as disarm:
                self.assertEqual(cd.recover_generation(generation)['result'],'committed-release-preserved')
                host.return_value.verify.assert_called_once();host.return_value.select.assert_not_called()
                self.assertEqual(host.return_value.snapshot,b'private-retained-hashes')
                disarm.assert_called_once_with(generation)

    def test_state_write_failure_restores_previous_and_reports_failed_commit(self):
        for failed_recovery in (False,True):
            adapter=self.adapter(recovery_fail=failed_recovery)
            with patch.object(cd,'atomic_json',side_effect=OSError('PRIVATE-STATE-PATH')):
                expected='state-write-failed-rollback-'+('failed' if failed_recovery else 'restored')
                with self.assertRaisesRegex(cd.Rejected,'^'+expected+'$'):
                    cd.commit_release(adapter,{'image':OLD_IMAGE},{'sha':SOURCE,'image':IMAGE})
            self.assertEqual(adapter.image,OLD_IMAGE)

    def test_one_shot_real_pause_command_is_owned_nonce_bound_and_consumed_before_pause(self):
        generation='123-2-'+SOURCE;identifier='e'*64
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);marker=root/'health-drill.json'
            marker.write_text(json.dumps({'sha':SOURCE,'generation':generation}))
            host=cd.Host.__new__(cd.Host);host.state={'image':OLD_IMAGE}
            host.expected_image=IMAGE;host.allowed_images={IMAGE,OLD_IMAGE}
            host.generation=generation;host.candidate_sha=SOURCE
            host.compose=lambda *args,**kwargs:subprocess.CompletedProcess([],0,identifier.encode() if args[0]=='ps' else b'',b'')
            paused=[False];calls=[]
            def execute(args,**kwargs):
                calls.append(args)
                if args[:2]==['docker','inspect']:
                    value=[{'Image':IMAGE,'State':{'Paused':paused[0]},'Config':{'Labels':{
                        'com.docker.compose.project':cd.PROJECT,'com.docker.compose.service':'app'}}}]
                    return subprocess.CompletedProcess([],0,json.dumps(value).encode(),b'')
                if args[:2]==['docker','pause']:
                    self.assertFalse(marker.exists())
                    self.assertTrue((root/('health-drill-consumed-'+generation+'.json')).exists())
                    paused[0]=True
                if args[:2]==['docker','unpause']:paused[0]=False
                return subprocess.CompletedProcess([],0,b'',b'')
            with patch.object(cd,'ROOT',root),patch.object(cd,'protected'),patch.object(cd,'execute',side_effect=execute):
                host.start();self.assertTrue(paused[0]);self.assertIn(['docker','pause',identifier],calls)
                host.expected_image=OLD_IMAGE
                host.start();self.assertFalse(paused[0]);self.assertIn(['docker','unpause',identifier],calls)
                self.assertEqual(sum(args[:2]==['docker','pause'] for args in calls),1)

    def test_mismatched_marker_cannot_pause_a_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'health-drill.json').write_text(json.dumps({'sha':PREVIOUS,'generation':'wrong'}))
            with patch.object(cd,'ROOT',root),patch.object(cd,'protected'),self.assertRaises(cd.Rejected):
                cd.validate_drill_marker(SOURCE,'123-2-'+SOURCE)


class Client(unittest.TestCase):
    def test_wrong_branch_and_missing_access_fail_before_any_ssh_or_file_creation(self):
        for env in (environment()|{'GITHUB_REF':'refs/heads/other'},environment()):
            stream=io.StringIO()
            with patch.dict(os.environ,env,clear=True),patch.object(client.subprocess,'run') as process,\
                 patch.object(client.tempfile,'mkdtemp') as temporary,contextlib.redirect_stdout(stream):
                self.assertEqual(client.main(),1)
            process.assert_not_called();temporary.assert_not_called()

    def test_host_key_mismatch_and_untrusted_response_never_publish_native_diagnostics(self):
        env=environment()|{'ORACLE_DEMO_HOST':'example.invalid',
              'ORACLE_DEMO_DEPLOY_KEY':'-----BEGIN OPENSSH PRIVATE KEY-----\nPRIVATE-KEY-SENTINEL',
              'ORACLE_DEMO_KNOWN_HOSTS':'example.invalid ssh-ed25519 AAAASYNTHETIC'}
        for result in (subprocess.CompletedProcess([],255,b'PRIVATE-STDOUT',b'PRIVATE-STDERR'),
                       subprocess.CompletedProcess([],0,json.dumps({'result':'deployed','sha':PREVIOUS}).encode(),b'')):
            stream=io.StringIO()
            with patch.dict(os.environ,env,clear=True),patch.object(client.subprocess,'run',return_value=result) as process,\
                 contextlib.redirect_stdout(stream):self.assertEqual(client.main(),1)
            args=process.call_args.args[0]
            self.assertIn('StrictHostKeyChecking=yes',args);self.assertIn('ClearAllForwardings=yes',args)
            self.assertNotIn('PRIVATE',stream.getvalue());self.assertNotIn('PRIVATE-KEY-SENTINEL',' '.join(args))


if __name__=='__main__':unittest.main()
