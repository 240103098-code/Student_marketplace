"""CI gates fail closed; sharing never rebuilds or deletes an unowned image."""
import subprocess
import unittest
from unittest.mock import patch
from tools.ci_checks import unittest_counts,validate_counts
from tools.e2e_stack import borrowed_image,Failure

class ImplementedCIGates(unittest.TestCase):
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
