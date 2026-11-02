"""Inert post-metadata D7 guard/readiness/review preparation; never launches.

Every mode consumes actual new closed artifacts. No default cached guard, old
E078/862 evidence, future policy hash or unclosed CPU result grants qualification.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
I=G/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027'
L=Path(__file__).resolve().parent
META=L/'actual-metadata-preparation-original01'
ST=I/'durable-window03-D7-fixed-RCRC-study-original01'
F=I/'declared-launcher-evaluator-adapters-original06-fresh-study-namespaces-preparation/source-family-original02-unit-authority'
Q=L/'closed-metadata-reuse-guard-final-original01-preparation'
OVERRIDE=L/'selected-closed-metadata-guard-original01.json'
BASE=ST/'ROOT-resource-readiness-original01.json'
REVIEW=ST/'review-precommit-original01/precommitted-four-reviews.json'
CPU=ST/'deadline-review-preparation-CPU-original01'
FINAL=ST/'ROOT-final-resource-and-review-readiness-before-R1-original01.json'
CONTROL=G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
CONTROL_SHA='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
SELECTOR_SHA='8f106b9ba5d78fcbeb05a52aa2ab002f7daa040a98929f94dbd82aed8ebc6f37'
GUARD_FAMILY_SHA='c8c9069e42a26d3404eb272363c2b1c4846e267e50f464a79ee4e9cba6a87eba'
FINALIZER_SHA='d3482ef378bfa84b83b6b4c2fef1f284096cdbb0dd222504e580ea54f69d6da6'
READINESS_SHA='29cf5ff16cf117246eff8409b5ea3e5d4da7829f7517c0a41576948585beafa7'
CLOSE_REVIEW_SHA='d7cc1b625d167daea4d74a490bed09bca4bfed8e95ffa6a5dd721fefa1e68f3a'


def require(value,message):
    if not value:raise RuntimeError(message)


def module(name,path,digest):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Exact selected source differs')
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def setup():
    m=module('_postguard_actual_metadata_workflow',L/'prepare_window03_D7_metadata600_v1.py',
        '46305b34f7291c8d8991e6a29d3bf77ae333d41271daf82e447f75c69334b09a')
    return m,m.helpers()


def metadata(m,h,path,digest=None):
    return m.metadata(h,path,digest)


def closed_metadata(m,h):
    m.selected_sources(h);prepared,_=m.packet(h)
    closed,cp=metadata(m,h,META/'independent-original-CPU-scope-closeout.json')
    require(closed['status']=='PASS_ENGINEERING_ONLY'and closed['actual_exit']==0
        and closed['actual_runtime_limit_s']==600
        and closed['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified']is True
        and closed['original_job']==prepared['job']and closed['original_config']==prepared['config']
        and closed['source']==prepared['closer'],'Actual NEW metadata600 owned closure required')
    report,rp=metadata(m,h,Path(closed['actual_report']['path']))
    require(rp==closed['actual_report']and report['status']=='PASS'and report['original_job']==prepared['job']
        and report['native_prepared']['path']==str(ST/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json'),
        'Exact actual new four-job metadata result required')
    return report,cp,rp


def guard(m,h,closed_required=False):
    report,mc,mr=closed_metadata(m,h)
    metadata(m,h,Q/'prepared-D7-new2s-closed-metadata-guard-SOURCE-ONLY-NOT-QUALIFIED.json',GUARD_FAMILY_SHA)
    selector=module('_postguard_selected_new_guard',Q/'select_closed_metadata_guard_D7_v2.py',SELECTOR_SHA)
    op=h.pin(OVERRIDE);_,_,selected=selector.selected(OVERRIDE,op['sha256'])
    require(selected['native_prepared']==report['native_prepared']
        and selected['unlaunched_default_guard_packet']==report['exact_CPU_packet']
        and selected['default_guard_executed']is False,'Only the actual new selected guard override is eligible')
    authority,ap=metadata(m,h,Path(selected['closed_metadata_readiness_authority']['path']))
    require(ap==selected['closed_metadata_readiness_authority']and authority['metadata_closeout']==mc
        and authority['metadata_report']==mr and authority['native_prepared']==report['native_prepared'],
        'Fresh guard authority must come only from this new closed metadata result')
    packet,pp=metadata(m,h,Path(selected['selected_guard_packet']['path']))
    require(pp==selected['selected_guard_packet']and packet['native_prepared_manifest']==report['native_prepared']
        and packet['closed_metadata_readiness_authority']==ap,'Exact new four-job guard packet required')
    root=Path(packet['CPU_job']['path']).parent
    require(root==L/'actual-closed-metadata-guard-original01','Exact new guard namespace required')
    if closed_required:
        index,ip=metadata(m,h,root/'all-four-exact-native-guard-receipts.json')
        close,cp=metadata(m,h,Path(index['original_all4_CPU_closeout']['path']))
        require(index['status']=='PASS'and len(index['guards'])==4 and cp==index['original_all4_CPU_closeout']
            and close['actual_CPU_job']==packet['CPU_job']and close['actual_exit']==0
            and close['source']==selected['selected_guard_closer']and close['tests_run']==10
            and close['new_native_chain_tests']==4
            and close['all_six_descriptors_resources_argv_birth_units_cgroup_and_release_verified']is True,
            'Actual new original guard10tests/owned closure required')
        return report,op,selected,ip
    return report,op,selected,None


def prepare_review(m,h):
    selected=m.selected_sources(h)[1]
    report,op,override,gp=guard(m,h,True)
    base,bp=metadata(m,h,BASE)
    require(base['prepared_manifest']==report['native_prepared']and base['exact_four_guards']==gp
        and base['CPU_qualifications_closed']is base['original_attempts_unused']is True,
        'Actual new qualified configurations/readiness must precede review precommit')
    source=F/'prepare_deadline_independent_review_v4.py'
    p=module('_postguard_new_review_preparer',source,h.pin(source)['sha256'])
    rp=p.precommit(Path(report['native_prepared']['path']),Path(gp['path']),ST/'review-precommit-original01')
    packet=json.loads(h.checked(rp).read_bytes());driver=h.pin(F/'check_deadline_review_preparation_cpu_v3.py')
    require(not CPU.exists(),'One fresh review-preparation CPU only');CPU.mkdir(mode=0o700)
    values=[*selected,rp,report['native_prepared'],gp,bp,op,override['closed_metadata_readiness_authority'],
        h.pin(Q/'prepared-D7-new2s-closed-metadata-guard-SOURCE-ONLY-NOT-QUALIFIED.json'),
        h.pin(L/'finalize_window03_D7_readiness_v1.py'),h.pin(Path(__file__).resolve())]
    for case in packet['cases']:
        job=json.loads(h.checked(case['native_job']).read_bytes())
        values.extend([case['native_job'],case['native_config'],case['guard'],*job['inputs']])
    inputs=list({value['path']:value for value in values}.values())
    job=dict(schema='robotron-deadline-review-preparation-CPU-engineering-job-v1',
        unit='robotron-window03-D7-reviewprep-CPU-'+report['native_prepared']['sha256'][:16]+'-original01-20261029.service',
        output=str(CPU/'runtime'),source=driver,review_precommit=rp,original_attempt=1,no_retry=True,inputs=inputs)
    jp=h.put(CPU/'job.json',job)
    c=module('_postguard_new_review_CPU_controller',CONTROL,CONTROL_SHA)
    cfg=dict(unit=job['unit'],output=str(CPU/'execution-original01'),
        argv=['/usr/bin/python3','-I','-B',driver['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128',
            'TimeoutStopSec=5','SendSIGKILL=no'],observation_s=240,pins=[c.pin(value['path'])for value in [jp,*inputs]])
    cp=h.put(CPU/'controller-config.json',cfg);require(c.checked_config(cp['path'])==cfg,'Exact new reviewCPU ABI differs')
    return dict(review_precommit=rp,CPU_job=jp,config=cp,Root_original_controller_argv=[
        '/usr/bin/python3.12','-I','-B',str(CONTROL),'--execute','--config',cp['path'],
        '--expected-source-sha256',CONTROL_SHA],CPU_launched=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    for name in ('close-guards','prepare-readiness','prepare-review-precommit','close-review-CPU',
        'finalize-readiness','prepare-sequence'):g.add_argument('--'+name,action='store_true')
    p.add_argument('--R1-owner',type=Path);a=p.parse_args(argv)
    active=[key for key,value in vars(a).items()if key!='R1_owner'and value]
    if not active:print('PLAN_ONLY: no reads, imports, outputs, CPU, services, models or controls');return
    m,h=setup()
    if a.close_guards:
        _,op,_,_=guard(m,h)
        selector=module('_postguard_new_guard_close',Q/'select_closed_metadata_guard_D7_v2.py',SELECTOR_SHA)
        selector.close(OVERRIDE,op['sha256']);out=dict(guard_publication=h.pin(L/'actual-closed-metadata-guard-original01/all-four-exact-native-guard-receipts.json'))
    elif a.prepare_readiness:
        report,_,_,gp=guard(m,h,True)
        out=module('_postguard_new_resource_readiness',G/'tools/post_recovery_evaluation/review_round_study_readiness_v2.py',READINESS_SHA).review(
            Path(report['native_prepared']['path']),Path(gp['path']),BASE)
    elif a.prepare_review_precommit:out=prepare_review(m,h)
    elif a.close_review_CPU:
        report,_,_,gp=guard(m,h,True)
        review,rp=metadata(m,h,REVIEW)
        job,_=metadata(m,h,CPU/'job.json')
        require(review['native_prepared']==report['native_prepared']and review['CPU_guard_publication']==gp
            and job['review_precommit']==rp and job['source']==h.pin(F/'check_deadline_review_preparation_cpu_v3.py'),
            'Actual selected new reviewCPU/precommit binding required')
        out=module('_postguard_original_review_CPU_close',G/'tools/post_recovery_evaluation/close_engineering_cpu_scope_v2.py',CLOSE_REVIEW_SHA).close(CPU)
    elif a.finalize_readiness:
        guard(m,h,True)
        out=module('_postguard_new_finalizer',L/'finalize_window03_D7_readiness_v1.py',FINALIZER_SHA).finalize(
            BASE,REVIEW,CPU/'independent-original-CPU-scope-closeout.json',FINAL)
    else:
        require(a.R1_owner is not None,'Actual original closed R1 owner receipt required')
        guard(m,h,True)
        source=F/'sequence_deadline_study_v6.py'
        out=module('_postguard_existing_new_sequence',source,h.pin(source)['sha256']).prepare(
            REVIEW,a.R1_owner,ST/'owned-continuation-original01')
    print(json.dumps(out),flush=True)


if __name__=='__main__':main()
