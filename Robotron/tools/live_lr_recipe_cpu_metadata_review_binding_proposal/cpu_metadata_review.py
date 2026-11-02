"""Exact known original CPU metadata-failure review; definitions only.

No numerical load, model access, runtime query, source mutation or rerun.
All inputs are authenticated closed metadata/source through injected readers.
"""
import json
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=ROOT/'logs/managed-learning-20261015/run-26'
D=RUN/'LR25-continuation-candidate-CPU-original01-root-execution-20261018'
SCHEMA='robotron-root-known-LR25-CPU-job-fingerprint-metadata-review-v1'
STATUS='PASS_NUMERICAL_CPU0_WITH_ORIGINAL_WRAPPER1_FAIL_PRESERVED'
BAD_STATEMENT="assert report_value is not None and report_value['job_file'] == job_pin"
KNOWN={
 'original_execution':(D/'CPU-execution.json','3bd089f9419e7846a005536111b2c61c5e9b572a6e44491c0d0d34f6bbffd23c'),
 'original_release':(D/'root-original-CPU-result-and-owned-release.json','cc2850f8a85fa6cc03c6bc1d3fb817d601b0cf0974a85c16c776d86b60ca304f'),
 'job':(RUN/'LR25-continuation-capture-trial01-20261018/candidate-CPU-job.json','e187d06bb2e326906616026bdc23598dc53c02a5b5b0de18169291e5d3cd35a7'),
 'report':(D/'candidate-CPU-report-readonly.json','c9f04209979e0574d0ae1d8f422c5bf75080d251aaf169934460c33dd0f5b2e9'),
 'completion':(D/'CPU-completion.json','ff1ccb820dfb4d10ebea7e2b081ad774996acf2d1c5d971e4c7cc5e0468e2f05'),
 'launcher_source':(ROOT/'tools/live_lr_recipe_cpu_launcher_proposal/run_candidate_cpu_reviewed2.py','d203f21066af5f090b93d6eab25f9bf40b1c3df119b5ece9b4281b2c305faf77'),
 'root_recheck':(RUN/'LR25-continuation-original01-root-preparation-20261018/root-closed-CPU-numeric0-PASS-metadata-recheck-original-wrapper1-FAIL-preserved.json','ba7be9fd6a2eb75a5f40f7d5c5741f445b8f9174d1ee2ff8f0d0aaaa31be4125')}
IDENTITY={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}
ROLES={'numerical_and_original_lifecycle':{'original_execution','original_release','job','report','completion'},
       'known_launcher_metadata_failure':{'original_execution','original_release','launcher_source'}}
SCOPES={'numerical_and_original_lifecycle':'Closed facts only; reviewer authored numerical149, not independent implementation signoff.',
        'known_launcher_metadata_failure':'Closed facts and known bad assertion only; reviewer authored launcherd203, not independent implementation signoff.'}
CHECKS={'no_numeric_rerun','no_model_or_replay_reads','original_records_unchanged',
        'root_review_does_not_override_gates','known_first_bad_assertion_only'}


def require(value,message):
    if not value:raise ValueError(message)


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def fullpin(value,label):
    require(type(value) is dict and set(value)=={'path','sha256','bytes','identity'} and
        type(value['path']) is str and Path(value['path']).is_absolute() and '..' not in Path(value['path']).parts and
        type(value['sha256']) is str and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256']) and
        type(value['bytes']) is int and 0<value['bytes']<=4<<20 and type(value['identity']) is dict and
        set(value['identity'])==IDENTITY and value['identity']['bytes']==value['bytes'] and
        all(type(value['identity'][k]) is int for k in IDENTITY-{'mode'}) and
        value['identity']['mode']=='0o444' and value['identity']['nlink']==1,
        'Exact bounded readonly FULL8 required: '+label)
    return value


def digests(value):
    # Bounded parsed JSON only, not referent following. Receipts may use their
    # authentic field layouts; require their actual bytes to cover these SHAs.
    pending=[value];found=set();count=0
    while pending:
        current=pending.pop();count+=1
        require(count<=100000,'Independent receipt structure exceeds bound')
        if type(current) is dict:pending.extend(current.values())
        elif type(current) is list:pending.extend(current)
        elif type(current) is str and len(current)==64 and all(c in '0123456789abcdef' for c in current):found.add(current)
    return found


def verify_known_review(execution,job_pin,report_pin,completion_pin,completion,reader,check_cpu,source_reader,validator_pin):
    require('metadata_review' in execution,'Original FAIL needs an explicit known-failure review')
    review_pin=fullpin(execution['metadata_review'],'metadata_review');review=reader(review_pin)
    fields={'schema','status',*KNOWN,'validator_source','original_wrapper','job_file_identity_join','checks','independent_peers'}
    require(type(review) is dict and set(review)==fields and review['schema']==SCHEMA and review['status']==STATUS and
        len(encoded(review).encode())<=128<<10,'Exact bounded known-failure review schema required')
    for name,(path,sha) in KNOWN.items():
        p=fullpin(review[name],name)
        require(p['path']==str(path) and p['sha256']==sha,'Unrelated original artifact is never reviewable here: '+name)
    require(fullpin(review['validator_source'],'validator_source')==validator_pin,'Exact selected review-validator source required')
    require(encoded(review['original_wrapper'])==encoded(dict(exit_code=1,release_status='FAIL',semantic_error='AssertionError()',preserved=True)) and
        type(review['checks']) is dict and set(review['checks'])==CHECKS and all(v is True for v in review['checks'].values()),
        'Original wrapper1/FAIL must remain factual; no numerical rerun/override/model reads')
    original=reader(review['original_execution']);release=reader(review['original_release'])
    require(encoded({k:v for k,v in execution.items() if k!='metadata_review'})==encoded(original) and
        set(execution)==set(original)|{'metadata_review'} and execution['release_receipt']==review['original_release'] and
        job_pin==review['job']==original['job'] and report_pin==review['report']==original['report'] and
        completion_pin==review['completion']==original['completion'],
        'Augmented execution must be an exact copy of the immutable original plus one review PIN')
    require(release['schema']=='robotron-root-captured-candidate-CPU-original-release-v1' and release['status']=='FAIL' and
        release['semantic_error']=='AssertionError()' and release['original_exec_code']==1 and release['original_exit']==0 and
        release['original_result']=='success' and release['known_original_absent'] is True and release['no_numeric_rerun'] is True and
        release['quality_acceptance'] is False and release['CPU_report']==report_pin and release['cpu_job']==job_pin,
        'Only this native0/reportPASS/original-wrapper metadata failure can be reviewed')
    job=reader(job_pin);report=reader(report_pin);actual_completion=reader(completion_pin)
    require(encoded(actual_completion)==encoded(completion) and completion['exit_code']==0 and
        report['status']=='PASS' and report['script']['sha256']=='14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5' and
        job['source_control_context']['held_recipe_context']['learning_control_lr_scale']==.25 and
        report['adam_group']['lr']==1.25e-5,'Original genuine149 numerical .25 PASS/native0 required')
    flat=report['job_file'];expected=dict(path=job_pin['path'],sha256=job_pin['sha256'],**job_pin['identity'])
    require(type(flat) is dict and set(flat)=={'path','sha256',*IDENTITY} and encoded(flat)==encoded(expected) and
        encoded(flat)!=encoded(job_pin) and
        encoded(review['job_file_identity_join'])==encoded(dict(report_job_file=flat,root_job_file=job_pin,exact=True)),
        'Actual flat10 and nested FULL8 identities must join exactly without normalization')
    source=source_reader(review['launcher_source'])
    require(type(source) is bytes and source.count(BAD_STATEMENT.encode())==1,'Exact original first bad metadata statement required')
    recheck=reader(review['root_recheck'])
    require(recheck['schema']=='robotron-root-closed-original-CPU-metadata-recheck-with-wrapper-failure-preserved-v1' and
        all(recheck[k]==review[name] for k,name in (('job','job'),('report','report'),('completion','completion'),
            ('original_execution','original_execution'),('original_failed_release','original_release'))) and
        recheck['original_numeric_exit']==0 and recheck['original_numeric_report_status']=='PASS' and
        recheck['original_wrapper_exit']==1 and recheck['original_wrapper_release_status']=='FAIL' and
        recheck['error_is_known_flat_vs_nested_job_fingerprint_equality'] is True and recheck['exact_flat10_matches_full8_identity'] is True and
        all(recheck[k] is False for k in ('raw_report_changed','raw_execution_changed','numeric_rerun','quality_qualified','model_structure_changed','model_or_replay_bodies_opened')) and
        all(recheck[k]=='PASS' for k in ('root_metadata_check_cpu','root_metadata_check_CPU_command','root_metadata_terminal')),
        'Authentic closed root recheck must preserve the original failure and all numerical gates')
    peers=review['independent_peers']
    require(type(peers) is list and len(peers)==2 and {p['role'] for p in peers}==set(ROLES),
        'Both independent numerical/lifecycle and exact known-source diagnosis reviews required')
    require(len({p['receipt']['sha256'] for p in peers})==2,'Distinct independent peer receipts required')
    for item in peers:
        require(type(item) is dict and set(item)=={'role','receipt','covered_artifact_sha256','authorship_scope'} and item['authorship_scope']==SCOPES[item['role']],'Exact peer scope/PIN/coverage required')
        peer=reader(fullpin(item['receipt'],'independent_peer'));coverage={key:KNOWN[key][1] for key in ROLES[item['role']]}
        require(type(item['covered_artifact_sha256']) is dict and item['covered_artifact_sha256']==coverage and
            type(peer) is dict and type(peer.get('status')) is str and peer['status'].startswith('PASS') and
            len(encoded(peer).encode())<=4<<20 and set(coverage.values())<=digests(peer),
            'Independent receipt actual bytes must cover this exact original attempt and PASS scope')
    source=job['source'];name=Path(source['path']).name
    require(name.endswith('.pt'),'Original selected candidate descriptor required')
    candidate=dict(tag=name[:-3],path=source['path'],sha256=source['sha256'],bytes=source['bytes'])
    # The existing metadata verifier remains authoritative; root review never
    # substitutes a PASS flag for finite/Adam/scaler/phase/recipe/source gates.
    check_cpu(job,report,completion,candidate)
    return True
