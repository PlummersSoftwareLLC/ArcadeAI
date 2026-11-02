"""Prepare the one original final fullgame assessment CPU configuration.

Default inert. Production input requires the actual passing screen, four exact
CPU guards, and precommitted review packets. No scope or game is launched here.
"""
import argparse
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def pipeline():
    spec=importlib.util.spec_from_file_location('_fullgame_assessment_prepare_pipeline',HERE/'fullgame_review_pipeline_v7.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def prepare(precommit,output):
    p=pipeline();h=p.helpers();commit_pin=h.pin(precommit.resolve());commit=p.read(commit_pin)
    p.require(commit['schema']=='robotron-four-fullgame-independent-review-precommit-v1'and commit['engineering_only']is False,
        'Engineering precommit cannot prepare a production fullgame assessment')
    p.require(commit['ordered_legs']==[row['leg']for row in commit['cases']]==p.ORDER
        and commit['assessor']==h.pin(HERE/'assess_fullgame_study_v8.py')and commit['pipeline']==h.pin(HERE/'fullgame_review_pipeline_v7.py'),
        'Exact final-assessment source/order precommit required')
    prepared=p.read(commit['native_prepared']);producer=p.load('_fullgame_final_prepare_eligibility',HERE/'prepare_fullgame_study_v6.py')
    producer.eligible_screen(prepared['screen_assessment'],prepared['reference_epoch'],h)
    publication=p.read(commit['CPU_guard_publication'])
    p.require(prepared['engineering_only']is False and publication['status']=='PASS'
        and publication['prepared']==commit['native_prepared']and [row['leg']for row in publication['cases']]==p.ORDER,
        'Actual exact four-job CPU guard publication required')
    pins=[commit_pin,commit['native_prepared'],commit['CPU_guard_publication'],commit['assessor'],commit['pipeline'],
        h.pin(Path(__file__).resolve()),h.pin(p.NUMERIC),h.pin(p.CPU_CONTROLLER),*p.sources(h).values()]
    for case,review,guard in zip(prepared['cases'],commit['cases'],publication['cases']):
        p.require(case['leg']==review['leg']==guard['leg']and case['native_job']==review['native_job']==guard['native_job'],
            'Exact original final-assessment leg joins differ')
        packet=p.read(review['review_job']);cfg=p.read(review['review_config']);p.validate_packet(case,packet,cfg,h)
        p.require(packet['controller_config']==guard['qualified_controller_config'],'Reviewer uses a different native configuration')
        subject=p.read(case['native_job'])
        pins += [case['native_job'],case['acceptance'],review['review_job'],review['review_config'],guard['CPU_guard'],
            guard['qualified_controller_config'],*subject['inputs']]
    pins=list({pin['path']:pin for pin in pins}.values());output=output.resolve()
    p.require(output.is_relative_to(p.BASE)and not output.exists()and output.parent.is_dir(),'Exclusive original assessment preparation required')
    output.mkdir(mode=0o700);control=p.cpu_controller(h);assessment_output=output/'assessment-original01.json'
    cfg=dict(unit='robotron-round-fullgame-assessment-'+commit_pin['sha256'][:16]+'-original01.service',
        output=str(output/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',commit['assessor']['path'],
            '--assess','--precommit',commit_pin['path'],'--precommit-sha256',commit_pin['sha256'],'--output',str(assessment_output)],
        properties=p.CPU_PROPERTIES,observation_s=2040,pins=[control.pin(pin['path'])for pin in pins])
    cp=h.put(output/'controller-config.json',cfg);p.require(control.checked_config(cp['path'])==cfg,'Actual final-assessment CPU controller interface differs')
    return h.put(output/'prepared-final-assessment-NOT-LAUNCHED.json',dict(schema='robotron-fullgame-final-assessment-CPU-preparation-v1',
        review_precommit=commit_pin,config=cp,controller=h.pin(p.CPU_CONTROLLER),assessor=commit['assessor'],
        prospective_assessment_output=str(assessment_output),source=h.pin(Path(__file__).resolve()),
        all_four_scientific_legs_and_reviews_still_required=True,assessment_launched=False,full_game_quality_qualified=False,promotion=False))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--prepare',action='store_true');a.add_argument('--precommit',type=Path);a.add_argument('--output',type=Path);args=a.parse_args()
    if args.prepare:print(json.dumps(prepare(args.precommit,args.output)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
