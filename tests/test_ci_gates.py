"""CI gates fail closed; sharing never rebuilds or deletes an unowned image."""
import subprocess
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import ci_checks as ci
from tools.ci_checks import unittest_counts,validate_counts
from tools.e2e_stack import borrowed_image,Failure

class ImplementedCIGates(unittest.TestCase):
    def run_modes(self,root,safe,mutate=lambda value:None):
        calls=[];candidate='a'*40;image='sha256:'+'b'*64
        record={'candidate':candidate}
        def execute(operation,args,**kwargs):
            directory=root/'e2e-safe'
            self.assertFalse(directory.exists(),'previous mode must be archived before starting a fresh child')
            directory.mkdir();calls.append(args[3:])
            intentional='--intentional-failure' in args
            selection=args[args.index('--selection')+1] if '--selection' in args else 'smoke'
            ids={'smoke':['student','admin'],'full':['student','admin','registration'],'registration':['registration']}[selection]
            if intentional:ids=['student']  # Actual maxFailures=1 lifecycle omits admin end record.
            value={'candidate':candidate,'result':'PASS','image_id':image,'borrowed_image_preserved':True,
                   'cleanup':True,'private_files_removed':True,'selection':selection,'intentional_failure':intentional,
                   'playwright_exit':1 if intentional else 0,'playwright':'fixture','browser_revision':[],
                   'tests':{'status':'failed' if intentional else 'passed','tests':[{'test':name,'status':'failed' if intentional and name=='student' else 'skipped' if intentional else 'passed'} for name in ids]}}
            mutate(value)
            (directory/'run.json').write_text(json.dumps(value))
            (directory/'tests.json').write_text(json.dumps(value['tests']))
            (directory/'student-stages.json').write_text(json.dumps({'stages':['controlled-failure-check'],'completed':['ui-register','private-smtp','ui-verify','ui-login','protected-reload','fresh-context-denied']}))
            self.assertEqual(operation,'playwright-suite');self.assertEqual(kwargs,{'okay':True,'timeout':600})
            return subprocess.CompletedProcess(args,0,'PRIVATE NATIVE OUTPUT','')
        with patch.object(ci,'ROOT',root):ci.playwright_modes(execute,safe,record,image)
        return calls,record

    def test_fixed_modes_preserve_default_smoke_and_honest_failure_with_separate_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);safe=root/'safe';safe.mkdir()
            calls,record=self.run_modes(root,safe)
            self.assertEqual(calls,[[],['--selection','full'],['--selection','registration'],['--intentional-failure']])
            self.assertEqual(len(record['playwright_modes']),4)
            self.assertEqual(record['playwright_modes'][-1]['browser_status'],'failed')
            self.assertEqual(record['playwright_modes'][-1]['browser_exit'],1)
            self.assertEqual(record['playwright_modes'][-1]['result'],'PASS')
            self.assertEqual(record['playwright_modes'][-1]['tests'],1)
            self.assertEqual(json.loads((safe/'e2e-intentional-failure-tests.json').read_text()),{'status':'failed','tests':[{'test':'student','status':'failed'}]})
            for prefix in ('e2e-smoke-','e2e-','e2e-registration-only-','e2e-intentional-failure-'):
                self.assertTrue((safe/(prefix+'run.json')).is_file())
                self.assertNotIn('PRIVATE', (safe/(prefix+'run.json')).read_text())
            self.assertFalse((root/'e2e-safe').exists())

    def test_child_identity_cleanup_selection_and_test_status_fail_closed(self):
        changes=({'candidate':'c'*40},{'image_id':'other'},{'cleanup':False},{'private_files_removed':False},
                 {'borrowed_image_preserved':False},{'selection':'full'},{'intentional_failure':True},
                 {'playwright_exit':1},{'tests':{'status':'passed','tests':[{'test':'student','status':'passed'}]}})
        for change in changes:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);safe=root/'safe';safe.mkdir()
                with self.assertRaises(Failure):self.run_modes(root,safe,lambda value:value.update(change))
                self.assertTrue((safe/'e2e-smoke-run.json').is_file(),'failed mode still retains safe diagnostics')

    def test_intentional_mode_rejects_a_successful_browser_or_wrong_failing_test(self):
        for change in ({'playwright_exit':0},{'playwright_exit':2},*({'tests':{'status':'failed','tests':rows}} for rows in (
            [{'test':'student','status':'passed'},{'test':'admin','status':'failed'}],
            [{'test':'student','status':'failed'},{'test':'admin','status':'failed'}],
            [{'test':'student','status':'failed'},{'test':'admin','status':'passed'}],
            [{'test':'student','status':'failed'},{'test':'student','status':'failed'}],
            [{'test':'student','status':'failed'},{'test':'unexpected','status':'skipped'}]))):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);safe=root/'safe';safe.mkdir()
                def mutate(value):
                    if value['intentional_failure']:value.update(change)
                with self.assertRaises(Failure):self.run_modes(root,safe,mutate)
                self.assertTrue((safe/'e2e-intentional-failure-run.json').is_file())
                self.assertTrue((safe/'e2e-registration-only-run.json').is_file())

    def test_intentional_mode_retains_an_actual_unexecuted_admin_record_when_emitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);safe=root/'safe';safe.mkdir()
            def mutate(value):
                if value['intentional_failure']:value['tests']['tests'].append({'test':'admin','status':'skipped'})
            _,record=self.run_modes(root,safe,mutate)
            self.assertEqual(record['playwright_modes'][-1]['tests'],2)
            self.assertEqual(json.loads((safe/'e2e-intentional-failure-tests.json').read_text())['tests'],[{'test':'student','status':'failed'},{'test':'admin','status':'skipped'}])

    def test_dynamic_backend_count_requires_success_and_zero_skips(self):
        counts=unittest_counts('Ran 317 tests in 12.34s\n\nOK\n')
        self.assertEqual(counts,{'discovered':317,'executed':317,'skipped':0,'failed':0,'errors':0,'passed':317});validate_counts(counts)
        for text in ('Ran 317 tests in 1s\nOK (skipped=1)\n','Ran 317 tests in 1s\nFAILED (failures=1)\n','Ran 0 tests in 1s\nOK\n'):
            with self.assertRaises(Failure):validate_counts(unittest_counts(text))
        with self.assertRaises(Failure):unittest_counts('command did not run')

    def test_borrowed_image_requires_exact_generated_tag_id_and_owner_label(self):
        owner='marketplace92-'+'a'*20;identity='sha256:'+'b'*64
        env={'MARKETPLACE_TEST_IMAGE':owner+':local','MARKETPLACE_TEST_IMAGE_ID':identity,'MARKETPLACE_TEST_IMAGE_OWNER':owner}
        with patch('tools.e2e_stack.run',return_value=subprocess.CompletedProcess([],0,identity+'|'+owner+'\n','')) as run:
            self.assertEqual(borrowed_image(env),owner+':local')
            self.assertIn('.Config.Labels',run.call_args.args[0][-1])
        with patch('tools.e2e_stack.run',return_value=subprocess.CompletedProcess([],0,identity+'|different-owner\n','')):
            with self.assertRaises(Failure):borrowed_image(env)
        for changed in ({'MARKETPLACE_TEST_IMAGE':'ordinary-image:latest'},{'MARKETPLACE_TEST_IMAGE_OWNER':'other-owner'},{'MARKETPLACE_TEST_IMAGE_ID':'not-exact'}):
            with patch('tools.e2e_stack.run') as run:
                with self.assertRaises(Failure):borrowed_image(env|changed)
                run.assert_not_called()
        self.assertIsNone(borrowed_image({}))
