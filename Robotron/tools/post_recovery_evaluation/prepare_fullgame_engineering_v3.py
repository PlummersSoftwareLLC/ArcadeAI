"""Build two inert actual-policy fullgame contexts; cannot authorize a cohort."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import secrets
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'logs/managed-learning-20261015/run-26'
I = BASE/'post-recovery-evaluation-isolation-original01-20261027'
HERE = Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def prepare(output):
    h=load('_fullgame_engineering_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    contract=load('_fullgame_engineering_contract',HERE/'fullgame_round_contract_v3.py')
    output=output.resolve();output.mkdir(mode=0o700)
    template=json.loads(contract.TEMPLATE.read_bytes())
    prior=I/'selected-candidate-receipt-census-study-original01/study'
    ref=json.loads((prior/'R1/job.json').read_bytes());candidate=json.loads((prior/'C1/job.json').read_bytes())
    health=load('_fullgame_prepare_health',HERE/'round_health_transport_v4.py')
    observer=load('_fullgame_prepare_raw',HERE/'fullgame_round_observer_v2.py')
    case=json.loads(h.checked(ref['main_binding']).read_bytes())
    deadline=time.monotonic()+15
    while True:
        try:
            case['initial_round']=json.loads((Path(case['round_root'])/'status.json').read_bytes())['round']
            baseline=observer.collect(health,case);health.validate(case,baseline);health.check_inputs(case,full=True);break
        except (ValueError,OSError):
            assert time.monotonic()<deadline
            time.sleep(.02)
    case['baseline_snapshot']=h.put(output/'baseline.raw.json',baseline)
    binding=h.put(output/'main-binding.json',case)
    policies={}
    for role,job,adoption in [('reference',ref,I/'reference-frozen-profile-v2-CPU-original01/independent-profile-adoption.json'),
                             ('candidate',candidate,I/'selected-candidate-frozen-profile-v2-CPU-original01/independent-profile-adoption.json')]:
        authority=h.pin(adoption)
        wrapper=h.put(output/(role+'-actual-CPU-authority.json'),dict(status='PASS',sha256=job['checkpoint']['sha256'],
            clocks=job['expected_policy_clocks'],independent_profile_adoption=authority,
            scope='Schema adapter to the existing independently closed strict CPU/profile proof; no new numeric run or gameplay claim'))
        policies[role]=dict(policy=job['checkpoint'],saved_clocks=job['expected_policy_clocks'],CPU_report=wrapper,original_CPU_readback=authority)
    pair=h.put(output/'ENGINEERING-ONLY-pair.json',dict(schema='robotron-recovered-round-fullgame-pair-v1',
        ordered_legs=['R1','C1','R2','C2'],minimum_complete_games_each=64,all32_slots=True,full_tails=True,
        no_candidate_pooling=True,no_scientific_retry=True,each_mean_ratio_min=[105,100],each_median_preserved=True,
        engineering_only=True,screen_assessment=None,reference_score_pool=None,**policies))
    observer_sources=dict(client=h.pin(HERE/'fullgame_round_observer_client_v4.py'),worker=h.pin(HERE/'fullgame_round_observer_v2.py'),
        health=h.pin(HERE/'round_health_transport_v4.py'),durability=h.pin(HERE/'durable_raw_writer.py'),interpreter=h.pin(Path('/usr/bin/python3').resolve()))
    protocol=h.put(output/'main-health-protocol.json',dict(schema='robotron-native-fullgame-round-main-health-protocol-v2',
        case=binding,raw_API_required=True,close_requires_final_sample=True,hot_max_gap_s=.5,initial_samples=100))
    recovery=h.pin(I/'post-outage-permanent-private-coordinator-restoration-original01.json')
    restored=json.loads(h.checked(recovery).read_bytes())['restored_lease']
    runtime=h.pin(HERE/'run_fullgame_rounds_v3.py');reviewer=h.pin(HERE/'review_fullgame_rounds_v3.py')
    family=h.put(output/'ENGINEERING-ONLY-source-family.json',dict(schema='robotron-recovered-round-fullgame-family-v2',
        runtime=runtime,leg_reviewer=reviewer,contract=h.pin(HERE/'fullgame_round_contract_v3.py'),main_observer=observer_sources,
        main_observer_reviewer=h.pin(HERE/'review_fullgame_round_observer_v3.py'),
        main_health_finalizer=ref['inputs'][next(n for n,x in enumerate(ref['inputs'])if x['sha256']=='64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee')],
        private_parent_job=h.pin(contract.TEMPLATE),current_main_binding=binding,lease_recovery_authority=recovery,
        engineering_only=True,native_launch_qualified=False,main_domain_hot_review=None))
    def pins(value):
        if isinstance(value,dict):
            if set(value)=={'path','sha256','bytes','identity'}:
                return [value]
            return [pin for item in value.values() for pin in pins(item)]
        if isinstance(value,list):return [pin for item in value for pin in pins(item)]
        return []
    rows=[]
    for leg,role in [('R1','reference'),('C1','candidate')]:
        directory=output/leg;directory.mkdir(mode=0o700)
        job=copy.deepcopy(template);job.pop('inputs')
        job.update(runtime=runtime,output=str(directory/'native-output-original01'),quality_leg=leg,
            quality_pair_precommit=pair,checkpoint=policies[role]['policy'],expected_policy_clocks=policies[role]['saved_clocks'],
            minimum_completed_games=50,confirmation_min_complete_games=64,engineering_only=True,
            source_family_manifest=family,main_health_protocol=protocol,main_binding=binding,lease=restored,
            training_experiment=case['experiment'],original_attempt=1,no_retry=True,
            prelaunch_CPU_closeout=str(directory/'fullgame-CPU-guards-original01/independent-closeout.json'))
        for name in ('sessions','connections'):
            job[name]={str(slot):secrets.token_hex(16) for slot in job['actor_slots']}
        values=[*pins(job),h.pin(Path(__file__).resolve()),h.pin(HERE/'fullgame_round_adaptation_delta_v3.json'),
                h.pin(HERE/'fullgame_round_contract_v3.py'),reviewer,*observer_sources.values(),
                h.pin(HERE/'review_fullgame_round_observer_v3.py'),case['baseline_snapshot'],recovery]
        job['inputs']=list({pin['path']:pin for pin in values}.values())
        jp=h.put(directory/'job.json',job)
        rows.append(dict(leg=leg,role=role,native_job=jp,runtime=runtime))
    return h.put(output/'ENGINEERING-ONLY-prepared-contexts.json',dict(schema='robotron-fullgame-two-context-engineering-v1',
        cases=rows,source=h.pin(Path(__file__).resolve()),pair=pair,family=family,main_binding=binding,
        native_source_derivation=contract.validate_derivation(runtime['path'],reviewer['path']),
        engineering_only=True,scientific_launch_qualified=False,quality_qualified=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-engineering',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.prepare_engineering:print(json.dumps(prepare(args.output)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
