"""Inert operator preparation for actualE078/D4 metadata, guards and reviews.

Every controller invocation is returned as data; this module never launches one.
No model/tensor bodies, service controls, native games or canonical writes.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
I=B/'post-recovery-evaluation-isolation-original01-20261027'
W=B/'post-natural-turnover-durable-next-candidate-20261029-original01'
D=I/'declared-launcher-evaluator-adapters-original04-mmap-preparation'
L=Path(__file__).resolve().parent
M=I/'declared-launcher-census-original34-preparation/readonly-mmap-source-validation-original02'
CTX=M/'actual-current-main-engineering-contexts-original02'
META=L/'actual-metadata-preparation-original01'
STUDY=I/'durable-e078b0da-launcher-mmap-study-original01'
GUARD=L/'guard247-source-correction-original01'
NEW_GUARD_ROOT=STUDY/'four-exact-contexts-CPU-original02'
GUARD_OVERRIDE=NEW_GUARD_ROOT/'selected-guard-packet-override-original02.json'
GUARD_DRIVER_SHA='44d5e726d0163a8e33d2589bbb9ffab20b81a782baaa5d125b6db7adc81c56fc'
GUARD_PREPARER_SHA='d5d7578cbe3d0b3f5390af1fbb497c10d8f7c6e8bcd3e230fb26564f295ede6f'
ENDPOINT='e078b0da4ce4e25146fab7484f8489f590e1086370746cb392afcd7f5f8adef5'
CONTROL=G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
CONTROL_SHA='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
DRIVER_SHA='6d0539c4f0fe385e5347db7826a98ed4d380abdf91c4de326baabba14d9d4a3c'
CONTROL600_SHA='5679d36399de4f0c7cc83edd900728112110115fb9f9d44d20c9a3e3b7753f55'
CLOSE600_SHA='04a1052b1407a1b8cac7ee8806587d1b67e74bdc3d935ed50b7c5b6936b7bebc'


def require(value,message):
    if not value:raise RuntimeError(message)


def module(name,path,digest=None):
    if digest is not None:require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Selected source differs')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def helpers():
    return module('_E078_operator_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')


def sealed(h,path,digest=None):
    require(path.suffix!='.pt' and path.is_file() and not path.is_symlink() and path.stat().st_size<=2<<20,
        'Bounded metadata only')
    pin=h.pin(path);require(pin['identity']['mode']=='0o444','Sealed original metadata required')
    if digest is not None:require(pin['sha256']==digest,'Selected original metadata differs')
    return json.loads(h.checked(pin).read_bytes()),pin


def controller_argv(path,digest,config):
    return ['/usr/bin/python3.12','-I','-B',str(path),'--execute','--config',config['path'],'--expected-source-sha256',digest]


def metadata_inputs(h):
    construction,_=sealed(h,D/'source-construction.json','c7e379d9967bfcd2f8facd7ba56ce217441a2bf5dee669d8c9e8e4cafba801c8')
    values=[]
    for row in construction['records']:
        selected=row['source'];actual=h.pin(Path(selected['path']))
        require(all(actual[key]==value for key,value in selected.items()),
            'Current D4 source differs from immutable selected construction')
        require(actual['identity']['mode']=='0o444' and actual['identity']['uid']==os.getuid()
            and actual['identity']['nlink']==1 and not Path(selected['path']).is_symlink(),
            'Selected D4 source must remain owned, readonly and independently linked')
        values.append(actual)
    return values


def prepare_metadata(h):
    # Every actual qualification is checked before the exclusive output mkdir.
    result,rp=sealed(h,W/'result.json','e2f2fb5b831a64bdc5b8b9a3062808bd15bfe7781dd67bda42d9dbfc4d746bc4')
    require(result['state']=='captured_CPU_verified' and result['endpoint']['sha256']==ENDPOINT,'Actual ownE078 capture required')
    canon,cc=sealed(h,W/'canonical-profile-CPU-original01/independent-original-canonical-CPU-closeout.json',
        '557ab069f9d2387b306464e0a877cb87b9b77854426240384deb77f63b29acd3')
    frozen,fc=sealed(h,W/'frozen-profile-CPU-original01/independent-original-profile-scope-closeout.json',
        '218bf368c6d0fa96fc3f166cae03200a7217cf9069506e1d85b5e2d701575b72')
    require(canon['status']==frozen['status']=='PASS' and canon['actual_exit']==frozen['actual_exit']==0,
        'Actual closed canonical/frozen CPU scopes required')
    candidate,cp=sealed(h,W/'frozen-profile-CPU-original01/independent-profile-adoption.json')
    proof,_=sealed(h,Path(candidate['profile_proof']['path']))
    require(candidate['status']=='PASS' and candidate['actual_exit']==0 and candidate['all_Q_bytes_and_actions_match']is True
        and candidate['original_scope_released']is True and proof['checkpoint']['sha256']==ENDPOINT
        and frozen['profile_adoption']==cp,'ActualE078 independentlyclosed frozen adoption required')
    _,ref=sealed(h,I/'reference-frozen-profile-v2-CPU-original01/independent-profile-adoption.json',
        '59f6fd9df2987ff15c4506b9fa306479bf9ddb893a45aeb21f6c434effe75654')
    raw,hot=sealed(h,CTX/'long-original01/runtime/independent-raw-review.json',
        '5808521bcf78a52a25d1abc271120bad12d9bdf4f13f2ccd6da27bed29e5f6fa')
    require(raw['status']=='PASS' and raw['full_main_input_count']==247 and len(raw['original_sources'])==10,
        'Exact new ten-source/247-input original main raw readiness required')
    long,lp=sealed(h,CTX/'long-original01/independent-original-engineering-closeout.json',
        'ac8ab83b08190ddf9017969b00de88e50c889a291372ccc1cebaebaff30320bc')
    abort,ap=sealed(h,CTX/'abort-original01/independent-original-engineering-closeout.json',
        '7ce726f98446f2e9202d89320226cabfcd2bfd2203b45255b6e05c55f7fa1ed8')
    for value,mode,code in [(long,'long',0),(abort,'abort',1)]:
        require(value['status']=='PASS_ENGINEERING_ONLY' and value['mode']==mode and value['worker_actual_exit']==code
            and value['original_parent_actual_exit']==0 and value['all_original_births_units_cgroups_and_tmpfs_control_absent']is True,
            'Actual newlong/abort owned original closure required')
    usage,up=sealed(h,I/'declared-launcher192-usage-smoke-original01-preparation/prepared-original03/ROOT-independent-original-owned192-usage-closeout.json',
        'b886b608c5bec16c9a46a365109408089b7cba097a61e3f9301b6d993ba29b8d')
    require(usage['status']=='PASS_USAGE_FIXTURE_ONLY' and usage['original_parent_actual_exit']==0
        and usage['all192_original_Popen_actual_exit0_and_reaped']is True
        and usage['all_original_births_and_own_unit_cgroup_absent']is True
        and usage['actual_simultaneous192_MAME_or_full500ms_qualified']is False,'Honest bounded192 usagefixture required')
    _,joined=sealed(h,CTX/'independent-deadline-main-domain-mmap-engineering-readiness-original02.json',
        '9f084bb2cc28c568634cb6769517bd6c29971fe35f18ffd1dd34448cbc47788a')
    _,lease=sealed(h,I/'post-outage-permanent-private-coordinator-restoration-original01.json',
        '26ccbdd83b17aabc5daeecb77e40278f68329152e8913fde26bc75073ccfe09d')
    _,peer=sealed(h,D/'independent-declared-launcher-mmap-adapter-D4-source-peer-v1.json',
        '68cdc236e777db4efcf4722734ba369dad5d737db2b2c48c6eade5cfa25dcd04')
    driver=h.pin(L/'prepare_selected_metadata600_v1.py');require(driver['sha256']==DRIVER_SHA,'Selected metadata600driver differs')
    control=module('_E078_metadata600_controller',L/'control_metadata600_v1.py',CONTROL600_SHA)
    require(not META.exists() and not STUDY.exists(),'Whollyfresh original outputs required')
    inputs=metadata_inputs(h)+[rp,cc,fc,cp,ref,hot,lp,ap,up,joined,lease,peer,driver,
        h.pin(Path(__file__).resolve()),h.pin(L/'control_metadata600_v1.py'),h.pin(L/'close_metadata600_v1.py')]
    inputs+=list(raw['original_sources'].values())
    inputs=list({value['path']:value for value in inputs}.values())
    META.mkdir(mode=0o700)
    job=dict(schema='robotron-selected-admission-study-CPU-preparation-v1',
        unit='robotron-durable-e078-study-preparation-CPU-original01-20261029.service',
        output=str(META/'runtime'),study_directory=str(STUDY),candidate_sha256=ENDPOINT,inputs=inputs,
        original_attempt=1,no_retry=True,capture_result=rp,reference_profile=ref,candidate_profile=cp,
        deadline_readiness=hot,lease_recovery=lease)
    jp=h.put(META/'job.json',job)
    cfg=dict(unit=job['unit'],output=str(META/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',driver['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=600',
            'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],observation_s=660,
        pins=[control.pin(p['path'])for p in [jp,*inputs]])
    cfgp=h.put(META/'controller-config.json',cfg);require(control.checked_config(cfgp['path'])==cfg,'Metadata600 config ABI differs')
    packet=h.put(META/'prepared-NOT-LAUNCHED.json',dict(job=jp,config=cfgp,source=h.pin(Path(__file__).resolve()),
        driver=driver,controller=h.pin(L/'control_metadata600_v1.py'),closer=h.pin(L/'close_metadata600_v1.py'),
        exact_metadata_runtime_s=600,observation_s=660,scientific_payload_launched=False,quality_qualified=False,promotion=False))
    return dict(prepared=packet,Root_next_controller_argv=controller_argv(L/'control_metadata600_v1.py',CONTROL600_SHA,cfgp))


def closed_metadata(h):
    closed,_=sealed(h,META/'independent-original-CPU-scope-closeout.json')
    require(closed['status']=='PASS_ENGINEERING_ONLY' and closed['actual_exit']==0
        and closed['actual_runtime_limit_s']==600,'Actual original metadata600closure required')
    report,_=sealed(h,Path(closed['actual_report']['path']))
    require(report['status']=='PASS' and report['selected_sha256']==ENDPOINT,'Actual selectedmetadata report differs')
    return report


def prepare_guard_override(h):
    metadata_inputs(h)
    report=closed_metadata(h)
    old=report['exact_CPU_packet'];before=json.loads(h.checked(old).read_bytes())
    old_cfg=json.loads(h.checked(before['config']).read_bytes())
    require(not Path(old_cfg['output']).exists(), 'Old unlaunched guard execution must remain unused')
    control=module('_E078_guard_original_controller',CONTROL,CONTROL_SHA)
    require(control.show(old_cfg['unit'])['LoadState']=='not-found', 'Old guard original unit was already used')
    require(not NEW_GUARD_ROOT.exists(), 'New guard override is one original preparation only')
    module('_E078_corrected_guard_driver',GUARD/'qualify_round_study_cpu_v6.py',GUARD_DRIVER_SHA)
    preparer=module('_E078_corrected_guard_preparer',GUARD/'prepare_round_cpu_guard_v9.py',GUARD_PREPARER_SHA)
    replacement=preparer.prepare(Path(report['native_prepared']['path']),NEW_GUARD_ROOT)
    value=json.loads(h.checked(replacement).read_bytes())
    require(value['native_prepared_manifest']==report['native_prepared']
        and value['driver']['sha256']==GUARD_DRIVER_SHA, 'Corrected packet must bind the same four actual native jobs')
    override=h.put(GUARD_OVERRIDE,dict(schema='robotron-explicit-unlaunched-four-guard-packet-replacement-v1',
        original_metadata_closeout=h.pin(META/'independent-original-CPU-scope-closeout.json'),
        original_metadata_report=h.pin(META/'runtime/report.json'), original_unlaunched_guard_packet=old,
        replacement_guard_packet=replacement, native_prepared=report['native_prepared'],
        corrected_driver=h.pin(GUARD/'qualify_round_study_cpu_v6.py'),
        corrected_preparer=h.pin(GUARD/'prepare_round_cpu_guard_v9.py'),
        old_guard_execution_unused=True, same_four_native_jobs_preserved=True,
        correction='Only actual full_main_input_count assertion243 to247; no scientific retry or native source change.',
        source=h.pin(Path(__file__).resolve()),CPU_launched=False,scientific_payload_launched=False))
    return dict(override=override,Root_next_controller_argv=controller_argv(CONTROL,CONTROL_SHA,value['config']))


def guard_packet(h):
    report=closed_metadata(h);override,_=sealed(h,GUARD_OVERRIDE)
    require(override['schema']=='robotron-explicit-unlaunched-four-guard-packet-replacement-v1'
        and override['original_metadata_report']==h.pin(META/'runtime/report.json')
        and override['original_metadata_closeout']==h.pin(META/'independent-original-CPU-scope-closeout.json')
        and override['original_unlaunched_guard_packet']==report['exact_CPU_packet']
        and override['native_prepared']==report['native_prepared']
        and override['old_guard_execution_unused']is override['same_four_native_jobs_preserved']is True,
        'Root-selected immutable replacement guard packet required')
    require(h.pin(GUARD/'qualify_round_study_cpu_v6.py')==override['corrected_driver']
        and override['corrected_driver']['sha256']==GUARD_DRIVER_SHA
        and h.pin(GUARD/'prepare_round_cpu_guard_v9.py')==override['corrected_preparer']
        and override['corrected_preparer']['sha256']==GUARD_PREPARER_SHA, 'Corrected guard sources differ')
    packet=override['replacement_guard_packet'];value=json.loads(h.checked(packet).read_bytes())
    require(value['native_prepared_manifest']==report['native_prepared']
        and value['driver']==override['corrected_driver'], 'Actual same-four-job selected guard binding differs')
    return packet,value


def prepare_reviews(h):
    selected_D4_inputs=metadata_inputs(h)  # Before importing or writing any review metadata.
    report=closed_metadata(h);guard_packet(h);guardroot=NEW_GUARD_ROOT
    guards,_=sealed(h,guardroot/'all-four-exact-native-guard-receipts.json')
    require(guards['status']=='PASS' and len(guards['guards'])==4,'Actual exactfourjobguard closeout required')
    p=module('_E078_actual_review_preparer',D/'prepare_deadline_independent_review_v4.py')
    rp=p.precommit(Path(report['native_prepared']['path']),guardroot/'all-four-exact-native-guard-receipts.json',STUDY/'review-precommit-original01')
    packet=json.loads(h.checked(rp).read_bytes());driver=h.pin(D/'check_deadline_review_preparation_cpu_v3.py')
    root=STUDY/'deadline-review-preparation-CPU-original01';require(not root.exists(),'Fresh original reviewCPU path required');root.mkdir(mode=0o700)
    values=selected_D4_inputs+[rp,report['native_prepared'],h.pin(guardroot/'all-four-exact-native-guard-receipts.json'),
        h.pin(GUARD_OVERRIDE),h.pin(GUARD/'qualify_round_study_cpu_v6.py'),h.pin(GUARD/'prepare_round_cpu_guard_v9.py')]
    for case in packet['cases']:
        job=json.loads(h.checked(case['native_job']).read_bytes());values += [case['native_job'],case['native_config'],case['guard'],*job['inputs']]
    inputs=list({value['path']:value for value in values}.values())
    job=dict(schema='robotron-deadline-review-preparation-CPU-engineering-job-v1',
        unit='robotron-durable-e078-review-preparation-CPU-original01-20261029.service',output=str(root/'runtime'),
        source=driver,review_precommit=rp,original_attempt=1,no_retry=True,inputs=inputs)
    jp=h.put(root/'job.json',job);control=module('_E078_review_CPU_controller',CONTROL,CONTROL_SHA)
    cfg=dict(unit=job['unit'],output=str(root/'execution-original01'),argv=['/usr/bin/python3','-I','-B',driver['path'],
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=240,pins=[control.pin(v['path'])for v in [jp,*inputs]])
    cp=h.put(root/'controller-config.json',cfg);require(control.checked_config(cp['path'])==cfg,'Actual reviewCPU ABI differs')
    return dict(review_precommit=rp,CPU_job=jp,config=cp,Root_next_controller_argv=controller_argv(CONTROL,CONTROL_SHA,cp),scientific_payload_launched=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    for name in ['prepare-metadata','close-metadata','prepare-guard-override','print-four-guard-command','close-four-guards','prepare-review-precommit']:
        g.add_argument('--'+name,action='store_true')
    a=p.parse_args(argv)
    if not any(vars(a).values()):print('PLAN_ONLY: no reads, outputs, controls, models or CPU launches');return
    h=helpers()
    if a.prepare_metadata:out=prepare_metadata(h)
    elif a.close_metadata:
        out=module('_E078_actual_metadata600_close',L/'close_metadata600_v1.py',CLOSE600_SHA).close(META)
    elif a.prepare_guard_override:out=prepare_guard_override(h)
    elif a.print_four_guard_command:
        pp,value=guard_packet(h);out=dict(prepared=pp,Root_next_controller_argv=controller_argv(CONTROL,CONTROL_SHA,value['config']))
    elif a.close_four_guards:
        pp,value=guard_packet(h);closer=module('_E078_exact_four_guard_close',D/'close_round_study_cpu_v6.py')
        out=closer.close(pp['path'],pp['sha256'],h.pin(D/'close_round_study_cpu_v6.py')['sha256'])
    else:out=prepare_reviews(h)
    if out is None and a.close_four_guards:
        out=dict(status='EXACT_FOUR_GUARDS_CLOSED',publication=h.pin(NEW_GUARD_ROOT/'all-four-exact-native-guard-receipts.json'))
    print(json.dumps(out),flush=True)


if __name__=='__main__':main()
