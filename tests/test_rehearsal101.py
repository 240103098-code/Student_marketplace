"""Focused ownership, transport, privacy and stop regressions; no Docker/.env."""
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import ssl
import socket
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

from backend.config import Settings, load_settings
from tools import rehearsal101 as harness
from tools import rehearsal101_capacity as capacity
from ops.rehearsal101.proxy import Handler as FixtureRelay


class RehearsalSafety(unittest.TestCase):
    def setUp(self):
        self.controller=harness.Rehearsal()

    def tearDown(self):
        shutil.rmtree(self.controller.private)

    def test_wrong_label_refuses_project_deletion_before_compose_down(self):
        stack={'project':self.controller.owner+'-dev'}
        calls=[]
        def run(args,**kw):
            calls.append(args)
            value=({'Config':{'Labels':{'com.docker.compose.project':stack['project'],harness.LABEL:'foreign'}}})
            stdout=json.dumps([value]) if args[1:3]==['container','inspect'] else 'synthetic-container'
            return subprocess.CompletedProcess(args,0,stdout,'')
        with patch.object(self.controller,'run',side_effect=run),patch.object(self.controller,'compose') as compose:
            with self.assertRaisesRegex(harness.Failure,'cleanup-ownership'):
                self.controller.cleanup_project(stack,True)
            compose.assert_not_called()

    def test_cross_project_argument_is_rejected_without_subprocess(self):
        with patch.object(self.controller,'run') as run:
            with self.assertRaisesRegex(harness.Failure,'project-ownership'):
                self.controller.compose({'project':'unrelated-live-project'},'down','--volumes')
            run.assert_not_called()

    def test_stack_is_production_validated_and_never_reads_ambient_secrets(self):
        # Create fixture files only; stack generation must not inspect an ambient .env.
        for name in ('dev','prod'):
            (self.controller.private/(name+'-smtp')).mkdir()
            for filename in ('server.key','server.pem'):(self.controller.private/(name+'-smtp')/filename).write_text('fixture')
        with patch.dict(os.environ,{'DATABASE_URL':'PRIVATE-LIVE','JWT_SECRET_KEY':'PRIVATE-LIVE'},clear=False):
            dev=self.controller.stack('dev');prod=self.controller.stack('prod')
        for name in ('POSTGRES_DB','POSTGRES_USER','POSTGRES_PASSWORD','JWT_SECRET_KEY','SMTP_PASSWORD','FRONTEND_ORIGINS'):
            self.assertNotEqual(dev['environment'][name],prod['environment'][name])
        production={k:v for k,v in prod['environment'].items() if k in {field.alias for field in Settings.model_fields.values()}}
        settings=load_settings(environ=production,env_file=None)
        self.assertEqual(settings.app_env,'production')
        self.assertTrue(settings.refresh_cookie_secure)
        for stack in (dev,prod):
            self.assertNotIn('PRIVATE-LIVE',json.dumps(stack['config']))
            self.assertTrue(stack['config']['networks']['default']['internal'])
            self.assertNotIn('ports',stack['config']['services']['db'])
            self.assertFalse(any(v.get('external') for v in stack['config']['volumes'].values()))
            self.assertEqual(stack['config']['services']['app']['depends_on']['migrate']['condition'],'service_completed_successfully')
            self.assertEqual(stack['config']['services']['proxy']['user'],self.controller.fixture_user)
            self.assertEqual(stack['config']['services']['proxy']['cap_drop'],['ALL'])
            self.assertIn(str(self.controller.private/(stack['name']+'-web'))+':/tls:ro',stack['config']['services']['proxy']['volumes'])
            self.assertNotIn(str(self.controller.private/'ca.key'),json.dumps(stack['config']))

    def test_proxy_diagnostics_keep_only_owned_state_and_permission_metadata(self):
        web=self.controller.private/'dev-web';web.mkdir()
        (web/'server.key').write_text('PRIVATE KEY')
        stack={'project':self.controller.owner+'-dev','name':'dev'}
        info={'Config':{'Labels':{harness.LABEL:self.controller.owner,'com.docker.compose.project':stack['project']},
                        'Env':['PRIVATE TOKEN']},'State':{'Running':False,'ExitCode':1,'OOMKilled':False},
              'Mounts':[{'Source':'PRIVATE PATH'}],'NetworkSettings':{'Ports':{'8443/tcp':[{'HostIp':'127.0.0.1','HostPort':'12345'}]}}}
        with patch.object(self.controller,'compose',return_value=subprocess.CompletedProcess([],0,'owned-container','')),\
             patch.object(self.controller,'run',return_value=subprocess.CompletedProcess([],0,json.dumps([info]),'')):
            self.controller.proxy_diagnostics(stack,'connection-refused')
        value=self.controller.record['https_fixture_diagnostics']['dev']
        self.assertEqual(value['containers'],[{'running':False,'exit_code':1,'oom_killed':False,'process_uid_gid':''}])
        self.assertNotIn('PRIVATE',json.dumps(value))
        self.assertTrue(value['loopback_published'])

    def test_native_errors_and_timeout_never_reveal_output(self):
        for side in (subprocess.CompletedProcess([],1,'PRIVATE SECRET','PRIVATE TOKEN'),subprocess.TimeoutExpired('PRIVATE',1,output='PRIVATE')):
            with patch('tools.rehearsal101.subprocess.run',side_effect=side if isinstance(side,Exception) else None,
                       return_value=side),contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(harness.Failure) as error:harness.bounded(['irrelevant'])
                self.assertNotIn('PRIVATE',str(error.exception))
                self.assertEqual(output.getvalue(),'')

    def test_self_metric_parser_drops_labels_and_unrelated_payload(self):
        parsed=harness.metrics('# private\notelcol_exporter_queue_size{exporter="fixture",secret="PRIVATE"} 3\n'
                               'otelcol_exporter_queue_size{exporter="second"} 2\nuntrusted_payload{private="secret"} 8\n')
        self.assertEqual(parsed,{'otelcol_exporter_queue_size':5})
        self.assertNotIn('PRIVATE',json.dumps(parsed))

    def test_candidate_has_real_bounded_queue_and_no_external_export(self):
        self.controller.pins=json.loads((harness.ROOT/'ops/rehearsal101/images.json').read_text())
        obs=capacity.candidate(self.controller)
        config=json.loads((obs['directory']/'collector.json').read_text())
        exporter=config['exporters']['prometheusremotewrite']
        self.assertEqual(exporter['remote_write_queue']['queue_size'],10)
        self.assertEqual(exporter['endpoint'],'http://prometheus:9090/api/v1/write')
        self.assertNotIn('sending_queue',exporter)
        self.assertEqual(set(config['service']['pipelines']),{'metrics'})
        grafana=obs['config']['services']['grafana']['environment']
        self.assertEqual(grafana['GF_AUTH_ANONYMOUS_ENABLED'],'false')
        self.assertEqual(grafana['GF_ANALYTICS_REPORTING_ENABLED'],'false')
        self.assertTrue(obs['config']['networks']['default']['internal'])
        for service in ('collector','prometheus','grafana'):
            self.assertNotIn('ports',obs['config']['services'][service])
            self.assertNotIn('networks',obs['config']['services'][service])
        control=obs['config']['services']['control']
        self.assertEqual(control['networks'],['default','ingress'])
        self.assertTrue(all(p.startswith('127.0.0.1:') for p in control['ports']))
        self.assertEqual(control['command'],['python','/proxy.py','--capacity-control'])

    def test_stop_duration_cannot_reset_under_continuous_overload(self):
        sampler=capacity.Sampler(self.controller,()) if os.name!='nt' else capacity.Sampler.__new__(capacity.Sampler)
        sampler.bad={}
        with patch('tools.rehearsal101_capacity.time.monotonic',side_effect=[0,20,31]):
            sampler.sustained('cpu-stop',True)
            sampler.sustained('cpu-stop',True)
            with self.assertRaisesRegex(harness.Failure,'cpu-stop'):sampler.sustained('cpu-stop',True)

    def test_otlp_generator_is_100_bounded_series_and_reports_partial_rejection(self):
        captured={}
        def request(origin,path,**kw):
            captured.update(json.loads(kw['body']))
            return 200,{},b'{"partialSuccess":{"rejectedDataPoints":"7"}}'
        with patch('tools.rehearsal101_capacity.request',side_effect=request):
            self.assertEqual(capacity.otlp({'endpoints':{'otlp':'http://127.0.0.1:1'}}),93)
        points=captured['resourceMetrics'][0]['scopeMetrics'][0]['metrics'][0]['gauge']['dataPoints']
        self.assertEqual(len(points),100)
        self.assertEqual({p['attributes'][0]['value']['intValue'] for p in points},{str(n) for n in range(100)})

    def test_grafana_proof_requires_actual_expected_measurement_not_timestamp(self):
        obs={'endpoints':{'grafana':'http://127.0.0.1:1'},'auth':'synthetic'}
        for value,accepted in ((None,False),(float('inf'),False),(42,False),(5050,True)):
            frame={'schema':{'fields':[{'type':'time'},{'type':'number'}]},
                   'data':{'values':[[1900000000000],[value]]}}
            body=json.dumps({'results':{'A':{'frames':[frame]}}}).encode()
            with self.subTest(value=value),patch('tools.rehearsal101_capacity.request',return_value=(200,{},body)):
                if accepted:self.assertEqual(capacity.grafana(obs),1)
                else:
                    with self.assertRaisesRegex(harness.Failure,'grafana-query-values'):capacity.grafana(obs)

    def test_slow_sampler_does_not_pause_fixed_rate_workload(self):
        controller=self.controller
        class SlowSampler:
            def sample(self,name,elapsed,obs):
                time.sleep(.8)
                controller.record['samples'].append({'phase':name,'services':{},'aggregate_cpu_percent':0,
                    'aggregate_memory_bytes':0,'runner_cpu_percent':0,'runner_used_memory_bytes':0})
        stacks=({'name':'dev'},{'name':'prod'})
        with patch('tools.rehearsal101_capacity.normal_login'),\
             patch('tools.rehearsal101_capacity.app_disk',return_value={}),\
             patch('tools.rehearsal101_capacity.load_read',return_value=(200,.001)),\
             patch('tools.rehearsal101_capacity.otlp',return_value=100),\
             patch('tools.rehearsal101_capacity.grafana',return_value=1):
            result=capacity.phase(controller,SlowSampler(),stacks,'recovery',1.1,None)
        self.assertLess(result['app_tick_lateness_peak_seconds'],.25)
        self.assertEqual(result['app_reads']['dev']['completed'],3)
        self.assertEqual(result['app_reads']['prod']['completed'],3)

    def test_slow_otlp_has_one_admitted_future_and_records_skipped_offers(self):
        controller=self.controller
        class FastSampler:
            def sample(self,name,elapsed,obs):
                controller.record['samples'].append({'phase':name,'services':{},'aggregate_cpu_percent':0,
                    'aggregate_memory_bytes':0,'runner_cpu_percent':0,'runner_used_memory_bytes':0})
        calls=[]
        def slow_otlp(obs):
            calls.append(time.monotonic())
            time.sleep(4)
            return 100
        with patch('tools.rehearsal101_capacity.normal_login'),\
             patch('tools.rehearsal101_capacity.app_disk',return_value={}),\
             patch('tools.rehearsal101_capacity.load_read',return_value=(200,.001)),\
             patch('tools.rehearsal101_capacity.otlp',side_effect=slow_otlp),\
             patch('tools.rehearsal101_capacity.grafana',return_value=1):
            result=capacity.phase(controller,FastSampler(),({'name':'dev'},{'name':'prod'}),'outage',3.1,None)
        self.assertEqual(len(calls),1)
        self.assertEqual(result['otlp_offered_points'],400)
        self.assertEqual(result['otlp_accepted_points'],100)
        self.assertEqual(result['otlp_failed_or_unscheduled_points'],300)
        self.assertGreater(result['otlp_offer_interval_seconds']['min'],.75)

    def test_missed_offer_fails_before_catchup_and_records_unoffered_slots(self):
        with self.assertRaisesRegex(harness.Failure,'fixed-scheduler-missed-tick'):
            capacity.tick_delay(self.controller,'load','app',3,1,.5)
        self.assertEqual(self.controller.record['scheduler_failure']['unoffered_due_slots'],5)

    def test_app_disk_reports_numeric_pg_wal_subset_without_paths_or_doublecount(self):
        results=[subprocess.CompletedProcess([],0,'100 /PRIVATE/PGDATA\n20 /PRIVATE/WAL\n',''),
                 subprocess.CompletedProcess([],0,'4096\n','')]
        with patch.object(self.controller,'compose',side_effect=results):
            result=capacity.app_disk(self.controller,{'name':'dev'})
        self.assertEqual(result,{'pgdata_bytes_including_wal':102400,'pg_wal_bytes_subset':20480,
                                 'uploads_allocated_bytes':4096})
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_fixture_relay_cannot_select_upstream_from_request_authority(self):
        calls=[]
        class Destination(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                calls.append(self.server.server_port)
                self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'ok')
        target=ThreadingHTTPServer(('127.0.0.1',0),Destination)
        forbidden=ThreadingHTTPServer(('127.0.0.1',0),Destination)
        relay=ThreadingHTTPServer(('127.0.0.1',0),type('TestFixedRelay',(FixtureRelay,),{'upstream':target.server_address}))
        servers=(target,forbidden,relay)
        for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            connection=http.client.HTTPConnection(*relay.server_address,timeout=3)
            connection.request('GET','http://127.0.0.1:'+str(forbidden.server_port)+'/different-authority',
                               headers={'Host':'127.0.0.1:'+str(forbidden.server_port)})
            response=connection.getresponse()
            self.assertEqual((response.status,response.read()),(200,b'ok'))
            connection.close()
            self.assertEqual(calls,[target.server_port])
        finally:
            for server in servers:server.shutdown();server.server_close()

    def test_generated_fixture_chain_passes_strict_tls_and_rejects_other_host(self):
        executable=shutil.which('openssl')
        if executable is None:
            fallback=Path('C:/Program Files/Git/usr/bin/openssl.exe')
            if fallback.is_file():executable=str(fallback)
        self.assertIsNotNone(executable,'OpenSSL is required for the rehearsal fixture regression')
        native=self.controller.run
        def run(args,**kwargs):return native([executable,*args[1:]] if args[0]=='openssl' else args,**kwargs)
        with patch.object(self.controller,'run',side_effect=run):self.controller.certificates()
        self.assertTrue(self.controller.context.verify_flags & ssl.VERIFY_X509_STRICT)
        server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        web=self.controller.private/'dev-web'
        server_context.load_cert_chain(web/'server.pem',web/'server.key')
        for hostname,accepted in (('dev.marketplace.test',True),('prod.marketplace.test',False)):
            with socket.socket() as listener:
                listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(5)
                def serve():
                    raw,_=listener.accept()
                    try:
                        with server_context.wrap_socket(raw,server_side=True) as connection:connection.sendall(b'ok')
                    except (ssl.SSLError,ConnectionResetError):raw.close()
                worker=threading.Thread(target=serve);worker.start()
                try:
                    with socket.create_connection(listener.getsockname(),timeout=5) as raw:
                        if accepted:
                            with self.controller.context.wrap_socket(raw,server_hostname=hostname) as connection:
                                self.assertEqual(connection.recv(2),b'ok')
                        else:
                            with self.assertRaises(ssl.SSLCertVerificationError) as rejected:
                                self.controller.context.wrap_socket(raw,server_hostname=hostname)
                            self.assertEqual(rejected.exception.verify_code,62)
                finally:worker.join(timeout=5)
                self.assertFalse(worker.is_alive())


if __name__=='__main__':unittest.main()
