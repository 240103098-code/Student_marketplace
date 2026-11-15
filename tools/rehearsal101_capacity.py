"""Capacity-only synthetic metrics, fixed-rate load, Linux counters and explicit stops."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shutil
import time
import urllib.parse

from tools.rehearsal101 import (CAPS, LABEL, PHASES, Failure, metrics, percentile,
                                port, request, require, resources)


def candidate(r):
    directory=r.private/'obs';directory.mkdir()
    endpoints={key:'http://127.0.0.1:'+str(port()) for key in ('otlp','self','prometheus','grafana')}
    collector={
        'receivers':{'otlp':{'protocols':{'http':{'endpoint':'0.0.0.0:4318','max_request_body_size':65536}}}},
        'processors':{'memory_limiter':{'check_interval':'1s','limit_mib':128,'spike_limit_mib':32},
                      'batch':{'timeout':'1s','send_batch_size':100,'send_batch_max_size':100}},
        'exporters':{'prometheusremotewrite':{
            'endpoint':'http://prometheus:9090/api/v1/write','timeout':'5s',
            'max_batch_size_bytes':65536,'max_batch_request_parallelism':1,
            'target_info':{'enabled':False},'add_metric_suffixes':False,
            'remote_write_queue':{'enabled':True,'queue_size':10,'num_consumers':1},
            'retry_on_failure':{'enabled':True,'initial_interval':'1s','max_interval':'5s','max_elapsed_time':'20s'}}},
        'service':{'telemetry':{'logs':{'level':'error'},'metrics':{
            'level':'detailed','readers':[{'pull':{'exporter':{'prometheus':{'host':'0.0.0.0','port':8888}}}}]}},
                   'pipelines':{'metrics':{'receivers':['otlp'],'processors':['memory_limiter','batch'],
                                           'exporters':['prometheusremotewrite']}}}}
    (directory/'collector.json').write_text(json.dumps(collector))
    (directory/'prometheus.json').write_text(json.dumps({'global':{'scrape_interval':'5s','scrape_timeout':'3s'},
        'scrape_configs':[{'job_name':'collector-capacity','sample_limit':2000,'label_limit':20,
                          'static_configs':[{'targets':['collector:8888']}]}]}))
    # A JSON document is valid YAML for these tools.
    provisioning=directory/'provisioning/datasources';provisioning.mkdir(parents=True)
    (provisioning/'capacity.yaml').write_text(json.dumps({'apiVersion':1,'datasources':[
        {'name':'capacity','uid':'capacity101','type':'prometheus','access':'proxy','url':'http://prometheus:9090',
         'isDefault':True,'editable':False,'jsonData':{'httpMethod':'POST','timeInterval':'1s'}}]}))
    import secrets
    grafana_password=secrets.token_hex(24)
    services={
        'collector':{'image':r.pins['collector'],'command':['--config=/config/collector.json'],
            'volumes':[str(directory/'collector.json')+':/config/collector.json:ro'],
            'ports':['127.0.0.1:'+urllib.parse.urlsplit(endpoints['otlp']).netloc.split(':')[1]+':4318',
                     '127.0.0.1:'+urllib.parse.urlsplit(endpoints['self']).netloc.split(':')[1]+':8888'],
            'read_only':True,'depends_on':['prometheus']},
        'prometheus':{'image':r.pins['prometheus'],
            'command':['--config.file=/etc/prometheus/prometheus.json','--storage.tsdb.path=/prometheus',
                       '--web.enable-remote-write-receiver','--storage.tsdb.retention.time=24h',
                       '--storage.tsdb.retention.size=512MB','--query.timeout=5s','--query.max-concurrency=2',
                       '--query.max-samples=100000','--web.max-connections=20','--log.level=error'],
            'volumes':[str(directory/'prometheus.json')+':/etc/prometheus/prometheus.json:ro','metrics:/prometheus'],
            'ports':['127.0.0.1:'+urllib.parse.urlsplit(endpoints['prometheus']).netloc.split(':')[1]+':9090']},
        'grafana':{'image':r.pins['grafana'],'environment':{
            'GF_SECURITY_ADMIN_USER':'fixture','GF_SECURITY_ADMIN_PASSWORD':grafana_password,
            'GF_AUTH_ANONYMOUS_ENABLED':'false','GF_AUTH_DISABLE_LOGIN_FORM':'false',
            'GF_USERS_ALLOW_SIGN_UP':'false','GF_ANALYTICS_REPORTING_ENABLED':'false',
            'GF_ANALYTICS_CHECK_FOR_UPDATES':'false','GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES':'false',
            'GF_NEWS_NEWS_FEED_ENABLED':'false','GF_PLUGINS_PREINSTALL_DISABLED':'true',
            'GF_PLUGINS_CHECK_FOR_UPDATES':'false','GF_LOG_LEVEL':'error',
            'GF_SERVER_ENABLE_GZIP':'true'},
            'volumes':['grafana:/var/lib/grafana',str(directory/'provisioning')+':/etc/grafana/provisioning:ro'],
            'ports':['127.0.0.1:'+urllib.parse.urlsplit(endpoints['grafana']).netloc.split(':')[1]+':3000']}}
    for service,config in services.items():
        config.update(resources(service,r.owner));config.update(cap_drop=['ALL'],security_opt=['no-new-privileges:true'])
    stack={'project':r.owner+'-obs','compose':directory/'compose.json','name':'obs','directory':directory,
           'config':{'services':services,'volumes':{v:{'labels':{LABEL:r.owner}} for v in ('metrics','grafana')},
                     'networks':{'default':{'internal':True,'labels':{LABEL:r.owner}}}},
           'endpoints':endpoints,'auth':'Basic '+base64.b64encode(('fixture:'+grafana_password).encode()).decode()}
    r.save(stack);r.projects.append(stack)
    r.record['candidate_configuration']={'queue_capacity_requests':10,'queue_sizer':'requests (version factory source)',
        'retry_max_seconds':20,'batch_points':100,'collector_limit_mib':128,
        'retention_hours':24,'retained_block_limit_bytes':512000000,
        'WAL_head_reserve_bytes':512*1024*1024,'minimum_projection_fixed_reserve_bytes':1024*1024*1024,
        'notes':'Block retention is asynchronous; WAL/head add disk. Projections are not a retention soak or quota proof.',
        'endpoints':'loopback-only control/generator ports; internal Docker network; no DB publication or external export',
        'components':'otlp/http, memory_limiter, batch, prometheusremotewrite; metrics only'}
    return stack


def query(obs,expression):
    status,_,body=request(obs['endpoints']['prometheus'],'/api/v1/query?'+urllib.parse.urlencode({'query':expression,'timeout':'4s'}))
    require(status==200,'prometheus-query')
    value=json.loads(body)
    require(value['status']=='success','prometheus-query-result')
    return value['data']['result']


def scalar(obs,expression):
    values=query(obs,expression)
    return sum(float(v['value'][1]) for v in values)


def grafana(obs):
    data={'queries':[{'refId':'A','datasource':{'type':'prometheus','uid':'capacity101'},
                     'expr':'sum(rehearsal_capacity_value)','instant':True,'range':False}],
          'from':str(int((time.time()-60)*1000)),'to':str(int(time.time()*1000))}
    status,_,body=request(obs['endpoints']['grafana'],'/api/ds/query',method='POST',
                         body=json.dumps(data).encode(),headers={'Authorization':obs['auth'],'Content-Type':'application/json'})
    require(status==200,'grafana-authenticated-query')
    value=json.loads(body)
    frames=value.get('results',{}).get('A',{}).get('frames',[])
    require(frames and any(frame.get('data',{}).get('values') for frame in frames),'grafana-query-values')
    return 1


def otlp(obs):
    now=str(time.time_ns())
    points=[{'attributes':[{'key':'series','value':{'intValue':str(n)}}],
             'timeUnixNano':now,'asDouble':float(n+1)} for n in range(100)]
    body=json.dumps({'resourceMetrics':[{'resource':{'attributes':[
        {'key':'service.name','value':{'stringValue':'capacity-generator'}}]},
        'scopeMetrics':[{'scope':{'name':'capacity101'},'metrics':[
            {'name':'rehearsal_capacity_value','gauge':{'dataPoints':points}}]}]}]}).encode()
    status,_,response=request(obs['endpoints']['otlp'],'/v1/metrics',method='POST',body=body,headers={'Content-Type':'application/json'})
    require(status==200,'otlp-receiver-status')
    rejected=int(json.loads(response or b'{}').get('partialSuccess',{}).get('rejectedDataPoints',0))
    return 100-rejected


def bytes_value(text):
    match=re.fullmatch(r'([0-9.]+)\s*([KMGTPE]?i?B)',text.strip())
    require(match is not None,'docker-stats-unit')
    units={'B':1,'kB':1000,'KB':1000,'MB':1000**2,'GB':1000**3,'TB':1000**4,
           'KiB':1024,'MiB':1024**2,'GiB':1024**3,'TiB':1024**4}
    return float(match[1])*units[match[2]]


def disk(r,obs):
    values={}
    for service,path in [('prometheus','/prometheus'),('grafana','/var/lib/grafana')]:
        result=r.compose(obs,'exec','-T',service,'du','-sk',path,timeout=8)
        values[service+'_bytes']=int(result.stdout.split()[0])*1024
    for name in ('wal','chunks_head'):
        result=r.compose(obs,'exec','-T','prometheus','du','-sk','/prometheus/'+name,timeout=8,okay=True)
        values[name+'_bytes']=int(result.stdout.split()[0])*1024 if result.returncode==0 else 0
    return values


def host_cpu():
    fields=[int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
    return sum(fields),fields[3]+fields[4]


class Sampler:
    def __init__(self,r,stacks):
        self.r=r;self.stacks=stacks;self.previous_cpu=host_cpu();self.bad={};self.expected_outage=False

    def sustained(self,key,bad,seconds=30):
        now=time.monotonic()
        if not bad:self.bad.pop(key,None)
        elif key not in self.bad:self.bad[key]=now
        elif now-self.bad[key]>=seconds:raise Failure(key)

    def sample(self,phase,elapsed,obs=None):
        r=self.r
        ids=[]
        for stack in self.stacks:ids+=r.compose(stack,'ps','-q','--status','running').stdout.split()
        if obs:ids+=r.compose(obs,'ps','-q','--status','running').stdout.split()
        require(bool(ids),'sampler-no-containers')
        stats=r.run(['docker','stats','--no-stream','--format','{{json .}}',*ids],timeout=8)
        inspected=json.loads(r.run(['docker','inspect',*ids],timeout=8).stdout)
        byname={c['Name'].lstrip('/'):c for c in inspected}
        row={'phase':phase,'elapsed_seconds':round(elapsed,3),'timestamp_unix':time.time(),
             'services':{},'aggregate_cpu_percent':0,'aggregate_memory_bytes':0}
        for line in stats.stdout.splitlines():
            value=json.loads(line);info=byname[value['Name']]
            service=info['Config']['Labels']['com.docker.compose.service']
            project=info['Config']['Labels']['com.docker.compose.project']
            name=('obs' if project.endswith('-obs') else 'dev' if project.endswith('-dev') else 'prod')+'/'+service
            used=bytes_value(value['MemUsage'].split('/')[0]);cpu=float(value['CPUPerc'].rstrip('%'))
            require(not info['State'].get('OOMKilled') and info['RestartCount']==0,'service-oom-or-restart')
            self.sustained('memory-stop-'+name,used>CAPS[service][1]*1024**2*.85)
            row['services'][name]={'cpu_percent':cpu,'memory_bytes':used,'memory_cap_bytes':CAPS[service][1]*1024**2}
            row['aggregate_cpu_percent']+=cpu;row['aggregate_memory_bytes']+=used
        self.sustained('aggregate-cpu-stop',row['aggregate_cpu_percent']>os.cpu_count()*100*.8)
        free=shutil.disk_usage(r.private)
        require(free.free>=max(4*1024**3,free.total*.2),'disk-stop')
        row['disk_free_bytes']=free.free
        current=host_cpu();total=current[0]-self.previous_cpu[0];idle=current[1]-self.previous_cpu[1]
        row['runner_cpu_percent']=100*os.cpu_count()*(1-idle/total) if total else 0
        self.previous_cpu=current
        memory=Path('/proc/meminfo').read_text()
        row['runner_used_memory_bytes']=(int(re.search(r'MemTotal:\s+(\d+)',memory)[1])-int(re.search(r'MemAvailable:\s+(\d+)',memory)[1]))*1024
        row['runner_load1']=os.getloadavg()[0]
        for stack in self.stacks:
            try:healthy=request(stack['origin'],'/health/ready',context=r.context)[0]==200
            except Exception:healthy=False
            self.sustained(stack['name']+'-unhealthy-over-30s',not healthy)
            row[stack['name']+'_ready']=healthy
        if obs:
            status,_,body=request(obs['endpoints']['self'],'/metrics')
            require(status==200,'collector-self-metrics')
            allmetrics=metrics(body.decode())
            # Explicit safe numeric catalog, with version-defined queue instrumentation required.
            row['collector']={k:v for k,v in allmetrics.items() if any(s in k for s in (
                'queue_size','queue_capacity','accepted_metric_points','refused_metric_points',
                'sent_metric_points','send_failed_metric_points','enqueue_failed_metric_points',
                'prometheusremotewrite_sent_batches','prometheusremotewrite_failed_translations'))}
            queue=sum(v for k,v in row['collector'].items() if k.endswith('queue_size'))
            cap=sum(v for k,v in row['collector'].items() if k.endswith('queue_capacity'))
            require(cap==10 and 0<=queue<=cap,'collector-queue-bound')
            row['queue_requests']=queue;row['queue_capacity_requests']=cap
            if phase!='outage':row['storage']=disk(r,obs)
        r.record['samples'].append(row)
        return row


def normal_login(r,stack):
    status,_,body=r.api(stack,'/auth/login',method='POST',value={'email':stack['email'],'password':stack['password']})
    require(status==200,'phase-normal-login')
    stack['token']=json.loads(body)['access_token']


def load_read(r,stack,n):
    start=time.monotonic()
    try:status=r.api(stack,'/users/me' if n%2==0 else '/users/me/avatar',token=stack['token'])[0]
    except Exception:status=0
    return status, time.monotonic()-start


def phase(r,sampler,stacks,name,seconds,obs):
    active=name in ('load','outage','recovery')
    for stack in stacks:normal_login(r,stack)
    pools={s['name']:ThreadPoolExecutor(max_workers=4) for s in stacks}
    metric_pool=ThreadPoolExecutor(max_workers=1)
    futures={s['name']:[] for s in stacks};metric_futures=[];grafana_futures=[]
    results={s['name']:{'offered':0,'scheduled':0,'scheduler_rejected':0,'completed':0,'errors':0,'latency_seconds':[]} for s in stacks}
    started=time.monotonic();next_read=next_metric=next_grafana=next_sample=started
    start_wall=time.time();max_sample_gap=0;last_sample=started
    start_storage=disk(r,obs) if obs and name!='outage' else None
    try:
        while time.monotonic()-started<seconds:
            now=time.monotonic()
            require(now<r.deadline,'phase-outer-deadline')
            if active and now>=next_read:
                for stack in stacks:
                    res=results[stack['name']];res['offered']+=1
                    pending=sum(not f.done() for f in futures[stack['name']])
                    if pending<4:
                        futures[stack['name']].append(pools[stack['name']].submit(load_read,r,stack,res['offered']))
                        res['scheduled']+=1
                    else:res['scheduler_rejected']+=1
                next_read+=.5
            if active and now>=next_metric:
                # Never substitute an unbounded executor queue for the fixed offered rate.
                if not any(f is not None and not f.done() for f in metric_futures[-2:]):metric_futures.append(metric_pool.submit(otlp,obs))
                else:metric_futures.append(None)
                next_metric+=1
            if active and now>=next_grafana:
                # During the deliberate outage datasource errors are expected and counted.
                grafana_futures.append(metric_pool.submit(grafana,obs))
                next_grafana+=10
            if now>=next_sample:
                gap=now-last_sample;max_sample_gap=max(max_sample_gap,gap)
                require(gap<=5.5,'sampler-cadence-deadline')
                sampler.sample(name,now-started,obs)
                last_sample=now;next_sample+=5
            time.sleep(.02)
        duration=time.monotonic()-started
        for stack in stacks:
            res=results[stack['name']]
            for f in futures[stack['name']]:
                status,latency=f.result(timeout=10)
                res['completed']+=int(status==200);res['errors']+=int(status!=200)
                res['latency_seconds'].append(latency)
            latencies=res.pop('latency_seconds')
            res.update(achieved_success_per_second=res['completed']/duration,
                       latency_p95_seconds=percentile(latencies),latency_peak_seconds=max(latencies,default=0))
        accepted=errors=0
        for future in metric_futures:
            if future is None:errors+=100;continue
            try:accepted+=future.result(timeout=10)
            except Exception:errors+=100
        gpassed=gerrors=0
        for f in grafana_futures:
            try:gpassed+=f.result(timeout=10)
            except Exception:gerrors+=1
        samples=[s for s in r.record['samples'] if s['phase']==name]
        output={'duration_seconds':duration,'start_unix':start_wall,'end_unix':time.time(),'sample_count':len(samples),
                'max_sample_gap_seconds':max_sample_gap,'app_reads':results,
                'otlp_offered_points':len(metric_futures)*100,'otlp_accepted_points':accepted,'otlp_failed_or_unscheduled_points':errors,
                'grafana_query_success':gpassed,'grafana_query_errors':gerrors,
                'storage_start':start_storage,'storage_end':disk(r,obs) if obs and name!='outage' else None}
        for key in ('aggregate_cpu_percent','aggregate_memory_bytes','runner_cpu_percent','runner_used_memory_bytes'):
            values=[s[key] for s in samples]
            output[key]={'peak':max(values,default=0),'p95':percentile(values),'count':len(values)}
        if obs and name!='outage':
            # Raw samples over exact phase window, not a scrape-count proxy for 100 OTLP points/s.
            expression='sum(count_over_time(rehearsal_capacity_value['+str(int(duration))+'s]))'
            output['query_visible_synthetic_samples']=scalar(obs,expression)
            output['query_visible_series']=scalar(obs,'count(rehearsal_capacity_value)')
            # TSDB ingestion counters are read from Prometheus /metrics directly, never assumed scraped.
            status,_,raw=request(obs['endpoints']['prometheus'],'/metrics')
            require(status==200,'prometheus-self-metrics')
            match=re.search(rb'^prometheus_tsdb_head_samples_appended_total\s+([0-9.eE+\-]+)',raw,re.M)
            output['prometheus_tsdb_samples_appended_total']=float(match[1]) if match else None
        r.record['phases'][name]=output
        if active:
            target=seconds*2
            coverage=all(v['completed']>=target*.98 and v['errors']==0 and v['scheduler_rejected']==0 for v in results.values())
            r.check(name+'-fixed-app-target',coverage)
            # During storage outage receiver rejection/drop is a measured controlled outcome.
            if name!='outage':r.check(name+'-otlp-offered-target',len(metric_futures)>=seconds*.98 and accepted>=seconds*100*.98)
            if name=='load':
                r.check('load-query-visible-series',output['query_visible_series']==100)
                r.check('load-stored-sample-target',output['query_visible_synthetic_samples']>=seconds*100*.95)
                r.check('load-grafana-query-target',gpassed>=seconds/10*.95 and gerrors==0)
        return output
    finally:
        for pool in pools.values():pool.shutdown(wait=True,cancel_futures=True)
        metric_pool.shutdown(wait=True,cancel_futures=True)


def projection(r):
    phases=r.record['phases'];loaded=phases['load'];baseline=phases['baseline'];idle=phases['idle']
    begin=loaded['storage_start'];end=loaded['storage_end'];duration=loaded['duration_seconds']
    growth=max(0,sum(end[k]-begin[k] for k in ('prometheus_bytes','grafana_bytes')))
    rate=growth/duration
    # Include fixed reserve even when short-run WAL allocation masks amortized growth.
    fixed=1024**3
    hour=rate*3600;day=rate*86400
    sample_bytes=growth/max(1,loaded['query_visible_synthetic_samples'])
    samples=r.record['samples']
    steady=[s for s in samples if s['phase']=='load']
    peak_memory=max(s['aggregate_memory_bytes'] for s in steady)
    peak_cpu=max(s['aggregate_cpu_percent'] for s in steady)
    r.record['projection']={
        'observed_growth_bytes':growth,'observed_bytes_per_query_visible_sample':sample_bytes,
        'growth_bytes_per_hour':hour,'growth_bytes_per_day':day,
        'conservative_24h_bytes':fixed+day*2,'conservative_7d_unretained_bytes':fixed+day*7*2,
        'retained_24h_blocks_cap_bytes':512000000,'retention_excludes_WAL_head':True,
        'fixed_WAL_compaction_grafana_reserve_bytes':fixed,'growth_safety_factor':2,
        'baseline_to_idle_memory_p95_delta':idle['aggregate_memory_bytes']['p95']-baseline['aggregate_memory_bytes']['p95'],
        'baseline_to_load_cpu_p95_delta':loaded['aggregate_cpu_percent']['p95']-baseline['aggregate_cpu_percent']['p95'],
        'baseline_to_load_memory_p95_delta':loaded['aggregate_memory_bytes']['p95']-baseline['aggregate_memory_bytes']['p95'],
        'oracle_hypothetical_total_memory_bytes':6*1024**3,'oracle_reserved_memory_bytes':int(1.5*1024**3),
        'oracle_remaining_memory_bytes':int(4.5*1024**3),'local_loaded_peak_memory_bytes':peak_memory,
        'local_measured_memory_with_50pct_margin_fits_hypothetical_remainder':peak_memory*1.5<int(4.5*1024**3),
        'local_loaded_peak_logical_cpu_percent':peak_cpu,'oracle_reserved_cpu_percent':20,
        'oracle_usable_cpu_percent':80,'architecture_equivalence':'unproven; no linear x64-vCPU to ARM-OCPU conversion',
        'startup_budget_mib':{'both_apps_dbs':2*(256+384),'two_migrations_upload_init':2*(256+64),
                             'two_proxies_sinks':2*(96+96),'metrics_stack':192+384+256,
                             'OS_Docker_proxy_transients_reserve':1536,'logs_backup_disk':'separate 1GiB logs + aligned backup + >=4GiB/20% free reserve'},
        'interpretation':'Short run, fixed offered rate; WAL allocation/compaction noise makes linear growth uncertain. '
          'No trace/log storage or application SDK overhead measured. Hosted activation blocked; #103 platform-specific retest required.'}


def capacity(r,dev,prod):
    stacks=(dev,prod)
    sampler=Sampler(r,stacks)
    phase(r,sampler,stacks,'baseline',120,None)
    obs=candidate(r)
    r.compose(obs,'up','-d',timeout=90)
    end=time.monotonic()+90
    while time.monotonic()<end:
        try:
            if request(obs['endpoints']['grafana'],'/api/health')[0]==200 and request(obs['endpoints']['prometheus'],'/-/ready')[0]==200:break
        except Exception:pass
        time.sleep(1)
    else:raise Failure('candidate-readiness')
    r.check('grafana-anonymous-denied',request(obs['endpoints']['grafana'],'/api/datasources')[0]==401)
    phase(r,sampler,stacks,'idle',120,obs)
    phase(r,sampler,stacks,'load',300,obs)
    r.compose(obs,'stop','--timeout','5','prometheus')
    sampler.expected_outage=True
    phase(r,sampler,stacks,'outage',60,obs)
    outage_samples=[s for s in r.record['samples'] if s['phase']=='outage']
    r.check('outage-queue-growth',max(s['queue_requests'] for s in outage_samples)>0)
    r.compose(obs,'start','prometheus')
    recovery_start=time.monotonic()
    recovery=phase(r,sampler,stacks,'recovery',120,obs)
    r.check('recovery-query-visible-ingestion',recovery['query_visible_synthetic_samples']>0)
    # Time of first sampled recovery proof, not total measurement phase runtime.
    resumed=[s for s in r.record['samples'] if s['phase']=='recovery' and s['queue_requests']==0]
    r.record['recovery_seconds_upper_bound']=resumed[0]['elapsed_seconds'] if resumed else 121
    r.check('recovery-within-120s',r.record['recovery_seconds_upper_bound']<=120)
    latest=[s for s in r.record['samples'] if s['phase']=='recovery'][-1]
    r.check('recovery-queue-drained',latest['queue_requests']==0)
    r.record['controlled_export_loss']={k:v for k,v in latest['collector'].items() if 'failed' in k or 'refused' in k}
    projection(r)
