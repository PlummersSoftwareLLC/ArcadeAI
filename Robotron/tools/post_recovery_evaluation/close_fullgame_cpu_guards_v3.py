"""Independently close one exact four-job CPU scope and publish launch guards.

Engineering packets are rejected before publication. Complete-game quality and
promotion always require the later independently reviewed original game runs.
"""
import argparse
import json
from pathlib import Path

from importlib.util import spec_from_file_location,module_from_spec

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
ORDER=['R1','C1','R2','C2']


def load(name,path):
    spec=spec_from_file_location(name,path);m=module_from_spec(spec);spec.loader.exec_module(m);return m


def require(value,message):
    if not value:raise ValueError(message)


def close(directory):
    h=load('_fullgame_guard_close_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    producer=load('_fullgame_guard_close_producer',HERE/'prepare_fullgame_study_v2.py')
    directory=directory.resolve();jp=h.pin(directory/'job.json');job=producer.read(jp,h)
    prepared=producer.read(job['prepared'],h)
    require(job['schema']=='robotron-fullgame-four-exact-CPU-job-v1'
            and prepared['schema']=='robotron-fullgame-rounds-four-job-preparation-v1'
            and job['engineering_only']is prepared['engineering_only']is False,
            'Engineering contexts cannot publish scientific launch guards')
    require(prepared['ordered_legs']==[case['leg']for case in prepared['cases']]==ORDER
            and job['original_attempt']==1 and job['no_retry']is True,'Four exact original jobs required')
    producer.eligible_screen(prepared['screen_assessment'],prepared['reference_epoch'],h)
    cfg=producer.read(h.pin(directory/'controller-config.json'),h)
    driver=h.pin(HERE/'check_fullgame_four_cpu_v3.py')
    require(job['source']==driver and cfg['argv']==['/usr/bin/python3','-I','-B',driver['path'],
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        'Actual four-job CPU driver/argv differs')
    report_pin=h.pin(Path(job['output'])/'report.json');report=producer.read(report_pin,h)
    require(report['schema']=='robotron-fullgame-four-exact-contexts-CPU-result-v1'and report['status']=='PASS'
            and report['original_job']==jp and report['engineering_only']is False
            and report['all_four_exact_contexts_qualified']is True
            and report['Torch_imported']is report['weights_deserialized']is report['GPU_or_MAME_launched']is False,
            'Actual passed production-context CPU result required')
    require([row['native_job']for row in report['actual_contexts']]==[case['native_job']for case in prepared['cases']]
            and len(report['actual_rejected_contexts'])==48
            and all(row['rejected']is True for row in report['actual_rejected_contexts']),
            'All four exact contexts and48 damaged-context rejections required')
    plans=[]
    native=load('_fullgame_guard_close_native',HERE/'run_fullgame_rounds_v3.py')
    contract=native.round_contract()
    control=load('_fullgame_guard_close_controller',HERE/'control_fullgame_rounds_v2.py')
    for case in prepared['cases']:
        subject=producer.read(case['native_job'],h);ctx=native.validate_completed_context(subject,h)
        path=Path(subject['prelaunch_CPU_closeout'])
        require(not path.exists()and not path.parent.exists(),'Exact original guard namespace must remain unused')
        try:contract.validate_launch(subject,case['native_job'],ctx,h)
        except FileNotFoundError as error:
            require(error.filename==str(path),'Only prospective exact CPU guard may be absent')
        else:raise ValueError('Uncreated per-job CPU guard is required before publication')
        launch=Path(case['native_job']['path']).parent/'controller-config-CPU-QUALIFIED.json'
        require(not launch.exists(),'Exact original launch configuration must remain unused')
        config=producer.read(case['unqualified_controller_config'],h)
        require(control.checked_config(case['unqualified_controller_config']['path'])==config,'Actual fullgame controller differs')
        plans.append((case,subject,path,launch,config))
    # Reuse the established independent six-descriptor/resource/argv/birth/unit/
    # timer/cgroup closer. Its scope is metadata engineering even for production
    # inputs; this proves CPU closure, never scientific performance.
    closer=load('_fullgame_guard_actual_CPU_close',HERE/'close_engineering_cpu_scope_v2.py')
    closure_pin=closer.close(directory)
    closure=producer.read(closure_pin,h)
    require(closure['actual_report']==report_pin and closure['actual_exit']==0
            and closure['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified']is True,
            'Independent original CPU closure differs')
    records=[]
    for case,subject,path,launch,config in plans:
        path.parent.mkdir(mode=0o700)
        guard=h.put(path,dict(schema='robotron-fullgame-exact-job-CPU-closeout-v1',status='PASS',
            native_job=case['native_job'],runtime=subject['runtime'],original_CPU_job=jp,
            original_CPU_report=report_pin,independent_original_CPU_closeout=closure_pin,
            actual_exit=0,original_scope_released=True,actual_CPU_cores=2,actual_memory_bytes=4<<30,
            actual_runtime_limit_s=180,original_attempt=1,no_retry=True,source=h.pin(Path(__file__).resolve()),
            full_game_quality_qualified=False,promotion=False))
        config['pins'].append(control.pin(guard['path']))
        launch_pin=h.put(launch,config)
        require(control.checked_config(launch_pin['path'])==config,'CPU-qualified config interface differs')
        contract.validate_launch(subject,case['native_job'],native.validate_completed_context(subject,h),h)
        records.append(dict(leg=case['leg'],native_job=case['native_job'],CPU_guard=guard,qualified_controller_config=launch_pin))
    return h.put(directory/'independent-four-exact-fullgame-CPU-guards.json',dict(
        schema='robotron-four-exact-fullgame-CPU-guard-publication-v1',status='PASS',prepared=job['prepared'],
        CPU_closeout=closure_pin,cases=records,scientific_payload_launched=False,full_game_quality_qualified=False,promotion=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--close',action='store_true');p.add_argument('--directory',type=Path);a=p.parse_args()
    if a.close:print(json.dumps(close(a.directory)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
