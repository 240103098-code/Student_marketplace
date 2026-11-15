"""Focused ownership, transport, privacy and stop regressions; no Docker/.env."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend.config import Settings, load_settings
from tools import rehearsal101 as harness
from tools import rehearsal101_capacity as capacity


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
        (self.controller.private/'smtp').mkdir()
        for filename in ('server.key','server.pem'):(self.controller.private/'smtp'/filename).write_text('fixture')
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


if __name__=='__main__':unittest.main()
