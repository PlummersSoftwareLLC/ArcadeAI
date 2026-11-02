"""One original four-leg quality assessment; default is inert.

Each leg needs its own successful original native AND independent-review scope.
Only NEW R1+R2 games form the fixed reference. C1/C2 are never pooled. This
program publishes evidence; it never installs a policy or modifies main.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'tools/startup_policy_journal_proposal'
R=G/'logs/managed-learning-20261015/run-26'
ORDER=('R1','C1','R2','C2')
ROLES={'R1':'reference','C1':'candidate','R2':'reference','C2':'candidate'}
DIRECTORIES=('01-reference','02-candidate','03-reference','04-candidate')
PAIR_SHA='63000cf3441f085e8b297d9c589f19e7147c7213a07288e644c420089e497dc3'

def require(value,message):
    if not value:raise ValueError(message)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

SLOTS=tuple(range(4096,4128))
COHORT_SELECTION = dict(
    schema='robotron-fixed-slot64-selection-v1',
    strategy='first_two_known_starts_per_declared_slot', actor_slots=list(SLOTS),
    games_per_slot=2, expected_games=64, minimum_complete_games=50,
    outer_start_horizon_s=21540, whole_cohort_timeout_from_enter_s=21600,
    timestamp_close_role='outer_start_horizon',
    selector_source_sha256='494dcdbcb0ae30f95f4724435e6bf61c68bec3aa7fc3705e39636c0ba60ddbd0')


def metrics(scores):
    require(type(scores)is list and len(scores)>=50
        and all(type(value)is int and value>=0 for value in scores),'At least50 original integer scores required')
    ordered=sorted(scores);n=len(ordered)
    median_twice=2*ordered[n//2]if n%2 else ordered[n//2-1]+ordered[n//2]
    return dict(count=n,score_sum=sum(scores),mean=sum(scores)/n,median=median_twice/2,
        median_twice=median_twice,sd=statistics.stdev(scores),se=statistics.stdev(scores)/math.sqrt(n))

def assess_validated_cohorts(legs,reference_sha,candidate_sha):
    """Numerical decision only; the executable separately proves all receipts."""
    require(type(legs)is list and [leg['role']for leg in legs]==list(ORDER),'Exactly original R1/C1/R2/C2 order required')
    require(reference_sha!=candidate_sha,'Distinct fixed reference and candidate policies required')
    ids=set();native_ids=set();review_ids=set();summaries={};scores={}
    for leg in legs:
        role=leg['role'];cohort=leg['cohort']
        require(leg['evidence_verified']is True and leg['original_attempt']==1 and leg['no_retry']is True,
            'Each original leg must have independent actual runtime/review evidence')
        require(leg['policy_sha256']==(reference_sha if ROLES[role]=='reference'else candidate_sha),
            'Original leg policy role changed')
        for value,seen in [(tuple(leg['native_identity']),native_ids),(tuple(leg['review_identity']),review_ids)]:
            require(value not in seen,'Original leg native/review identity reused');seen.add(value)
        require(cohort['closed']is cohort['complete']is cohort['valid']is True
            and cohort['pending']==cohort['abandoned']==0
            and cohort['pending_ids']==cohort['abandoned_ids']==[],'Each original full tail must finish validly')
        rows=cohort['rows'];started=cohort['started_ids'];row_ids=[row['journal_game_id']for row in rows]
        require(type(cohort['count'])is int and cohort['count']==cohort['started']==len(rows)==len(started)==64
            and cohort['closed_by']=='slot_quota'
            and cohort['slot_admitted_counts']=={str(slot):2 for slot in SLOTS}
            and len(set(started))==len(started)and set(started)==set(row_ids)and len(set(row_ids))==len(rows),
            'Original admitted denominator lost a game or duplicated evidence')
        require(not ids.intersection(started),'A game was reused across independent cohorts');ids.update(started)
        require(cohort['started_actor_slots']==list(range(4096,4128))
            and {row['client_slot']for row in rows}==set(range(4096,4128)),
            'Every original quality leg requires all32 slots')
        require(all(row['complete']is row['eligible']is row['known_start']is True
            and row['excluded_reason']==''for row in rows),'An original quality game is incomplete/excluded')
        require(all(sum(row['client_slot']==slot for row in rows)==2 for slot in SLOTS),
            'Every original slot must contribute exactly its two selected full games')
        require(json.dumps(leg['cohort_selection'],sort_keys=True,separators=(',',':'),allow_nan=False)
            ==json.dumps(COHORT_SELECTION,sort_keys=True,separators=(',',':'),allow_nan=False),
            'Original leg count selection strategy/bounds changed')
        scores[role]=[row['score']for row in rows];summary=metrics(scores[role])
        for key in ('count','mean','median','sd','se'):
            require(type(cohort[key])in (int,float)and math.isfinite(cohort[key])
                and math.isclose(cohort[key],summary[key],rel_tol=1e-12,abs_tol=1e-9),
                'Saved cohort statistics differ from all original games')
        summaries[role]=summary
    reference=metrics(scores['R1']+scores['R2'])
    require(reference['score_sum']>0,'A positive fixed reference is required for a percentage improvement')
    candidates={}
    for role in ('C1','C2'):
        candidate=summaries[role]
        # Exact integer comparison avoids floating-point boundary changes.
        mean_pass=candidate['score_sum']*reference['count']*20>=reference['score_sum']*candidate['count']*21
        median_pass=candidate['median_twice']>=reference['median_twice']
        candidates[role]=dict(**candidate,mean_ratio=candidate['mean']/reference['mean'],
            median_ratio=(candidate['median']/reference['median']if reference['median']else None),
            mean_at_least_105_percent=mean_pass,median_preserved=median_pass,passed=mean_pass and median_pass)
    return dict(fixed_fresh_reference=reference,reference_roles=['R1','R2'],per_leg=summaries,
        independent_candidates=candidates,all_candidate_gates_passed=all(v['passed']for v in candidates.values()),
        candidate_pool_used=False,minimum_complete_games_per_leg=50,all32_each_leg=True,
        exact_mean_gate='candidate_sum * reference_count *20 >= reference_sum * candidate_count *21')

def execute(job_pin,h,reader):
    artifacts=[]
    def read(entry,as_json=True):
        result=reader.read_pin(entry,as_json=as_json);artifacts.append(entry);return result
    job=read(job_pin);directory=Path(job['campaign_directory']);output=Path(job['output'])
    require(job['schema']=='robotron-original-certified-quality32-campaign-assessment-job-v1'
        and directory.is_relative_to(R)and directory.is_absolute()and directory.resolve()==directory
        and output==directory/'independent-campaign-assessment-original01'and not output.exists(),
        'Fresh exact original campaign assessment output required')
    output.mkdir(mode=0o700)
    intent=h.put(output/'original-assessment-intent.json',dict(job=job_pin,source=h.pin(__file__),
        original_attempt=1,no_retry=True,created_unix_s=time.time()))
    report=dict(schema='robotron-original-certified-quality32-campaign-assessment-v1',valid=False,
        quality_qualified=False,promotion=False,main_runtime_changed=False,learning_speed_gain_verified=False,
        job=job_pin,intent=intent,artifacts=artifacts)
    try:
        require(PAIR_SHA!='0'*64 and PAIR_SHA!='3d3169064b25e933218e4d2dce2a3cd62ef5f3f5324354f362a9137671759650' and PAIR_SHA!='75baa58f45fc053041a90e2e5d5a66505c76137122ef647198e164e01bf5af5d'
            and PAIR_SHA not in ('7c74a3f8e27b3401404fe5d69bfbabd243f5cd57984b4f8f33087ba05a9a9f51','7862f46a6d42c51ef05fe8be2e97cdf29ad13717412b32451bc94417267bdba6','399f029598471553677c730b97c2ecc174b6fc1c8e295f72e1b319840926890a','24829cde7c4153795a335b9883a57e6c58ef4974879035245c8fbdff7ae16089','a8d442fb60bd5d4859e2c3683f9e91e410c71d33d6b0de3e3b25d87f17d05cb2')and job['pair']['sha256']==PAIR_SHA,
            'New later-policy fixed pair required; old failed case cannot be adopted')
        pair=read(job['pair']);readiness=read(job['launch_readiness_precommit'])
        require(readiness['schema']=='robotron-certified-quality32-new-launch-readiness-v1'
            and readiness['original_attempts_per_leg']==1 and readiness['no_retries']is True
            and readiness['quality_pair']==job['pair']and readiness['campaign_assessor']==h.pin(__file__),
            'Actual new original launch readiness/source binding differs')
        required={'leg_reviewer','native_runtime','native_controller','CPU_controller','native_closure'}
        require(set(job['sources'])==required,'Exact assessment dependency set required')
        modules={}
        for key,entry in job['sources'].items():
            read(entry,False);modules[key]=load('_final_quality_'+key,entry['path'])
        q=modules['leg_reviewer'];ctl=modules['CPU_controller'];rt=modules['native_closure']
        require(readiness['leg_reviewer']==job['sources']['leg_reviewer']
            and readiness['native_runtime']==job['sources']['native_runtime']
            and readiness['native_controller']==job['sources']['native_controller']
            and readiness['leg_CPU_controller']==job['sources']['CPU_controller'],'Selected campaign sources changed')
        require(job['legs']==[dict(role=role,directory=str(directory/name))for role,name in zip(ORDER,DIRECTORIES)],
            'Original fixed four leg directories/order required')
        legs=[];main_sources=None;case_groups=[]
        family=read(readiness['source_family_manifest'])
        require(family['runtime']==job['sources']['native_runtime'],'Original source family/runtime differs')
        for descriptor in job['legs']:
            role=descriptor['role'];root=Path(descriptor['directory'])
            native_pin=h.pin(root/'job.json');native_job=read(native_pin)
            require(native_job['quality_leg']==role and native_job['quality_pair_precommit']==job['pair']
                and native_job['runtime']==job['sources']['native_runtime'],'Original native leg binding differs')
            selected=pair[ROLES[role]]
            require(native_job['checkpoint']==selected['policy'],'Original selected policy changed')
            scope_pin=h.pin(root/'precommitted-acceptance-scope.json');scope=read(scope_pin)
            cfg_pin=h.pin(root/'controller-config.json');cfg=read(cfg_pin);q.validate_scope(native_job,native_pin,scope,cfg)
            native_result_pin=h.pin(root/'diagnostic-output-original01/result.json');native=read(native_result_pin)
            policy,cohort=q.validate_runtime_result(native,native_job)
            require(native_job['output']==str(root/'diagnostic-output-original01'),'Original native output escaped')
            controller_pin=h.pin(root/'controller-original-result.json');controller=read(controller_pin)
            owner_pin=h.pin(root/'execution-original01/root-original-identity.json');owner=read(owner_pin)
            require(controller['actual_exit']==0 and controller['original_attempt']==1 and controller['no_retry']is True,
                'An original native controller failed or retried')
            closure=read(controller['closure']);fields=rt.archived_closure(closure,owner,read,exit_zero=True)
            q.validate_native_fields(fields,cfg,owner,rt.duration_seconds)
            review_job_pin=h.pin(root/'independent-review-job.json');review_job=read(review_job_pin)
            require(review_job['native_job']==native_pin and review_job['controller_config']==cfg_pin
                and review_job['acceptance']==scope_pin and review_job['sources']['runtime']==native_job['runtime'],
                'Independent original review selected different native evidence')
            cpucfg_name='independent-review-controller-config.json'
            cpucfg_pin=h.pin(root/cpucfg_name);cpucfg=read(cpucfg_pin)
            ctl.checked_config(cpucfg_pin['path'])
            expected_argv=['/usr/bin/python3.12','-I','-B',job['sources']['leg_reviewer']['path'],
                '--observe','--job',review_job_pin['path'],'--job-sha256',review_job_pin['sha256'],
                '--expected-source-sha256',job['sources']['leg_reviewer']['sha256']]
            require(cpucfg['argv']==expected_argv,'Actual original independent reviewer argv/source differs')
            cpu_result_pin=h.pin(root/'independent-review-controller-original-result.json');cpu=read(cpu_result_pin)
            cpu_owner_pin=h.pin(root/'independent-review-execution-original01/root-original-identity.json');cpu_owner=read(cpu_owner_pin)
            require(cpu['actual_exit']==0 and cpu['original_attempt']==1 and cpu['no_retry']is True,
                'An original independent reviewer/controller failed or retried')
            cpu_closure=read(cpu['closure']);cpu_fields=rt.archived_closure(cpu_closure,cpu_owner,read,exit_zero=True)
            require(' '.join(expected_argv)+' ; ignore_errors=no ;'in cpu_fields['ExecStart']
                and rt.duration_seconds(cpu_fields['CPUQuotaPerSecUSec'])==2
                and cpu_fields['MemoryMax']==str(4<<30)and cpu_fields['MemorySwapMax']=='0'
                and rt.duration_seconds(cpu_fields['RuntimeMaxUSec'])==1980 and cpu_fields['TasksMax']=='128'
                and rt.duration_seconds(cpu_fields['TimeoutStopUSec'])==5 and cpu_fields['SendSIGKILL']=='no'
                and cpu_fields['Restart']=='no','Original independent-review resources differ')
            for identity in (owner,cpu_owner):
                require(birth(identity['pid'])!=identity['starttime_ticks'],'An original scoped process remains')
                for unit in (identity['unit'],identity['timer']):
                    require(ctl.show(unit)['LoadState']=='not-found','An original scoped unit remains')
                    require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists(),
                        'An original scoped cgroup remains')
            review_pin=h.pin(root/'independent-quality-leg-review-original01/review.json');leg=read(review_pin)
            require(leg['schema']=='robotron-original-quota64-independent-cohort-review-v1'
                and leg['valid']is leg['full_game_score_verified']is True
                and leg['quality_qualified']is leg['promotion']is False
                and leg['quality_leg']==role and leg['quality_pair_precommit']==job['pair']
                and leg['minimum_quality_complete_games']==50 and leg['outer_start_horizon_s']==21540
                and leg['expected_selected_games']==64
                and leg['review_job']==review_job_pin and leg['original_native_job']==native_pin
                and leg['original_result']==native_result_pin and leg['original_owner']==owner_pin
                and leg['original_controller_result']==controller_pin and leg['original_closure']==controller['closure']
                and leg['policy']==policy and leg['actual_runtime_exit']==leg['actual_controller_exit']==0,
                'An independently valid original quality review is missing or points to another case')
            for key in ('all_admitted_games_retained','all6_original_descriptors_verified',
                    'exact_owned_births_unit_timer_cgroup_absent','private_GPU_ports_and_coordinator_released',
                    'original_outputs_sealed_after_writer_exit'):require(leg[key]is True,'Original quality evidence incomplete: '+key)
            require(type(leg['all32_actual_MAME_exits'])is int and leg['all32_actual_MAME_exits']==0,
                'Original MAME exits missing')
            for entry in leg['artifacts']:read(entry,False)
            require(leg['source_family_manifest']==readiness['source_family_manifest']
                and native_job['source_family_manifest']==readiness['source_family_manifest']
                and leg['main_health_case_roles']==list(ORDER[:len(legs)+1])
                and leg['main_health_engine']==readiness['main_health_sources']['full_health_engine'],
                'Original full raw-health case/family/role prefix differs')
            transport=leg['main_health_raw_replay']['transport']
            require(transport['case_groups']==case_groups+transport['groups'],
                'Original raw-reviewed transport budget was reset, duplicated or changed between legs')
            case_groups=transport['case_groups']
            stats=leg['original_games']['statistics'];recomputed=metrics([row['score']for row in cohort['rows']])
            require(stats['count']==recomputed['count']and stats['score_sum']==recomputed['score_sum']
                and set(leg['original_games']['admitted_ids'])==set(cohort['started_ids']),
                'Original independent journal denominator/statistics differ')
            for name,entry in native['journal'].items():
                h.checked(entry)
                require(entry['sha256']==leg['original_games']['original_payload_sha256'][name],
                    'Original raw game/start/life payload changed')
            main=read(native_job['main_binding'])
            if main_sources is None:main_sources=main['held_hashes']
            require(main['held_hashes']==main_sources and len(main_sources)==197,'Held main sources changed between legs')
            legs.append(dict(role=role,policy_sha256=policy['checkpoint_sha256'],cohort=cohort,
                cohort_selection=leg['cohort_selection'],
                evidence_verified=True,original_attempt=1,no_retry=True,
                native_identity=[owner['pid'],owner['starttime_ticks'],owner['invocation_id']],
                review_identity=[cpu_owner['pid'],cpu_owner['starttime_ticks'],cpu_owner['invocation_id']],
                independent_review=review_pin))
        health_modules={key:load('_campaign_health_'+key,h.checked(readiness['main_health_sources'][key]))
            for key in ('primitives','transport','proc_repeat','mixed_transport')}
        case_budget=health_modules['mixed_transport'].closed_budget(health_modules['primitives'],
            health_modules['transport'],health_modules['proc_repeat'],case_groups)
        require(case_budget==leg['main_health_raw_replay']['transport']['budget'],
                'Final actual four-leg transport budget differs from the original closed C2 prefix')
        report.update(main_health_case_budget=case_budget,source_family_manifest=readiness['source_family_manifest'])
        decision=assess_validated_cohorts(legs,pair['reference']['policy']['sha256'],pair['candidate']['policy']['sha256'])
        for selected in ('reference','candidate'):h.checked(pair[selected]['policy'])
        for path,digest in main_sources.items():require(h.pin(path)['sha256']==digest,'Held source changed after the campaign')
        require('torch'not in sys.modules,'Independent campaign assessment imported numerical runtime')
        report.update(valid=True,status='ORIGINAL_FOUR_LEG_QUALITY_ASSESSMENT_COMPLETE',decision=decision,
            quality_qualified=decision['all_candidate_gates_passed'],fixed_input_pair=job['pair'],
            original_leg_reviews=[leg['independent_review']for leg in legs],all_original_runtime_and_review_scopes_verified=True)
    except Exception as error:
        report.update(status='ORIGINAL_CAMPAIGN_ASSESSMENT_INVALID_NO_RETRY',error=repr(error),traceback=traceback.format_exc())
    report['ended_unix_s']=time.time();pin=h.put(output/'assessment.json',report)
    print(json.dumps(dict(assessment=pin,valid=report['valid'],quality_qualified=report['quality_qualified'])),flush=True)
    return 0 if report['valid']else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job')
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    h=load('_original_campaign_helpers',B/'run_full_policy_startup_v3.py')
    require(h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','Helper changed')
    require(h.pin(__file__)['sha256']==args.source_sha256,'Original assessment source differs')
    pin=h.pin(args.job);require(pin['sha256']==args.job_sha256,'Original assessment job differs')
    reader_path=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(h.pin(reader_path)['sha256']=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','Reader changed')
    reader=load('_original_campaign_immutable_reader',reader_path)
    return execute(pin,h,reader)

if __name__=='__main__':sys.exit(main())
