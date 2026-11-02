"""Prepare bounded metadata-only qualification for four exact fullgame jobs.

Engineering inputs can exercise interfaces but can never publish launch guards.
Production inputs require an actual passing original screen. Inert by default.
"""
import argparse
import copy
import json
from pathlib import Path
import secrets

from importlib.util import spec_from_file_location,module_from_spec

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'logs/managed-learning-20261015/run-26'
HERE=Path(__file__).resolve().parent
ORDER=['R1','C1','R2','C2']
PROPERTIES=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']


def load(name,path):
    spec=spec_from_file_location(name,path);m=module_from_spec(spec);spec.loader.exec_module(m);return m


def require(value,message):
    if not value:raise ValueError(message)


def engineering_four(two_manifest,output):
    """Clone the actual two-policy engineering domain into four fresh contexts."""
    h=load('_fullgame_four_engineering_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    source=h.pin(two_manifest.resolve());original=json.loads(h.checked(source).read_bytes())
    require(original['schema']=='robotron-fullgame-two-context-engineering-v1'and original['engineering_only']is True,
            'Actual inert two-policy engineering domain required')
    output=output.resolve();require(output.is_relative_to(BASE),'Run-26 engineering output required');output.mkdir(mode=0o700)
    controller=load('_fullgame_four_engineering_controller',HERE/'control_fullgame_rounds_v2.py')
    reviewer=load('_fullgame_four_engineering_reviewer',HERE/'review_fullgame_rounds_v3.py')
    tokens=set();cases=[]
    for leg in ORDER:
        before=original['cases'][0 if leg.startswith('R')else 1]
        subject=copy.deepcopy(json.loads(h.checked(before['native_job']).read_bytes()))
        directory=output/leg;directory.mkdir(mode=0o700)
        subject.update(quality_leg=leg,output=str(directory/'native-output-original01'),
            prelaunch_CPU_closeout=str(directory/'fullgame-CPU-guards-original01/independent-closeout.json'))
        for field in ('sessions','connections'):
            subject[field]={}
            for slot in subject['actor_slots']:
                token=secrets.token_hex(16)
                while token in tokens or token=='0'*32:token=secrets.token_hex(16)
                tokens.add(token);subject[field][str(slot)]=token
        jp=h.put(directory/'job.json',subject)
        scope=h.put(directory/'acceptance.json',dict(schema='robotron-original-all32-quota64-quality-acceptance-v1',job=jp,
            original_attempt=1,no_retry=True,outer_start_horizon_s=21540,whole_cohort_timeout_s=21600,
            admission_mode=reviewer.COHORT_SELECTION['strategy'],expected_selected_games=64,wall_limit_s=22200,startup_trace_frames=1200,
            minimum_quality_completed_games=50,quality_minimum_games_remains=50,confirmation_min_complete_games=64,
            quality_qualified=False,promotion=False))
        runtime=subject['runtime'];cfg=dict(unit='robotron-compiled-full-tail32-integration-engineering-'+jp['sha256'][:12]+'-'+leg.lower()+'.service',
            output=str(directory/'execution-original01'),argv=[str(ROOT.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',runtime['path'],
                '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',runtime['sha256']],
            properties=reviewer.PROPERTIES,observation_s=22320,pins=[controller.pin(p['path'])for p in [jp,scope,*subject['inputs']]])
        cp=h.put(directory/'controller-config-ENGINEERING-ONLY.json',cfg)
        require(controller.checked_config(cp['path'])==cfg,'Actual fullgame config interface differs')
        reviewer.validate_scope(subject,jp,json.loads(h.checked(scope).read_bytes()),cfg)
        cases.append(dict(leg=leg,role='reference'if leg.startswith('R')else'candidate',native_job=jp,runtime=runtime,
            controller=h.pin(HERE/'control_fullgame_rounds_v2.py'),acceptance=scope,unqualified_controller_config=cp,native_launch_ready=False))
    return h.put(output/'ENGINEERING-ONLY-four-contexts.json',dict(schema='robotron-fullgame-rounds-four-job-preparation-v1',
        ordered_legs=ORDER,cases=cases,pair=original['pair'],source=h.pin(Path(__file__).resolve()),original_two_contexts=source,
        all256_transports_fresh_and_disjoint=len(tokens)==256,engineering_only=True,
        exact_job_CPU_closed=False,native_launch_ready=False,any_scientific_payload_launched=False,promotion=False))


def prepare(manifest,output):
    h=load('_fullgame_exact_guard_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    mp=h.pin(manifest.resolve());prepared=json.loads(h.checked(mp).read_bytes())
    require(prepared['schema']=='robotron-fullgame-rounds-four-job-preparation-v1'
            and prepared['ordered_legs']==[c['leg']for c in prepared['cases']]==ORDER
            and prepared['exact_job_CPU_closed']is prepared['native_launch_ready']is False,'Four exact unlaunched fullgame jobs required')
    engineering=prepared['engineering_only']
    require(type(engineering)is bool,'Exact engineering domain required')
    if not engineering:
        producer=load('_fullgame_exact_guard_production',HERE/'prepare_fullgame_study_v2.py')
        producer.eligible_screen(prepared['screen_assessment'],prepared['reference_epoch'],h)
    output=output.resolve();require(output.is_relative_to(BASE),'Fresh run-26 CPU output required');output.mkdir(mode=0o700)
    control=load('_fullgame_exact_guard_controller',ROOT/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    driver=h.pin(HERE/'check_fullgame_four_cpu_v3.py');helper=h.pin(ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    inputs=[mp,driver,helper,h.pin(Path(__file__).resolve()),h.pin(HERE/'prepare_fullgame_study_v2.py'),
        h.pin(HERE/'assess_screen_study.py'),h.pin(HERE/'review_fullgame_rounds_v3.py'),h.pin(HERE/'control_fullgame_rounds_v2.py')]
    for case in prepared['cases']:
        subject=json.loads(h.checked(case['native_job']).read_bytes())
        require(subject['engineering_only']is engineering,'Job/domain mismatch')
        inputs += [case['native_job'],case['runtime'],case['acceptance'],case['unqualified_controller_config'],*subject['inputs']]
    inputs=list({p['path']:p for p in inputs}.values())
    unit='robotron-fullgame-four-exact-CPU-'+mp['sha256'][:16]+'-original01.service'
    job=dict(schema='robotron-fullgame-four-exact-CPU-job-v1',unit=unit,output=str(output/'runtime'),prepared=mp,
        helpers=helper,reviewer=h.pin(HERE/'review_fullgame_rounds_v3.py'),inputs=inputs,source=driver,
        original_attempt=1,no_retry=True,engineering_only=engineering,scientific_payload=False)
    jp=h.put(output/'job.json',job)
    cfg=dict(unit=unit,output=str(output/'execution-original01'),argv=['/usr/bin/python3','-I','-B',driver['path'],
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=PROPERTIES,observation_s=240,pins=[control.pin(p['path'])for p in [jp,*inputs]])
    cp=h.put(output/'controller-config.json',cfg);require(control.checked_config(cp['path'])==cfg,'CPU controller ABI differs')
    return h.put(output/'prepared-CPU-NOT-LAUNCHED.json',dict(schema='robotron-fullgame-four-exact-CPU-preparation-v1',
        native_prepared=mp,CPU_job=jp,config=cp,controller=h.pin(ROOT/'tools/quality_capacity_proposal/control_quality32_review_v1.py'),
        engineering_only=engineering,CPU_launched=False,scientific_launch_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--engineering-four',action='store_true')
    p.add_argument('--manifest',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.engineering_four:print(json.dumps(engineering_four(a.manifest,a.output)),flush=True)
    elif a.prepare:print(json.dumps(prepare(a.manifest,a.output)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
