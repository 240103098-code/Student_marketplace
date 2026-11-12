"""Safe operation evidence never includes native process content or private inputs."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_checks as ci

SENTINELS=('private-password-97-example','someone-private@example.invalid',
           '/private/credential-97.key','NATIVE-SECRET-97\ninjected-operation')


class OperationDiagnostics(unittest.TestCase):
    def public(self, error):
        record={'result':'FAIL','checks':[],'cleanup':False}
        ci.capture_failure(record,'prerequisites',error)
        payload=json.dumps(record)
        for sentinel in SENTINELS:self.assertNotIn(sentinel,payload)
        return record

    def test_real_exit_captures_only_fixed_operation_class_and_actual_status(self):
        code='import os,sys;print(os.environ["PRIVATE_97"]);print(sys.argv[1],file=sys.stderr);sys.exit(37)'
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            with self.assertRaises(ci.OperationFailure) as raised:
                ci.run_operation('postgres-container-start',[sys.executable,'-c',code,SENTINELS[1]],
                                 os.environ|{'PRIVATE_97':'|'.join(SENTINELS)},timeout=10)
        record=self.public(raised.exception)
        self.assertEqual(record['failure_operation'],'postgres-container-start')
        self.assertEqual(record['failure_class'],'exit-status')
        self.assertEqual(record['failure_exit_status'],37)
        self.assertFalse(record['failure_timeout'])
        self.assertEqual(output.getvalue(),'')

    def test_real_timeout_has_no_invented_exit_status_or_native_output(self):
        with self.assertRaises(ci.OperationFailure) as raised:
            ci.run_operation('postgres-version',[sys.executable,'-c',
                'import time;print("private-password-97-example",flush=True);time.sleep(10)'],timeout=.05)
        record=self.public(raised.exception)
        self.assertEqual(record['failure_class'],'timeout')
        self.assertTrue(record['failure_timeout'])
        self.assertNotIn('failure_exit_status',record)

    def test_process_start_failure_and_hostile_exception_are_suppressed(self):
        with patch('tools.ci_checks.subprocess.run',side_effect=OSError('|'.join(SENTINELS))):
            with self.assertRaises(ci.OperationFailure) as raised:
                ci.run_operation('postgres-volume-create',['irrelevant'])
        record=self.public(raised.exception)
        self.assertEqual(record['failure_class'],'process-start')
        self.assertNotIn('failure_exit_status',record)
        self.assertFalse(record['failure_timeout'])

    def test_real_missing_executable_is_classified_without_its_path(self):
        with self.assertRaises(ci.OperationFailure) as raised:
            ci.run_operation('docker-version',['/nonexistent/private/credential-97.key'])
        self.assertEqual(self.public(raised.exception)['failure_class'],'process-start')

    def test_approved_success_and_expected_nonzero_keep_private_native_result(self):
        for status in (0,23):
            with self.subTest(status=status):
                result=ci.run_operation('postgres-readiness',[sys.executable,'-c',
                    f'import sys;print("private-password-97-example");sys.exit({status})'],okay=True,timeout=10)
                self.assertEqual(result.returncode,status)
                self.assertIn(SENTINELS[0],result.stdout)
        record={};self.assertNotIn('failure_operation',record)

    def test_missing_unknown_nonstring_and_hostile_labels_fail_before_process(self):
        for label in (None,'',SENTINELS[0],'postgres-container-start\ninjected-operation',{},42):
            with self.subTest(label=type(label).__name__),patch('tools.ci_checks.subprocess.run') as process:
                with self.assertRaises(ci.OperationFailure) as raised:
                    ci.run_operation(label,['secret-private-command'])
                process.assert_not_called()
                record=self.public(raised.exception)
                self.assertEqual(record['failure_operation'],'unapproved-operation')
                self.assertEqual(record['failure_class'],'invalid-operation')
        with patch('tools.ci_checks.subprocess.run') as process:
            with self.assertRaises(ci.OperationFailure):ci.run_operation()
            process.assert_not_called()

    def test_readiness_deadline_reports_actual_last_status_without_retry_policy_change(self):
        calls=[]
        def execute(operation,args,**kwargs):
            calls.append((operation,kwargs))
            return subprocess.CompletedProcess([],2,'|'.join(SENTINELS),'')
        with self.assertRaises(ci.OperationFailure) as raised:
            ci.await_postgres(execute,'private-container',{'POSTGRES_USER':'u','POSTGRES_DB':'d'},
                              clock=iter((0,61)).__next__,pause=lambda _:self.fail('deadline should stop'))
        record=self.public(raised.exception)
        self.assertEqual(record['failure_operation'],'postgres-readiness')
        self.assertEqual(record['failure_class'],'readiness-deadline')
        self.assertEqual(record['failure_exit_status'],2)
        self.assertTrue(record['failure_timeout'])
        self.assertEqual(calls,[('postgres-readiness',{'okay':True,'timeout':5})])

    def test_readiness_expected_failure_then_success_is_not_public_failure(self):
        statuses=iter((1,0));calls=[]
        def execute(operation,args,**kwargs):
            calls.append(operation)
            return subprocess.CompletedProcess([],next(statuses),'','')
        ci.await_postgres(execute,'c',{'POSTGRES_USER':'u','POSTGRES_DB':'d'},
                          clock=iter((0,1)).__next__,pause=lambda _:None)
        self.assertEqual(calls,['postgres-readiness']*2)

    def test_primary_failure_survives_following_cleanup_failure(self):
        record={};primary=ci.OperationFailure('postgres-container-start','exit-status',125)
        ci.capture_failure(record,'prerequisites',primary)
        ci.capture_cleanup_failure(record,ci.OperationFailure('cleanup-child-list','timeout'))
        ci.capture_failure(record,'frontend-tests',ci.OperationFailure('frontend-suite','exit-status',8))
        self.assertEqual(record['failure_operation'],'postgres-container-start')
        self.assertEqual(record['failure_exit_status'],125)
        self.assertEqual(record['failure_stage'],'prerequisites')
        self.assertEqual(record['cleanup_failures'][0]['failure_operation'],'cleanup-child-list')

    def test_unknown_exception_text_and_unapproved_stage_are_not_public(self):
        for error in (RuntimeError('|'.join(SENTINELS)),ci.Failure('|'.join(SENTINELS))):
            record={};ci.capture_failure(record,SENTINELS[0],error)
            self.assertEqual(record,{'failure_stage':'controller','failure_kind':'controller-failure'})

    def test_incidental_success_output_cannot_become_a_public_version_or_revision(self):
        for operation,pattern in (('source-revision',r'[a-f0-9]{40}'),
                                  ('docker-version',r'[0-9]+\.[0-9]+\.[0-9]+')):
            for sentinel in SENTINELS:
                with self.assertRaises(ci.OperationFailure) as raised:
                    ci.public_value(operation,sentinel,pattern)
                record=self.public(raised.exception)
                self.assertEqual(record['failure_operation'],operation)
                self.assertEqual(record['failure_class'],'invalid-result')
                self.assertEqual(record['failure_exit_status'],0)

    def test_controller_failure_attempts_owned_cleanup_without_touching_unrelated_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);unrelated=root/'preserve.txt';unrelated.write_text('untouched')
            calls=[]
            def execute(operation,args,env=None,**kwargs):
                calls.append(operation)
                if operation=='postgres-volume-create':
                    raise ci.OperationFailure(operation,'exit-status',125)
                if operation=='cleanup-child-list':
                    raise ci.OperationFailure(operation,'timeout')
                outputs={'source-revision':'a'*40,'node-version':'v24.19.0','npm-version':'12.2.0',
                         'docker-version':'28.0.4','compose-version':'2.38.2','source-inventory':''}
                status=1 if operation in ('cleanup-owned-inspect','cleanup-owned-absence') else 0
                return subprocess.CompletedProcess([],status,outputs.get(operation,''),'|'.join(SENTINELS))
            console=io.StringIO()
            with patch.object(ci,'ROOT',root),patch.object(ci,'run_operation',side_effect=execute),\
                 patch.object(ci.sys,'argv',['ci_checks']),patch.object(ci.sys,'version','3.13.15 test'),\
                 contextlib.redirect_stdout(console),contextlib.redirect_stderr(console):
                self.assertEqual(ci.main(),1)
            record=json.loads((root/'ci-safe/summary.json').read_text())
            self.assertEqual(record['failure_operation'],'postgres-volume-create')
            self.assertEqual(record['failure_exit_status'],125)
            self.assertFalse(record['cleanup']);self.assertEqual(record['result'],'FAIL')
            self.assertEqual(len(record['cleanup_failures']),3)
            self.assertIn('cleanup-owned-inspect',calls);self.assertIn('cleanup-owned-absence',calls)
            self.assertEqual(unrelated.read_text(),'untouched')
            payload=json.dumps(record)+console.getvalue()
            for sentinel in SENTINELS:self.assertNotIn(sentinel,payload)


if __name__=='__main__':unittest.main()
