"""One prospective8M/8M window with the validated independent owned capture.

No action by default. All policy/runtime inputs remain fixed. Exactly one first
durable eligible endpoint may launch one capture and one independent watcher.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021'
OUT=P/'window-original01'
UNIT='robotron-profile06-production-next8M-window-original01-20261021.service'
TIMER=UNIT.removesuffix('.service')+'.timer'
HORIZON=8_000_000
DEPENDENCY_SHA=dict(
    linux='3c0a54a589e6790865b1dcecc1a0bf6e1f662b204155c7bf767a1d8b579f7de2',
    guard='f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
    raw_API='9e2fd74571e39065efef8492637ad3011d671b83e2bcf4134ba8a1a4212cc9b0',
    counter='11380275b544eb7196d33d92b1fbe28a1ae057404120419a2cfa447410c7e430',
    controller='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14',
    archive_checker='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')


def require(value,message):
    if not value:raise ValueError(message)


def load(entry,name):
    require(hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256'],'Selected module changed')
    spec=importlib.util.spec_from_file_location(name,entry['path']);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def require_unused_capture_paths(plan):
    paths=[P/'capture-original01',P/'capture-rescue-original01',P/'capture-job-original01.json',
        P/'capture-controller-execution-original01',P/'capture-rescue-controller-execution-original01',
        P/'capture-controller-config-original01.json',P/'rescue-controller-config-original01.json',
        G/'models_dqn/managed-checkpoints'/(plan['capture_tag']+'.pt')]
    require(not any(path.exists() for path in paths),'Original capture tag/output already consumed')


def validate_plan(plan):
    require(plan['schema']=='profile06-production-next8M-fixed-window-plan-v1' and plan['authorized'] is True,
        'One explicit fixed window plan required')
    require(plan['output']==str(OUT) and plan['unit']==UNIT and plan['timer']==TIMER
        and plan['job_path']==str(P/'window-job.json'),'Original window scope differs')
    require(plan['owner']['pid']==3295795 and plan['owner']['starttime_ticks']==64995335
        and plan['owner']['invocation_id']=='160d2b4b1f6e4e2f8839790658a7d01c','Current main owner differs')
    require(plan['reference']['sha256']=='c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'
        and plan['source_package']['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e',
        'Fixed protected policy or evaluated runtime differs')
    require(plan['capture_source']['sha256']=='b967caf7f2be7ac577f472330d38ab5120fc7f79f6742b99cb1082ef9ee54341'
        and plan['design']['sha256']=='bdb43d83e65b81722ed4b5c3369752cb4570290df6c39248d6aba251b6ca5c90',
        'Selected validated capture or prospective design differs')
    require(plan['horizons']==dict(learner_frames=8_000_000,accepted_dqn_epsilon=8_000_000)
        and plan['cutoff_s']==5400 and plan['observer_runtime_s']==5700,'Window bounds changed')
    require(plan['capture_tag']=='profile06_LR25_next8M_01_20261021','Original capture tag differs')
    require(set(plan['dependencies'])==set(DEPENDENCY_SHA)
        and all(plan['dependencies'][k]['sha256']==v for k,v in DEPENDENCY_SHA.items()),'Original observer dependencies changed')
    require(plan['pause_source']['sha256']=='0756488a19bf653a068aec8c9d3def26605b06498718621e9dc9a8a634f37b3c'
        and plan['capture_CPU']['sha256']=='967890e348a9e83090377e0bf2d78dbf2587ed27ad380e47368508dc43998a9e'
        and plan['capture_kernel']['sha256']=='17ce2fe63a9d4a3bbac5b3c70dd74afaf87a87e3cc1576b6cd57b755d333f8b8',
        'Original successful capture validation changed')


def progress(current, baseline, previous):
    for kind in ('optimizer_identity','replay_identity'):
        require(current[kind]==baseline[kind], 'Exposure process/instance/epoch changed')
    for group in ('clocks','optimizer','optimizer_since_epoch','categories'):
        require(all(current[group][key]>=previous[group][key] for key in previous[group]),
                'Counter regressed: '+group)
    require(current['optimizer']['unavailable']==0, 'Unclassified optimizer outcome')
    frames=current['clocks']['learner_frame_count']-baseline['clocks']['learner_frame_count']
    accepted=current['learner_accepted']-baseline['learner_accepted']
    require(accepted>=0, 'Learner accepted count regressed')
    return dict(learner_frames=frames,learner_accepted=accepted,
        applied_updates=current['optimizer']['applied']-baseline['optimizer']['applied'],
        amp_skips=current['optimizer']['amp_skipped']-baseline['optimizer']['amp_skipped'],
        logical_samples=current['clocks']['optimized_samples']-baseline['clocks']['optimized_samples'],
        both_horizons=frames>=HORIZON and accepted>=HORIZON)


class Context:
    def __init__(self,plan):
        validate_plan(plan);self.plan=plan;d=plan['dependencies']
        self.l=load(d['linux'],'_window_linux');self.guard=load(d['guard'],'_window_main_guard')
        self.raw=load(d['raw_API'],'_window_raw_API');self.counter=load(d['counter'],'_window_exposure_counter')
        self.capture=load(plan['capture_source'],'_window_owned_capture')
        self.control=load(d['controller'],'_window_original_control')
        self.runtime=load(d['archive_checker'],'_window_archive_checker');self.reader=self.runtime.protector()
        for entry in [*d.values(),plan['observer_source'],plan['launcher_source'],plan['capture_source'],plan['design'],
            plan['binding'],plan['source_package'],plan['pause_source'],plan['capture_CPU'],plan['capture_kernel'],plan['window_CPU'],
            plan['boot_CPU'],plan['resume_phase_record'],plan['predecessor_final_review'],plan['predecessor_adoption']]:
            self.l.checked(entry)

    def authority(self):
        p=self.plan;l=self.l;read=self.reader.read_pin
        design=json.loads(l.checked(p['design']))
        require(design['current_main_binding']==p['binding'] and design['current_main_owner']==p['owner']
            and design['protected_reference']==p['reference'] and design['source_package']==p['source_package']
            and design['counter_module']==p['dependencies']['counter'],
            'Prospective design identity differs')
        require(l.full_pin(p['reference']['path'])==p['reference'],'Protected reference changed')
        package=read(p['source_package']);root=Path(package['root'])
        require(root==G/'tools/quality_capacity_proposal/profile06/Robotron'
            and package['source_count']==len(package['files'])==123,'Original evaluated runtime package scope differs')
        for relative,digest in package['files'].items():
            source=l.full_pin(root/relative)
            require(source['sha256']==digest and source['identity']['mode']=='0o444','Original evaluated runtime source changed')
        capture_proof=read(p['capture_kernel']);CPU=read(p['capture_CPU'])
        require(capture_proof['status']=='ACTUAL_REVISED_CAPTURE_CPU23_KERNEL_TWO_CASES_ALL42_AND_RELEASE_PASS'
            and capture_proof['all42_original_descriptors_and_exact_releases_verified'] is True
            and capture_proof['selected_capture_source']==p['capture_source']
            and capture_proof['original_CPU23']==p['capture_CPU'] and capture_proof['emergency_cleanup_used'] is False
            and CPU['actual_tests']==23 and CPU['actual_exit']==0,'Actual original capture validation differs')
        proof=read(p['window_CPU']);report=read(proof['CPU_report'])
        require(proof['status']=='ACTUAL_ORIGINAL_WINDOW_FLOW_CPU_ALL6_AND_RELEASE_PASS'
            and report['status']=='PASS' and report['tests']>=18
            and report['failures']==report['errors']==report['skipped']==0
            and proof['tested_sources']['observer']==p['observer_source']
            and proof['tested_sources']['launcher']==p['launcher_source']
            and proof['tested_sources']['capture']==p['capture_source'],'Original window source contracts required')
        closure=read(proof['original_closure']);owner=read(proof['original_owner'])
        fields=self.runtime.archived_closure(closure,owner,lambda e,as_json=True:read(e,as_json=as_json),exit_zero=True)
        require(self.runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
            and fields['MemorySwapMax']=='0' and self.runtime.duration_seconds(fields['RuntimeMaxUSec'])==180
            and fields['TasksMax']=='128' and fields['SendSIGKILL']==fields['Restart']=='no','Original window CPU resource proof differs')
        binding=read(p['binding']);require(binding['owner']==p['owner'],'Original main binding differs')
        boot=read(p['boot_CPU']);phase=read(p['resume_phase_record'])
        require(boot['status']=='PASS' and boot['phase_metadata_verified'] is True
            and boot['sha256']==p['boot_checkpoint']['sha256'] and phase['checkpoint']==p['boot_checkpoint']
            and phase['action']=='resume','Actual current boot/resume lineage differs')
        require_unused_capture_paths(p)
        self.l.live_owner(p['owner']);self.guard.owner_and_files(binding)
        state=json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())
        predecessor=state['last_closed_quality_job'];review=read(p['predecessor_final_review'])
        require(state['optimization_goal']['current_main_binding']==p['binding']
            and state['optimization_goal']['current_fixed_reference_policy']['policy']==p['reference']
            and predecessor['state']=='CLOSED_QUALIFIED_PROTECTED_ADOPTED' and predecessor['quality_qualified'] is True
            and predecessor['protected_winner']==p['reference'] and predecessor['source_package']==p['source_package']
            and predecessor['original_final_review']==p['predecessor_final_review']
            and predecessor['canonical_adoption']==p['predecessor_adoption']
            and predecessor['all4_original_process_lifecycles_verified'] is True
            and predecessor['candidates_pooled_for_qualification'] is False
            and review['status']=='VALID_CLOSED_FOUR_LEG_QUALITY32_REVIEW' and review['valid'] is review['quality_qualified'] is True
            and state['active_quality_job']['phase']=='complete','Current closed predecessor/reference differs')
        return binding

    def api(self):
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
            wire=response.read(self.raw.MAX_WIRE_BYTES+1)
        return wire,self.raw.parse_wire(wire)

    def CPU_config(self,role,job_pin):
        p=self.plan
        require(role in ('capture','rescue'),'Unknown original capture role')
        capture_job=json.loads(self.l.checked(job_pin));flag='--capture' if role=='capture' else '--watch'
        unit=capture_job['controller_unit' if role=='capture' else 'rescue_unit']
        output=P/('capture-controller-execution-original01' if role=='capture' else 'capture-rescue-controller-execution-original01')
        argv=['/usr/bin/python3.12','-I','-B',p['capture_source']['path'],flag,'--job',job_pin['path'],
            '--expected-job-sha256',job_pin['sha256']]
        inputs=[job_pin,p['capture_source'],p['dependencies']['linux'],p['dependencies']['guard'],p['dependencies']['counter'],
            p['pause_source'],p['design'],p['capture_CPU'],p['capture_kernel']]
        return dict(unit=unit,output=str(output),argv=argv,properties=['CPUQuota=200%','MemoryMax=4G','RuntimeMaxSec=180',
            'MemorySwapMax=0','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
            pins=[self.control.pin(e['path']) for e in inputs],observation_s=240)

    def start_capture_role(self,role,config_pin):
        command=['/usr/bin/python3.12','-I','-B',self.plan['dependencies']['controller']['path'],'--execute',
            '--config',config_pin['path'],'--expected-source-sha256',self.plan['dependencies']['controller']['sha256']]
        with (OUT/(role+'-lifecycle-stdout.txt')).open('xb') as stdout,(OUT/(role+'-lifecycle-stderr.txt')).open('xb') as stderr:
            return subprocess.Popen(command,stdout=stdout,stderr=stderr)

    def capture_at_endpoint(self,job,latch,trigger_API):
        p=self.plan;l=self.l;prefix='robotron-profile06-candidate-save-original01-20261021'
        path=P/'capture-job-original01.json'
        capture_job=dict(schema='robotron-one-owned-candidate-save-v1',mode='production',
            case='profile06-candidate-save-original01-20261021',owner=p['owner'],model_dir=str(G/'models_dqn'),
            capture_output=str(P/'capture-original01'),rescue_output=str(P/'capture-rescue-original01'),tag=p['capture_tag'],
            controller_unit=prefix+'-capture.service',rescue_unit=prefix+'-rescue.service',job_path=str(path),
            controller_argv_prefix=['/usr/bin/python3.12','-I','-B',p['capture_source']['path'],'--capture','--job',str(path),
                '--expected-job-sha256'],controller_source=p['capture_source'],source=p['capture_source'],
            linux=p['dependencies']['linux'],pause_source=p['pause_source'],design=p['design'],main_binding=p['binding'],
            main_guard=p['dependencies']['guard'],counter_module=p['dependencies']['counter'],
            baseline_API=job['baseline_API'],trigger_API=trigger_API,latch=latch)
        self.capture.validate_scope(capture_job);capture_pin=l.publish(path,capture_job)
        configs={role:l.publish(P/(role+'-controller-config-original01.json'),self.CPU_config(role,capture_pin))
            for role in ('capture','rescue')}
        for entry in configs.values():self.control.checked_config(entry['path'])
        self.capture.mutable_state(OUT/'status.json',dict(state='capture_inflight',both_horizons=True,
            observed_unix_s=time.time(),latch=latch,capture_job=capture_pin,configs=configs))
        children={'rescue':self.start_capture_role('rescue',configs['rescue'])}
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if (P/'capture-rescue-original01/ready.json').exists():break
            require(children['rescue'].poll() is None,'Original rescue carrier exited before readiness')
            time.sleep(.03)
        else:raise RuntimeError('Original rescue readiness pending; no retry')
        ready=json.loads((P/'capture-rescue-original01/ready.json').read_bytes())
        require(ready['job_sha256']==capture_pin['sha256'],'Original rescue is foreign');l.live_owner(ready['owner'])
        children['capture']=self.start_capture_role('capture',configs['capture'])
        deadline=time.monotonic()+260
        while time.monotonic()<deadline and any(child.poll() is None for child in children.values()):time.sleep(.05)
        require(all(child.poll() is not None for child in children.values()),
            'Same original capture/watch handles remain pending; never relaunch')
        exits={role:child.returncode for role,child in children.items()}
        l.publish(OUT/'original-capture-carrier-outcomes.json',dict(actual_exits=exits,configs=configs,restart_retry=False))
        require(exits==dict(capture=0,rescue=0),'Original capture/watch outcome was nonzero; preserve it')
        closures={}
        for role,entry in configs.items():
            config=json.loads(l.checked(entry));directory=Path(config['output'])
            op=l.full_pin(directory/'root-original-identity.json');owner=json.loads(l.checked(op))
            cp=l.full_pin(directory/'root-original-result-and-owned-release.json');closure=json.loads(l.checked(cp))
            self.runtime.archived_closure(closure,owner,lambda e,as_json=True:self.reader.read_pin(e,as_json=as_json),exit_zero=True)
            require(self.control.show(owner['unit'])['LoadState']==self.control.show(owner['timer'])['LoadState']=='not-found',
                'Original capture/watch exact release incomplete')
            closures[role]=dict(owner=op,closure=cp,config=entry)
        result_pin=l.full_pin(P/'capture-original01/result.json');result=json.loads(l.checked(result_pin))
        watch_pin=l.full_pin(P/'capture-rescue-original01/result.json');watch=json.loads(l.checked(watch_pin))
        require(result['status']=='ORIGINAL_CAPTURE_ARCHIVED_NORMAL_PRODUCER_PRESERVED'
            and result['owner']==p['owner'] and result['normal_producer_mode_preserved'] is True,
            'Original single capture did not pass')
        require(watch['status']=='ORIGINAL_CONTROLLER_EXIT_OBSERVED' and watch['controller_alive'] is False
            and watch['recovery']['status']=='NO_RECORDED_SAVE_HOLD','Original watcher did not observe clean hold release')
        require(l.full_pin(result['checkpoint']['path'])==result['checkpoint']
            and l.full_pin(result['source']['path'])==result['source'],'Original candidate archive/producer changed')
        return dict(checkpoint=result['checkpoint'],normal_producer=result['source'],capture_result=result_pin,
            watch_result=watch_pin,capture_job=capture_pin,original_capture_lifecycles=closures,
            completed_slot_transition=result['completed_slot_transition'],normal_producer_mode_preserved=True)


def run(job):
    require(job['schema']=='profile06-production-next8M-window-job-v1' and job['output']==str(OUT),'Foreign original window job')
    plan=json.loads(Path(job['plan']['path']).read_bytes());context=Context(plan);l=context.l;l.checked(job['plan'])
    require(job['observer_source']==plan['observer_source']
        and Path(job['observer_source']['path'])==Path(__file__).resolve(),'Exact selected observer source required')
    context.authority();binding=context.reader.read_pin(plan['binding'])
    require(not OUT.exists(),'This original prospective window is already consumed');OUT.mkdir(mode=0o700)
    baseline_api=json.loads(l.checked(job['baseline_API']));baseline=context.counter.normalise(baseline_api)
    require(baseline['optimizer_identity']['process_id']==baseline['replay_identity']['process_id']==plan['owner']['pid'],
        'Baseline exposure belongs to another trainer')
    previous=copy.deepcopy(baseline);start=job['baseline_monotonic_s'];last_poll=start;last_applied=start;last_guard=0;missing=None
    try:
        require(time.monotonic()-start<30,'Fresh baseline missed its initial observation')
        while True:
            now=time.monotonic();require(now-last_poll<30,'Original observation gap reached30s');last_poll=now
            require(now-start<=plan['cutoff_s'],'Original window cutoff expired')
            if now-last_guard>=5:context.guard.owner_and_files(binding);last_guard=now
            try:wire,api=context.api()
            except (OSError,ValueError):
                if missing is None:missing=now
                require(now-missing<30,'Original API missing for30s');time.sleep(1);continue
            context.guard.healthy(api,baseline_api,binding['experiment'],time.time());missing=None
            current=context.counter.normalise(api);delta=progress(current,baseline,previous)
            if current['optimizer']['applied']>previous['optimizer']['applied']:last_applied=now
            require(now-last_applied<60,'No applied optimizer outcome for60s');previous=current
            status=dict(state='observing',elapsed_s=now-start,observed_unix_s=time.time(),**delta)
            context.capture.mutable_state(OUT/'status.json',status)
            if delta['both_horizons']:
                context.guard.owner_and_files(binding)
                api_pin=l.publish(OUT/'first-eligible-API.raw.json',wire)
                latch=l.publish(OUT/'first-durable-both-horizons.json',dict(status='LATCH',progress=delta,
                    observed_monotonic_s=now,observed_unix_s=time.time(),API=api_pin))
                captured=context.capture_at_endpoint(job,latch,api_pin)
                result=dict(status='CAPTURED_FIRST_BOTH_HORIZONS',progress=delta,latch=latch,
                    baseline_API=job['baseline_API'],owner=plan['owner'],**captured,CPU_verified=False,
                    quality_qualified=False,promotion=False,learning_speed_gain_verified=False)
                l.publish(OUT/'result.json',result)
                context.capture.mutable_state(OUT/'status.json',dict(status,state='captured',checkpoint=captured['checkpoint']))
                return 0
            time.sleep(1)
    except BaseException as error:
        l.publish(OUT/'result.json',dict(status='ORIGINAL_WINDOW_FAILED_OR_INCOMPLETE_PRESERVED',error=repr(error),
            original_capture_retried=False,trainer_restarted=False,quality_qualified=False,promotion=False))
        return 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--expected-job-sha256');args=parser.parse_args(argv)
    if not args.execute:print('PLAN_ONLY: no reads, outputs or runtime actions');return 0
    require(args.job and hashlib.sha256(args.job.read_bytes()).hexdigest()==args.expected_job_sha256,'Exact original window job required')
    return run(json.loads(args.job.read_bytes()))


if __name__=='__main__':raise SystemExit(main())
