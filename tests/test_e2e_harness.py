"""Protocol and safety regressions for the isolated E2E harness (no Docker/.env)."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from tools import e2e_stack
from tools.check_e2e_map import validate

ROOT=Path(__file__).resolve().parents[1]

class HarnessContract(unittest.TestCase):
    def test_canonical_map_has_no_fabricated_or_completed_operation(self):
        self.assertEqual(len(validate()),40)

    def test_subprocess_failures_never_disclose_native_output(self):
        with patch('tools.e2e_stack.subprocess.run',return_value=subprocess.CompletedProcess([],1,'SECRET password code token','SECRET')):
            with self.assertRaisesRegex(e2e_stack.Failure,'^subprocess-status$'):e2e_stack.run(['irrelevant'])
        with patch('tools.e2e_stack.subprocess.run',side_effect=subprocess.TimeoutExpired('SECRET',1,output='SECRET')):
            with self.assertRaisesRegex(e2e_stack.Failure,'^bounded-subprocess$'):e2e_stack.run(['irrelevant'])

    def test_reporter_drops_native_errors_and_attachment_paths(self):
        with tempfile.TemporaryDirectory(prefix='owned-reporter-',dir=ROOT) as directory:
            destination=Path(directory)/'safe.json'
            script="const R=require('./e2e/safe-reporter.cjs');const r=new R();r.onBegin({workers:1,projects:[{}]},{allTests:()=>[{},{}]});r.onTestEnd({title:'verified student smoke',errors:['SECRET']},{status:'failed',error:{message:'SECRET password code token'},attachments:[{path:'SECRET'}]});r.onEnd({status:'failed',error:'SECRET'});"
            result=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True,timeout=10,env=dict(os.environ,E2E_SAFE_REPORT=str(destination)))
            self.assertEqual(result.returncode,0)
            self.assertEqual(result.stdout+result.stderr,'')
            self.assertEqual(json.loads(destination.read_text()),{'status':'failed','tests':[{'test':'student','status':'failed'}]})

    def test_project_ownership_rejects_arbitrary_target_before_command(self):
        with patch('tools.e2e_stack.run') as run:
            with self.assertRaisesRegex(e2e_stack.Failure,'ownership'):e2e_stack.compose({},Path('/tmp'),'student-marketplace','down','--volumes')
            run.assert_not_called()

    def test_parallel_environment_refused_before_creation(self):
        with patch.dict(os.environ,{'PW_TEST_WORKERS':'2'}),patch('sys.argv',['controller']),patch('tools.e2e_stack.tempfile.mkdtemp') as create:
            with self.assertRaisesRegex(e2e_stack.Failure,'parallel'):e2e_stack.main()
            create.assert_not_called()

class ActualProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.openssl=shutil.which('openssl') or ('C:/Program Files/Git/usr/bin/openssl.exe' if Path('C:/Program Files/Git/usr/bin/openssl.exe').exists() else None)
        if not cls.openssl:raise unittest.SkipTest('OpenSSL prerequisite unavailable')

    def test_real_starttls_auth_recipient_purpose_and_ca_verification(self):
        with tempfile.TemporaryDirectory(prefix='owned-e2e-protocol-',dir=ROOT) as directory:
            root=Path(directory);(root/'mail').mkdir();(root/'smtp.json').write_text(json.dumps({'username':'fixture','password':'fixture-private-password'}))
            def openssl(*args):
                result=subprocess.run([self.openssl,*args],capture_output=True,text=True,timeout=20,env=dict(os.environ,MSYS_NO_PATHCONV='1'))
                self.assertEqual(result.returncode,0,'Certificate fixture generation failed')
            openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'server.key'),'-out',str(root/'server.pem'),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost','-addext','basicConstraints=critical,CA:TRUE')
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            process=subprocess.Popen([sys.executable,str(ROOT/'e2e/smtp_sink.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,E2E_SMTP_ROOT=str(root),E2E_SMTP_PORT=str(port),E2E_SMTP_BIND='127.0.0.1'))
            try:
                end=time.monotonic()+10
                while True:
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=.2):break
                    except OSError:
                        if time.monotonic()>end:self.fail('SMTP startup deadline')
                        time.sleep(.05)
                with smtplib.SMTP('localhost',port,timeout=3,local_hostname='fixture.local') as client:
                    client.ehlo();self.assertFalse(client.has_extn('auth'))
                    with self.assertRaises(smtplib.SMTPNotSupportedError):client.login('fixture','invalid')
                with self.assertRaises(ssl.SSLCertVerificationError):
                    with smtplib.SMTP('localhost',port,timeout=3,local_hostname='fixture.local') as client:client.starttls(context=ssl.create_default_context())
                context=ssl.create_default_context(cafile=str(root/'server.pem'))
                with smtplib.SMTP('localhost',port,timeout=3,local_hostname='fixture.local') as client:
                    client.starttls(context=context);client.ehlo()
                    with self.assertRaises(smtplib.SMTPAuthenticationError):client.login('fixture','invalid')
                    client.login('fixture','fixture-private-password')
                    with self.assertRaises(smtplib.SMTPRecipientsRefused):client.sendmail('fixture@sdu.edu.kz','external@example.com','not relayed')
                from backend.config import Settings
                from backend.mail import SmtpSender
                settings=Settings(JWT_SECRET_KEY='test-only-'+ 'x'*48,SMTP_HOST='localhost',SMTP_PORT=port,SMTP_USERNAME='fixture',SMTP_PASSWORD='fixture-private-password',SMTP_FROM_EMAIL='fixture@sdu.edu.kz',SMTP_SECURITY='starttls')
                with patch.dict(os.environ,{'SSL_CERT_FILE':str(root/'server.pem')}):SmtpSender(settings).send_code('e2e-protocol@sdu.edu.kz','123456','registration')
                message=json.loads((root/'mail/e2e-protocol@sdu.edu.kz.json').read_text())
                self.assertEqual(message,{'code':'123456','purpose':'registration','tls':True,'authenticated':True})
                self.assertEqual(len(list((root/'mail').iterdir())),1)
            finally:
                process.terminate();process.communicate(timeout=5)
