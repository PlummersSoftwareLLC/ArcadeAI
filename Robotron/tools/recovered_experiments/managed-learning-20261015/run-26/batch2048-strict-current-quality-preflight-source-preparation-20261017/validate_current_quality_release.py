"""Pinned historical quality closure gate. No runtime or activation authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time

RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
RELEASE = dict(path=str(RUN/'postRecoveryCE587M-quality-final-gates-and-owned-closure-root-20261017/root-explicit-current-quality-source-freeze-release.json'),
    sha256='4009346f36fac72f882b4dca8031d5e3a6ad9312537ea228290210aca9c05748',bytes=2693)
BINDINGS_SHA = '01f76c031aabba5bb0558363538e24f9e437193826a2169d6dd1371baf61b1af'
BINDINGS_BYTES = 11815
OWNER = dict(pid=1279628,starttime_ticks=35401858,invocation_id='b453bedb51994740b8b23360743ce960',
    cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-quality-CE543M-vs-postRecoveryCE-candidate02-20261017.service')
MAIN = (1247463,35298775)
SERVICE = 'robotron-quality-CE543M-vs-postRecoveryCE-candidate02-20261017.service'
TIMER = SERVICE.removesuffix('.service')+'.timer'
TIMER_INV = '576892a980ce47049a7be7e0ce4aa502'
EXITS = [2,0,2,0]
LIMIT = 2 << 20


def require(value,message):
    if not value:raise ValueError(message)


def triple(pin):
    require(isinstance(pin,dict) and {'path','sha256','bytes'}<=set(pin),'Bound metadata PIN required')
    require(isinstance(pin['path'],str) and Path(pin['path']).is_absolute() and
        isinstance(pin['sha256'],str) and len(pin['sha256'])==64 and
        all(c in '0123456789abcdef' for c in pin['sha256']) and
        type(pin['bytes']) is int and 0<pin['bytes']<=LIMIT,'Malformed metadata PIN')
    return {k:pin[k] for k in ('path','sha256','bytes')}


def same(left,right,message):
    require(triple(left)==triple(right),message)


def _bytes(pin):
    expected=triple(pin);p=Path(expected['path']);require(p.suffix!='.pt','No model body access')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        s=os.fstat(fd);signature=lambda z:(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_nlink)
        require(stat.S_ISREG(s.st_mode) and s.st_uid==1001 and s.st_nlink==1 and
            stat.S_IMODE(s.st_mode)==0o444 and s.st_size==expected['bytes'],'Owned single-link0444 metadata required')
        with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(LIMIT+1)
        require(len(raw)==s.st_size and signature(s)==signature(os.fstat(fd))==signature(p.lstat()),'Metadata changed while reading')
        require(hashlib.sha256(raw).hexdigest()==expected['sha256'],'Metadata SHA differs: '+str(p))
        if 'identity' in pin:
            require(pin['identity']==dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink),
                'Supplied full metadata identity differs')
    finally:os.close(fd)
    return raw


def _read(pin):
    return json.loads(_bytes(pin),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite metadata: '+x)))


def _integer(value,expected):
    return type(value) is int and value==expected


def _vector(value):
    return isinstance(value,list) and all(type(x) is int for x in value) and value==EXITS


def validate(input_release_pin):
    """Validate only the completed current campaign; new trial02 remains unbound."""
    same(input_release_pin,RELEASE,'Wrong current campaign release (historical winner is not current authority)')
    binding_path=Path(__file__).with_name('bindings.json')
    fixed=_read(dict(path=str(binding_path),sha256=BINDINGS_SHA,bytes=BINDINGS_BYTES))
    seen=[]
    def read(pin):
        value=_read(pin);seen.append(triple(pin));return value
    release=read(input_release_pin)
    require(release['schema']=='robotron-current-quality-source-freeze-release-v1' and
        release['status']=='RELEASED_AFTER_VALID_NOT_IMPROVED_CURRENT_CAMPAIGN' and
        release['source_freeze_released'] is True and release['owned_cleanup_complete'] is True and
        release['narrow_reference_dispositions_preserved'] is True,'Current explicit release predicates missing')
    for name in ('plan','binding_job','all4_acceptance','independent_all4_acceptance','actual_owned_closure'):
        same(release[name],fixed[name],'Wrong current release binding: '+name)
    read(fixed['plan']);read(fixed['binding_job'])
    require(release['original_controller']==OWNER and _integer(release['original_controller_exit'],0)
        and _vector(release['original_audit_exits_preserved']) and
        _integer(release['original_R1_supplemental_exit_separate'],0),'Original controller/audit history differs')
    require(release['native_outcome']=='not_improved' and release['qualified_improvement'] is False and
        release['candidate_promoted'] is False and release['protected543_preserved'] is True,
        'Valid non-improvement must remain distinct from promotion')
    closure=read(fixed['actual_owned_closure']);acceptance=read(fixed['all4_acceptance'])
    peer=read(fixed['independent_all4_acceptance']);archive=read(fixed['parent_archive'])
    require(closure['schema']=='robotron-current-quality-actual-owned-closure-v1' and
        closure['status']=='PASS_CURRENT_QUALITY_OWNED_CLOSURE' and
        closure['owned_cleanup_complete'] is True and closure['source_freeze_released'] is False,
        'Actual owned closure missing or conflated with separate root release')
    for value in (closure,acceptance):
        require(value['original_controller']==OWNER and _integer(value['original_controller_exit'],0) and
            _vector(value['original_audit_exits_preserved']) and _integer(value['original_R1_supplemental_exit_separate'],0),
            'Closure/acceptance original identity or exit history differs')
        same(value['plan'],fixed['plan'],'Wrong current plan');same(value['binding_job'],fixed['binding_job'],'Wrong current binding')
        require(value['native_outcome']=='not_improved' and value['candidate_promoted'] is False and
            value['protected543_preserved'] is True,'Closure/acceptance outcome differs')
    for name in ('original69_absent','all_seven_original_audit_capture_verifier_units_released',
        'parent_and_timer_not_found','quality_cgroup_empty_or_absent','main192_healthy','GPU0_free','main_sole_GPU1'):
        require(closure[name] is True,'Missing actual closure resource predicate: '+name)
    for name in ('all4_acceptance','independent_all4_acceptance','before_resources','after_resources',
        'exact_parent_timer_release','resource_checker_manifest','frozen_file_maps_unchanged'):
        same(closure[name],fixed[name],'Wrong owned closure evidence: '+name)
    same(closure['original_controller_terminal'],fixed['parent_archive'],'Wrong original controller archive')
    same(acceptance['original_controller_terminal_before_release'],fixed['parent_archive'],'Wrong accepted parent archive')
    require(archive['original_controller']==OWNER and _integer(archive['original_exec_main_code'],1)
        and _integer(archive['original_exec_main_status'],0) and archive['original_result']=='success'
        and _integer(archive['original_nrestarts'],0) and _integer(archive['original_current_main_pid'],0),
        'Original retained terminal was not actual original0')
    require(archive['unit']==SERVICE and archive['timer']==TIMER and
        archive['original_timer_invocation_id']==TIMER_INV,'Original service/timer lineage differs')
    require(acceptance['schema']=='robotron-current-quality-all4-acceptance-and-final-gates-v1' and
        acceptance['status']=='ACCEPTED_VALID_CAMPAIGN_NOT_IMPROVED' and acceptance['all_four_accepted_valid'] is True
        and acceptance['qualified_improvement'] is False,'Actual all-four validity acceptance missing')
    require(peer['all4_root_acceptance_lineage_verified'] is True and _vector(peer['original_audit_exits_preserved'])
        and _integer(peer['R1_supplemental_exit_separate'],0) and peer['native_outcome']=='not_improved',
        'Independent all-four saved review differs')
    require([x['index'] for x in acceptance['legs']]==[1,2,3,4] and
        [x['role'] for x in acceptance['legs']]==['reference','candidate','reference','candidate'],'Actual ordered four legs missing')
    for leg in acceptance['legs']:
        index=leg['index'];require(leg['accepted_cohort_valid'] is True and
            _integer(leg['original_audit_exit'],EXITS[index-1]),'Original audit exit/accepted cohort changed')
        for name in ('original_audit','root_leg_acceptance','independent_original_rows_review','native_receipt'):
            same(leg[name],fixed['legs'][index-1][name],'Wrong actual leg evidence: '+name)
        audit=read(leg['original_audit']);disposition=read(leg['root_leg_acceptance']);read(leg['independent_original_rows_review'])
        require(audit['leg']==index and audit['valid'] is (False if index in (1,3) else True),
            'Original audit valid/failed status was relabeled')
        if index==1:
            require(disposition['accepted_cohort_valid'] is True and _integer(disposition['original_audit_exit_preserved'],2)
                and _integer(disposition['original_evaluator_exit'],0),'R1 original failed audit disposition missing')
            same(disposition['supplemental_exit0_archive_release'],fixed['R1_supplemental_release'],'R1 supplemental proof differs')
            supplemental=read(fixed['R1_supplemental_release'])
            require(_integer(supplemental['supplemental_original_exit'],0) and
                supplemental['supplemental_original_starttime_ticks'] is None and
                _integer(supplemental['original_failed_audit_exit_preserved'],2) and
                supplemental['original_archived_before_release'] is True and supplemental['unit_released'] is True,
                'R1 supplemental exit was substituted for original or unknown ticks invented')
        elif index==3:
            require(disposition['accepted_cohort_valid'] is True and _integer(disposition['original_audit_exit'],2) and
                disposition['original_audit_valid'] is False and disposition['original_failed_report_preserved'] is True
                and disposition['evaluator_or_cohort_or_auditor_retried'] is False and
                disposition['auditor_or_scoring_source_changed'] is False,'R2 narrow original2 disposition missing')
            same(disposition['original_audit'],leg['original_audit'],'R2 failed report pin differs')
        # Native originals are0664: consume original root byte-exact0444 archives,
        # preserving the acceptance's original path/SHA/bytes rather than chmodding it.
        tag=('01-reference','02-candidate','03-reference','04-candidate')[index-1]
        pair=archive['native_artifacts'][tag];same(pair['original'],leg['native_receipt'],'Native original receipt differs')
        require(pair['archived_exact_bytes']['sha256']==leg['native_receipt']['sha256'] and
            pair['archived_exact_bytes']['bytes']==leg['native_receipt']['bytes'],'Native archive is not byte-identical')
        native=read(pair['archived_exact_bytes'])
        require(native['valid'] is True and native['complete'] is True and native['active'] is False and
            _integer(native['pending'],0) and _integer(native['abandoned'],0),'Native full-tail completion missing')
    inventory=read(fixed['inventory']);baseline=read(fixed['runtime_baseline'])
    original69=[(OWNER['pid'],OWNER['starttime_ticks'])]
    for leg in inventory['legs']:original69.extend((x['pid'],x['starttime_ticks']) for x in [leg['evaluator'],*leg['actors']])
    require(len(original69)==len(set(original69))==69,'Original69 proof inventory differs')
    resource_times={}
    for phase in ('before','after'):
        resources=read(fixed[phase+'_resources'])
        require(resources['status']=='PASS_CURRENT_CAMPAIGN_RESOURCE_OBSERVATION' and resources['phase']==phase
            and resources['resource_pass'] is True and resources['release_actions'] is False,
            'Actual resource observation missing')
        resource_times[phase]=(resources['started_unix_s'],resources['ended_unix_s'])
        same(resources['checker_source'],fixed['resource_checker_source'],'Unselected resource checker source')
        observations=resources['observations'];absent=observations['original69_absence']
        require(len(absent)==69 and [(x['pid'],x['expected_start']) for x in absent]==original69 and
            all(x['observed_start']!=x['expected_start'] for x in absent),'Original69 absence differs')
        group=observations['original_cgroup'];require(group['cgroup']==OWNER['cgroup'] and
            (group.get('absent') is True or group.get('empty') is True),'Owned quality cgroup remains')
        for name in ('GPU0_free','main_sole_GPU1','lease_unheld','port9999_unused','no_private_tmpfs_or_helpers'):
            require(observations[name] is True,'Resource predicate missing: '+name)
        require((observations['main']['pid'],observations['main']['starttime_ticks'])==MAIN and
            len(observations['actors'])==192 and {(x['pid'],x['starttime_ticks']) for x in observations['actors']}==
                {(x['pid'],x['starttime_ticks']) for x in baseline['actors']},'Historical main192 identity differs')
        api=observations['API_summary'];require(_integer(api['client_count'],192) and api['training_enabled'] is True
            and api['graphs_ready'] is True and _integer(api['capture_count'],128) and
            _integer(api['validation_replay_count'],640) and _integer(api['four_pipeline_errors'],0),
            'Saved main192 resource health differs')
        require(len(observations['helper_releases'])==7 and all(
            x['observed_start'] is None if x['expected_start'] is None else x['observed_start']!=x['expected_start']
            for x in observations['helper_releases']),'Saved helper absence differs')
    execution=read(fixed['exact_parent_timer_release'])
    require(execution['status']=='PASS_EXACT_ORIGINAL_PARENT_TIMER_RELEASE' and execution['exact_units_released'] is True
        and execution['original_controller_invocation_id']==OWNER['invocation_id'] and
        execution['original_timer_invocation_id']==TIMER_INV and execution['service']==SERVICE and execution['timer']==TIMER and
        _integer(execution['original_exec_main_code'],1) and _integer(execution['original_exec_main_status'],0),
        'Actual exact original parent/timer release missing')
    same(execution['original_controller_archive'],fixed['parent_archive'],'Wrong released original archive')
    same(execution['before_resources'],fixed['before_resources'],'Release did not bind original before-resources')
    require(archive['observed_unix_s']<=resource_times['before'][0]<=resource_times['before'][1]
        <=execution['started_unix_s']<=execution['ended_unix_s']<=resource_times['after'][0]
        <=resource_times['after'][1]<=closure['observed_unix_s']<=release['released_unix_s'],
        'Archive/resource/release chronology differs')
    stops=[x for x in execution['commands'] if x['argv'][:3]==['systemctl','--user','stop']]
    require([x['argv'][-1] for x in stops]==[execution['timer'],execution['service']] and
        all(_integer(x['returncode'],0) for x in stops),'Actual timer-first exact stop0/0 evidence differs')
    maps=read(fixed['frozen_file_maps_unchanged'])
    require(maps['counts']==dict(baseline_source=61,baseline_control=2,baseline_unit=3,
        native_evaluator_source=12,native_execution_source=4) and len(maps['entries'])==82 and maps['mismatches']==[]
        and all(x['matches'] is True and x['actual_sha256']==x['expected_sha256'] for x in maps['entries']),
        'Terminal frozen file maps differ')
    for name in ('guard_manifest','control_manifest'):
        manifest=read(fixed[name]);files=manifest['files'];files=files.values() if isinstance(files,dict) else files
        for pin in files:_bytes(pin)
    read(fixed['lineage_review'])
    return dict(schema='robotron-strict-current-quality-preparation-v1',status='PASS_STRICT_CURRENT_QUALITY_PREPARATION',
        release=triple(input_release_pin),closure=fixed['actual_owned_closure'],all4_acceptance=fixed['all4_acceptance'],
        independent_all4_acceptance=fixed['independent_all4_acceptance'],original_controller=OWNER,
        original_audit_exits_preserved=EXITS,original_R1_supplemental_exit_separate=0,native_outcome='not_improved',
        source_freeze_released=True,owned_cleanup_complete=True,protected543_preserved=True,candidate_promoted=False,
        source_integration_manifests={k:fixed[k] for k in ('guard_manifest','control_manifest','lineage_review')},
        checked_metadata_pins=seen,trial02_activated=False,actual_trial02=None,
        scope='Completed current campaign authority only; selected guard proofs, fresh owner/resources/insurance and a new root precommit remain required.')


def _publish(path,value):
    raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode();require(len(raw)<=LIMIT,'Output too large')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    parser.add_argument('--expected-source-sha256');args=parser.parse_args(argv)
    if args.output is None and args.expected_source_sha256 is None:
        print('PLAN_ONLY: no inputs/output/runtime; explicit root output and source SHA required');return 0
    require(args.output is not None and args.output.is_absolute() and args.output.is_relative_to(RUN)
        and not args.output.exists() and args.output.parent.is_dir(),'Fresh owned run26 output file required')
    result=dict(schema='robotron-strict-current-quality-preparation-v1',status='FAIL_STRICT_CURRENT_QUALITY_PREPARATION',
        prepared_unix_s=time.time(),trial02_activated=False,actual_trial02=None)
    try:
        source=Path(__file__).read_bytes();require(hashlib.sha256(source).hexdigest()==args.expected_source_sha256,
            'Explicit gate source SHA differs')
        result.update(validate(RELEASE));result['gate_source']=dict(path=str(Path(__file__).resolve()),
            sha256=hashlib.sha256(source).hexdigest(),bytes=len(source))
    except Exception as e:result['first_error']=dict(type=type(e).__name__,message=str(e))
    _publish(args.output,result);print(json.dumps(dict(status=result['status'],output=str(args.output))))
    return 0 if result['status']=='PASS_STRICT_CURRENT_QUALITY_PREPARATION' else 2


if __name__=='__main__':raise SystemExit(main())
