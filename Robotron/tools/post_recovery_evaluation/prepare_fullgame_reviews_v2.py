"""Precommit exact independent review packets before any fullgame launch.

Default is inert; production needs the actual four-job CPU guard publication.
Engineering metadata may exercise interfaces but never authorizes a payload.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent


def pipeline():
    spec=importlib.util.spec_from_file_location('_fullgame_review_prepare_pipeline',HERE/'fullgame_review_pipeline.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def prepare(manifest,guard_publication,output,*,engineering=False):
    p=pipeline();h=p.helpers();mp=h.pin(manifest.resolve());prepared=p.read(mp)
    p.require(prepared['schema']=='robotron-fullgame-rounds-four-job-preparation-v1'
        and prepared['ordered_legs']==[case['leg']for case in prepared['cases']]==p.ORDER
        and prepared['engineering_only']is engineering,'Exact four-job/domain manifest required')
    guard_pin=None;guards={}
    if not engineering:
        eligibility=p.load('_fullgame_review_production_eligibility',HERE/'prepare_fullgame_study.py')
        eligibility.eligible_screen(prepared['screen_assessment'],prepared['reference_epoch'],h)
        guard_pin=h.pin(guard_publication.resolve());publication=p.read(guard_pin)
        p.require(publication['schema']=='robotron-four-exact-fullgame-CPU-guard-publication-v1'
            and publication['status']=='PASS'and publication['prepared']==mp
            and [case['leg']for case in publication['cases']]==p.ORDER,'Actual exact four-job CPU guard publication required')
        guards={row['leg']:row for row in publication['cases']}
    output=output.resolve();p.require(output.is_relative_to(p.BASE)and not output.exists()and output.parent.is_dir(),'Exclusive run-26 review preparation output required')
    for case in prepared['cases']:
        root=Path(case['native_job']['path']).parent
        p.require(all(not(root/name).exists()for name in ('independent-review-job.json','independent-review-controller-config.json',
            'independent-review-execution-original01','independent-quality-leg-review-original01')),'Original review paths must be unused')
    output.mkdir(mode=0o700);sources=p.sources(h);control=p.cpu_controller(h);reviewer=h.pin(HERE/'review_fullgame_rounds_v2.py')
    records=[]
    for case in prepared['cases']:
        root=Path(case['native_job']['path']).parent;subject=p.read(case['native_job'])
        p.require(subject['engineering_only']is engineering,'Exact job engineering domain required')
        native_config=case['unqualified_controller_config']if engineering else guards[case['leg']]['qualified_controller_config']
        if not engineering:
            p.require(guards[case['leg']]['native_job']==case['native_job'],'CPU publication belongs to another exact job')
            native=p.load('_fullgame_review_exact_native',HERE/'run_fullgame_rounds_v2.py')
            native.round_contract().validate_launch(subject,case['native_job'],native.validate_completed_context(subject,h),h)
        packet=dict(schema='robotron-original-quota64-independent-leg-review-job-v1',
            output=str(root/'independent-quality-leg-review-original01'),native_job=case['native_job'],acceptance=case['acceptance'],
            controller_config=native_config,sources=sources)
        jp=h.put(root/'independent-review-job.json',packet)
        pins=[jp,case['native_job'],case['acceptance'],native_config,reviewer,*sources.values(),h.pin(HERE/'fullgame_review_pipeline.py'),h.pin(Path(__file__).resolve())]
        config=dict(unit='robotron-round-fullgame-review-'+case['native_job']['sha256'][:12]+'-'+case['leg'].lower()+'-original01.service',
            output=str(root/'independent-review-execution-original01'),argv=['/usr/bin/python3.12','-I','-B',reviewer['path'],
                '--observe','--job',jp['path'],'--job-sha256',jp['sha256'],'--expected-source-sha256',reviewer['sha256']],
            properties=p.CPU_PROPERTIES,observation_s=2040,pins=[control.pin(pin['path'])for pin in pins])
        cp=h.put(root/'independent-review-controller-config.json',config)
        p.require(control.checked_config(cp['path'])==config,'Actual bounded review controller ABI differs')
        p.validate_packet(case,packet,config,h)
        records.append(dict(leg=case['leg'],native_job=case['native_job'],review_job=jp,review_config=cp,
            controller=h.pin(p.CPU_CONTROLLER),engineering_only=engineering))
    return h.put(output/'precommitted-four-reviews.json',dict(schema='robotron-four-fullgame-independent-review-precommit-v1',
        native_prepared=mp,CPU_guard_publication=guard_pin,cases=records,ordered_legs=p.ORDER,
        leg_reviewer=reviewer,pipeline=h.pin(HERE/'fullgame_review_pipeline.py'),source=h.pin(Path(__file__).resolve()),
        assessor=h.pin(HERE/'assess_fullgame_study_v2.py'),created_monotonic_s=time.monotonic(),
        current_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        engineering_only=engineering,scientific_payload_launched=False,full_game_quality_qualified=False,promotion=False))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--prepare',action='store_true');a.add_argument('--engineering',action='store_true')
    a.add_argument('--manifest',type=Path);a.add_argument('--guard-publication',type=Path);a.add_argument('--output',type=Path);args=a.parse_args()
    if args.prepare:print(json.dumps(prepare(args.manifest,args.guard_publication,args.output,engineering=args.engineering)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
