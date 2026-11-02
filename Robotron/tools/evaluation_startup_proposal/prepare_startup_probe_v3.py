"""Prepare fresh source-bound diagnostic metadata after original scientific closure.

No scheduling, lease open, device query, model import, checkpoint request or
promotion. Default entry is inert. Real guard/probe execution is separate.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import urllib.request

GAME=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUN=GAME/'logs/managed-learning-20261015/run-26'
READER=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
LAUNCHER_SHA='35ba401ef033485d1bb45aaf4141166b53f8c0fe4c181fd53306d51be6784c8d'
PACKAGE=HERE/'startup-diagnostic-profile03/runtime-source-package.json'
PACKAGE_SHA='321012906155651b94014399e0a02b2d9c9e868a4ae6c3639384887a9c6f3b10'
FINITE_SHA='14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5'
FULL={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}


def require(value,message):
    if not value:raise ValueError(message)


def decode(raw):
    require(type(raw) is bytes and 0<len(raw)<=4*1024*1024,'Bounded preparation JSON required')
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate preparation JSON key');result[key]=value
        return result
    def nonfinite(value):raise ValueError('Nonfinite preparation JSON: '+value)
    result=json.loads(raw,object_pairs_hook=unique,parse_constant=nonfinite)
    require(type(result) is dict,'Preparation JSON must be an object')
    return result


def checked_request(value):
    keys={'schema','preparation','probe_output','tag','predecessor','main_template','checkpoint',
          'checkpoint_metadata','finite_CPU','affinity','guard_affinity'}
    require(type(value) is dict and set(value)==keys
        and value['schema']=='robotron-private-startup-preparation-request-v1','Exact preparation request required')
    prep=Path(value['preparation']);output=Path(value['probe_output'])
    require(prep.is_absolute() and prep==prep.resolve() and prep.is_relative_to(RUN)
        and prep!=RUN and prep.parent.is_dir() and not prep.exists(), 'New canonical owned preparation required')
    require(output.is_absolute() and output==output.resolve() and output.parent==RUN and not output.exists()
        and not prep.is_relative_to(output) and not output.is_relative_to(prep),'Separate fresh probe output required')
    require(type(value['tag']) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value['tag']),
            'Explicit unique original unit tag required')
    for key in ('affinity','guard_affinity'):
        mask=value[key]
        require(type(mask) is list and mask and mask==sorted(set(mask))
            and all(type(n) is int and 0<=n<4096 for n in mask),'Explicit bounded inherited CPU affinity required')
    finite=value['finite_CPU']
    require(type(finite) is dict and set(finite)=={'report','job','owner','closure','config'},
            'Original strict finite CPU proof bundle required')
    return prep,output


def finite_checkpoint(checkpoint,proof,reader,closure):
    report,job,owner,closed,config=(reader.read_pin(proof[key]) for key in ('report','job','owner','closure','config'))
    fields=closure.archived_closure(closed,owner,lambda p,j:reader.read_pin(p,as_json=j),exit_zero=True)
    require(report.get('schema')=='robotron-phase-snapshot-checkpoint-CPU-result-v1'
        and report.get('status')=='PASS' and report.get('root_job')==job
        and job.get('verifier_sha256')==FINITE_SHA and report.get('script',{}).get('sha256')==FINITE_SHA,
        'Exact successful original strict CPU verifier required')
    require(report.get('cuda_initialized') is False and report.get('actual_restore_or_optimizer_step') is False
        and report.get('actual_quality_qualification') is False,'Finite proof scope differs')
    for source in (job.get('source',{}),job.get('verification_copy',{}),report.get('source_before',{}),
                   report.get('verification_copy',{})):
        require(source.get('sha256')==checkpoint['sha256'] and source.get('bytes')==checkpoint['bytes'],
                'Finite proof checkpoint bytes differ')
    require(report.get('finite',{}).get('tensors')==443
        and report['finite'].get('tensor_elements')==68760333
        and report.get('adam_state_count')==81,'Complete fixed-model finite inventory required')
    require(type(report.get('models')) is dict and set(report['models'])=={'online_state_dict','target_state_dict'}
        and all(row.get('strict_cpu_load') is True and row.get('tensor_count')==100
                for row in report['models'].values()),'Both strict CPU models required')
    argv=config.get('argv',[]);script=report['script']['path']
    script_pin=reader.pin(script)
    require(script_pin['sha256']==FINITE_SHA,'Original strict CPU verifier source changed')
    reader.read_pin(script_pin,as_json=False)
    require(config.get('unit')==owner['unit'] and script in argv and proof['job']['path'] in argv
        and proof['job']['sha256'] in argv and FINITE_SHA in argv,'Original CPU config/job/source binding differs')
    require(all(token in fields.get('ExecStart','') for token in (script,proof['job']['path'],proof['job']['sha256'],FINITE_SHA)),
            'Actual archived strict CPU command differs')
    return dict(status='ORIGINAL_FINITE_CPU_CHECKPOINT_BOUND',checkpoint_sha256=checkpoint['sha256'],
                report=proof['report'],closure=proof['closure'],numerical_module_imported=False)


def progressing(first,second,owner_pid,closure):
    for api in (first,second):
        for key in ('frame_count','learner_frame_count','optimized_samples','training_steps'):
            require(type(api.get(key)) is int and api[key]>=0,'Finite main work clocks required')
        closure.inspect_optimizer_observation(api['host_pipeline']['learning_exposure']['optimizer'])
        for kind in ('optimizer','replay'):
            row=api['host_pipeline']['learning_exposure'][kind]
            require(row['process_id']==owner_pid and all(type(row[k]) is int for k in
                ('process_id','instance_monotonic_ns','epoch')),'Actual optimizer/replay identity required')
    require(all(second[k]>first[k] for k in ('frame_count','learner_frame_count','optimized_samples','training_steps')),
            'Main did not progress during the fresh preparation interval')
    for kind in ('optimizer','replay'):
        left=first['host_pipeline']['learning_exposure'][kind];right=second['host_pipeline']['learning_exposure'][kind]
        require(all(left[k]==right[k] for k in ('process_id','instance_monotonic_ns','epoch')),
                'Main optimizer/replay instance changed')
    for key in ('epsilon','expert_ratio','lr'):
        require(all(type(api.get(key)) in (int,float) and math.isfinite(api[key]) for api in (first,second))
            and first[key]==second[key],'Main behavior recipe changed')


def main_shape(main):
    require(type(main) is dict and main.get('schema')=='robotron-main192-capacity-pilot-binding-v1'
        and type(main.get('actors')) is list and len(main['actors'])==192
        and type(main.get('held_hashes')) is dict and len(main['held_hashes'])==195,
        'Exact proposed main192/held195 template required')
    for actor in main['actors']:
        require(type(actor) is dict and all(type(actor.get(key)) is int and actor[key]>0 for key in ('pid','starttime_ticks'))
            and type(actor.get('slot')) is int and 0<=actor['slot']<192
            and type(actor.get('mask')) is list and actor['mask']
            and actor['mask']==sorted(set(actor['mask']))
            and all(type(cpu) is int and 0<=cpu<4096 for cpu in actor['mask']),'Exact main actor birth/slot/mask required')
    require({a['slot'] for a in main['actors']}==set(range(192))
        and len({a['pid'] for a in main['actors']})==192,'Distinct complete main actor roster required')
    require(all(type(path) is str and Path(path).is_absolute() and type(sha) is str
        and re.fullmatch('[a-f0-9]{64}',sha) for path,sha in main['held_hashes'].items()),'Exact195 held input hashes required')


def anchored_main_api(api,baseline,experiment,now,guard):
    guard.healthy(api,baseline,experiment,now)
    for key in ('epsilon','expert_ratio','lr'):
        require(type(api.get(key)) in (int,float) and math.isfinite(api[key]) and api[key]==baseline[key],
                'Current recipe differs from bound main template')
    for kind in ('optimizer','replay'):
        current=api['host_pipeline']['learning_exposure'][kind]
        original=baseline['host_pipeline']['learning_exposure'][kind]
        require(all(current[key]==original[key] for key in ('process_id','instance_monotonic_ns','epoch')),
                'Current optimizer/replay differs from bound main template')


class System:
    def __init__(self):
        self.reader=None;self.modules={};self.sources={};self.preparation=None

    def authenticate(self,request,entry):
        require(hashlib.sha256(READER.read_bytes()).hexdigest()==READER_SHA,'Evidence reader changed')
        spec=importlib.util.spec_from_file_location('_startup_prepare_reader_'+str(time.time_ns()),READER)
        self.reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.reader);r=self.reader
        require(r.read_pin(entry)==request and decode(r.read_pin(entry,as_json=False))==request,
                'Immutable original preparation request differs')
        launch_entry=r.pin(HERE/'startup_probe_launch_v4.py')
        require(launch_entry['sha256']==LAUNCHER_SHA,'Exact CPU-tested launcher required')
        launch=r.checked_module('_startup_prepare_launch_'+str(time.time_ns()),launch_entry)
        special=dict(reader=READER,main_guard=RUN/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py',
            closure=GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
            raw_api=GAME/'tools/eval_capacity_proposal/raw_api_witness_v1.py')
        names=dict(runtime='startup_probe_runtime_v4.py',core='startup_probe_core_v2.py',watchdog='startup_probe_watchdog_v1.py',
            tap_join='reconcile_acceptance_tap_v2.py',raw_matcher='startup_server_prefix_v2.py')
        self.modules['launcher']=launch;self.sources['launcher']=launch_entry
        for name,sha in launch.EXPECTED.items():
            path=special[name] if name in special else HERE/names[name]
            source=r.pin(path);require(source['sha256']==sha,'Fixed preparation helper differs: '+name)
            r.read_pin(source,as_json=False);self.sources[name]=source
            if name!='reader':self.modules[name]=r.checked_module('_startup_prepare_'+name+'_'+str(time.time_ns()),source)
        self.package_entry=r.pin(PACKAGE);require(self.package_entry['sha256']==PACKAGE_SHA,'Exact126 source package required')
        self.package=r.read_pin(self.package_entry)
        require(self.package['source_count']==len(self.package['files'])==len(self.package['file_pins'])==126,
                'Exact126 full source inventory required')
        for pin in self.package['file_pins'].values():r.read_pin(pin,as_json=False)
        own=r.pin(Path(__file__).resolve());r.read_pin(own,as_json=False);self.source=own

    def fields(self,unit):
        result=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=10)
        require(result.returncode==0,'Original predecessor/main unit query failed')
        return dict(row.split('=',1) for row in result.stdout.splitlines() if '=' in row)

    def closed(self,request):
        r=self.reader
        return self.modules['core'].verify_closed_predecessor(request['predecessor'],
            read=lambda pin,j:r.read_pin(pin,as_json=j),archive=self.modules['closure'].archived_closure,
            process_start=self.modules['runtime'].process_start,unit_fields=self.fields,
            cgroup_exists=lambda group:Path('/sys/fs/cgroup'+group).exists())

    def publish(self,name,raw):
        require(self.preparation is not None and Path(name).name==name,'Owned flat preparation artifact required')
        path=self.preparation/name
        with path.open('xb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        return self.reader.pin(path)

    def api(self):
        wire=self.modules['raw_api']
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
            raw=response.read(wire.MAX_WIRE_BYTES+1)
        return raw,wire.parse_wire(raw)

    def inventory(self,root,*,maximum_files,maximum_directories):
        found=[];directories=0
        require(root==root.resolve(strict=True) and root.is_dir(),'Exact input directory required')
        for directory,subdirs,names in os.walk(root,followlinks=False):
            directories+=1
            require(directories<=maximum_directories and not Path(directory).is_symlink()
                and all(not (Path(directory)/name).is_symlink() for name in subdirs),'Input directory link/bound differs')
            for name in names:
                path=Path(directory)/name
                require(path.is_file() and not path.is_symlink(),'Input file link/type differs')
                found.append(path);require(len(found)<=maximum_files,'Input inventory exceeds bound')
        return sorted(found)

    def capture(self,request):
        r=self.reader;guard=self.modules['main_guard'];runtime=self.modules['runtime'];closure=self.modules['closure']
        main=decode(r.read_pin(request['main_template'],as_json=False));main_shape(main)
        recipe_baseline=self.modules['raw_api'].parse_wire(r.read_pin(main['baseline_API'],as_json=False))
        guard.owner_and_files(main)
        fields=self.fields(main['owner']['unit'])
        require(fields.get('MainPID')==str(main['owner']['pid'])
            and fields.get('InvocationID')==main['owner']['invocation_id'] and fields.get('NRestarts')=='0',
            'Actual main original unit differs')
        checkpoint=request['checkpoint'];r.read_pin(checkpoint,as_json=False)
        require(Path(checkpoint['path']).is_relative_to(GAME/'models_dqn/managed-incumbents'),
                'Current protected incumbent checkpoint required')
        state_path=GAME/'logs/managed-learning-20261015/state.json'
        state_pin=r.pin(state_path);require(state_pin['bytes']<1048576,'Canonical state exceeds limit')
        state_bytes=state_path.read_bytes();require(r.pin(state_path)==state_pin,'Canonical incumbent changed during read')
        incumbent=decode(state_bytes)['incumbent']
        require((GAME/incumbent['checkpoint']).resolve()==Path(checkpoint['path'])
            and incumbent['sha256']==checkpoint['sha256'] and incumbent.get('full_game_quality_qualified') is True,
            'Selected checkpoint is not the actual protected incumbent')
        metadata=r.read_pin(request['checkpoint_metadata'])
        require(request['checkpoint_metadata']['path']==str((GAME/incumbent['metadata_path']).resolve())
            and request['checkpoint_metadata']['sha256']==incumbent['metadata_sha256']
            and metadata.get('checkpoint_sha256')==checkpoint['sha256']
            and metadata.get('protected_checkpoint')==checkpoint['path'],'Protected publication metadata differs')
        finite=finite_checkpoint(checkpoint,request['finite_CPU'],r,closure)
        boot_path=GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1'
        boot_entry=self.package['file_pins']['tools/sidecar_boot.py']
        boot=r.checked_module('_startup_prepare_boot_'+str(time.time_ns()),boot_entry).load_snapshot(boot_path)
        binary_paths=[Path('/usr/games/mame'),*self.inventory(GAME/'roms',maximum_files=512,maximum_directories=128),
                      *self.inventory(boot_path,maximum_files=16,maximum_directories=16)]
        binaries=[r.pin(path) for path in binary_paths]
        require(len({e['path'] for e in binaries})==len(binaries),'Duplicate binary/boot input')
        held={path:r.pin(path) for path in main['held_hashes']}
        require(all(pin['sha256']==main['held_hashes'][path] for path,pin in held.items()),'Main held source changed')
        masks=set(os.sched_getaffinity(0))
        require(set(request['affinity'])<=masks and set(request['guard_affinity'])<=masks,
                'Requested private/guard CPU mask is unavailable')
        lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');info=lease.lstat()
        require(lease==lease.resolve(strict=True) and stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid()
            and info.st_nlink==1 and info.st_dev==32 and info.st_ino==757,'Canonical original lease identity differs')
        lease_value=dict(path=str(lease),device=info.st_dev,inode=info.st_ino)
        first_raw,first=self.api();anchored_main_api(first,recipe_baseline,main['experiment'],time.time(),guard)
        time.sleep(2)
        second_raw,second=self.api();observed=time.time();guard.healthy(second,first,main['experiment'],observed)
        progressing(first,second,main['owner']['pid'],closure)
        guard.owner_and_files(main)
        age=observed-(GAME/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime
        require(0<=age<=360,'Current main autosave is stale')
        return dict(main=main,first_API=first_raw,second_API=second_raw,baseline=second,observed_unix_s=observed,
            checkpoint=checkpoint,checkpoint_metadata=request['checkpoint_metadata'],finite=finite,
            canonical_state=state_pin,canonical_bytes=state_bytes,held_inputs=held,binary_inputs=binaries,
            boot_identity=boot['identity'],lease=lease_value)

    def revalidate(self,request,snapshot):
        r=self.reader;self.modules['main_guard'].owner_and_files(snapshot['main'])
        for pin in [snapshot['checkpoint'],snapshot['checkpoint_metadata'],*snapshot['held_inputs'].values(),
                    *snapshot['binary_inputs'],*self.sources.values(),*self.package['file_pins'].values(),
                    self.package_entry,self.source]:
            require(r.pin(pin['path'])==pin,'A bound original input changed during preparation')
        require(r.pin(GAME/'logs/managed-learning-20261015/state.json')==snapshot['canonical_state'],
                'Canonical incumbent changed during preparation')
        require(0<=time.time()-snapshot['observed_unix_s']<=60,'Fresh preparation observation expired')
        for kind in ('private','guard'):
            unit='robotron-startup-prefix-'+kind+'-'+request['tag']+'.service'
            for name in (unit,unit.removesuffix('.service')+'.timer'):
                fields=self.fields(name)
                require(fields.get('Id')==name and fields.get('LoadState')=='not-found',
                        'A future original guard/probe unit name is already consumed')


def prepare(request,entry,*,system=None):
    caps=system if system is not None else System()
    require(not getattr(caps,'attempt_consumed',False),'One original preparation per capability instance')
    caps.attempt_consumed=True
    prep,output=checked_request(request)
    caps.authenticate(request,entry)
    predecessor=caps.closed(request)  # No input/lease/API/process census before this gate.
    snapshot=caps.capture(request)
    require(type(snapshot['observed_unix_s']) in (int,float) and math.isfinite(snapshot['observed_unix_s']),
            'Finite fresh input observation time required')
    require(not prep.exists() and not output.exists(),'Original output was consumed during capture')
    prep.mkdir(mode=0o700);caps.preparation=prep
    def save(name,value):return caps.publish(name,(json.dumps(value,indent=2,allow_nan=False)+'\n').encode())
    try:
        caps.publish('canonical-incumbent-original.json',snapshot['canonical_bytes'])
        caps.publish('main-first-API-original.bin',snapshot['first_API'])
        baseline=caps.publish('main-baseline-API-original.bin',snapshot['second_API'])
        main=copy.deepcopy(snapshot['main']);main['baseline_API']=baseline
        main_pin=save('fresh-main192-binding.json',main)
        evidence=save('fresh-input-provenance.json',{key:value for key,value in snapshot.items()
            if key not in ('main','first_API','second_API','baseline','canonical_bytes')})
        sources=caps.sources
        job=dict(schema='robotron-private-startup-runtime-job-v2',output=str(output),package=caps.package_entry,
            checkpoint=snapshot['checkpoint'],predecessor=request['predecessor'],main=main_pin,
            binary_inputs=snapshot['binary_inputs'],boot_assets=str(GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1'),
            boot_identity=snapshot['boot_identity'],sessions={str(slot):os.urandom(16).hex() for slot in range(4096,4112)},
            affinity=request['affinity'],lease=snapshot['lease'],external_guard_permit_path=str(prep/'original-live-guard-permit.json'),
            sources={key:sources[key] for key in set(caps.modules['runtime'].EXPECTED)|{'runtime'}})
        caps.modules['runtime'].checked_job(job)
        job_pin=save('original-runtime-job.json',job)
        plan=dict(schema='robotron-authenticated-private-startup-launch-v2',job=job_pin,
            output=str(prep/'guard-execution'),probe_unit='robotron-startup-prefix-private-'+request['tag']+'.service',
            guard_unit='robotron-startup-prefix-guard-'+request['tag']+'.service',guard_affinity=request['guard_affinity'],sources=sources)
        caps.modules['launcher'].checked_plan(plan)
        # A late input failure leaves retained originals and a job but no plan.
        caps.revalidate(request,snapshot)
        plan_pin=save('original-launch-plan.json',plan)
        caps.modules['launcher'].load_plan(plan_pin)
        result=dict(schema='robotron-private-startup-preparation-result-v1',status='PREPARED_NOT_SELECTED_NOT_EXECUTED',
            request=entry,predecessor=predecessor,fresh_inputs=evidence,main=main_pin,job=job_pin,plan=plan_pin,
            preparer_source=caps.source,guard_properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','TasksMax=128',
                'RuntimeMaxSec=600','TimeoutStopSec=5','SendSIGKILL=no','Restart=no','RemainAfterExit=yes'],
            GPU_idle_queried=False,lease_opened_or_locked=False,canonical_lease_identity_bound=True,
            model_imported=False,actual_guard_or_probe_launched=False,
            real_preparation_selected=False,real_ROM_start_proven=False,protocol_selected=False,
            quality_qualified=False,learning_speed_gain_verified=False)
        save('preparation-result.json',result)
        for path in (prep,prep.parent):
            fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        return result
    except BaseException as error:
        save('preparation-failure-preserved.json',dict(status='FAILED_ORIGINAL_PREPARATION_NO_RETRY',
            error=repr(error),actual_guard_or_probe_launched=False,real_preparation_selected=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--request');parser.add_argument('--request-sha256')
    parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY: no reads, queries, output, imports of game code, lease, scheduling or device calls')
    else:
        require(args.source_sha256 and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,
                'Explicit exact preparation source SHA required')
        require(args.request and args.request_sha256,'Explicit immutable request and SHA required')
        path=Path(args.request);raw=path.read_bytes()
        require(hashlib.sha256(raw).hexdigest()==args.request_sha256,'Original request SHA differs')
        caps=System()
        # Bootstrap only the fixed reader to obtain the request's full immutable identity.
        require(hashlib.sha256(READER.read_bytes()).hexdigest()==READER_SHA,'Evidence reader changed')
        spec=importlib.util.spec_from_file_location('_startup_prepare_entry_reader',READER)
        reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
        entry=reader.pin(path);reader.read_pin(entry)
        result=prepare(decode(raw),entry,system=caps)
        print(json.dumps(dict(status=result['status'],plan=result['plan'],actual_guard_or_probe_launched=False)))
