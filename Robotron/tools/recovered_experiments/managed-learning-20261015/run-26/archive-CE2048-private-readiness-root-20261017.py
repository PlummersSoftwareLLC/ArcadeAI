"""Root execution: archive the one original terminal, then release its exact units."""
import importlib.util
import json
import time
from pathlib import Path

RUN = Path(__file__).resolve().parent
UTILITY = RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py'
import hashlib
assert hashlib.sha256(UTILITY.read_bytes()).hexdigest() == 'd525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'
spec = importlib.util.spec_from_file_location('CE2048_unchanged_root_ops', UTILITY)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
OUT = RUN/'CE2048-private-readiness-owned-cleanup-root-reviewed1-20261017'
LAUNCH = RUN/'CE2048-private-readiness-GPU-root-execution-reviewed1-20261017'
PROBE = RUN/'CE2048-private-training-readiness-reviewed1-20261017'
owner = json.loads((LAUNCH/'root-original-parent-identity.json').read_text())
unit = owner['unit']; timer = unit.removesuffix('.service')+'.timer'
assert (owner['pid'], owner['starttime_ticks'], owner['invocation_id']) == (1136647,34985894,'0d99e5969021473ab3e6a0cf9a98df9d')
value, original_show = ops.show(unit)
ops.original_terminal(owner, value)
assert value['ExecMainCode'] == '1' and value['ExecMainStatus'] == '0' and value['Result'] == 'success'
whole, whole_pin = ops.read_file(PROBE/'result.json'); whole = json.loads(whole)
assert whole['readiness_pass'] is True and whole['qualification_pass'] is False
assert whole['actual_attempts'] == whole['applied_outcomes'] == 18 and whole['owned_cleanup_complete'] is True
assert whole['batch_rows'] == 2048 and whole['priority_metric'] == 'ce'
assert [v['variant'] for v in whole['variants']] == ['ce18','resume','restart_ce']
assert all(v['readiness_pass'] is True for v in whole['variants'])
OUT.mkdir()
commands = []
def record(label, raw):
    pin = ops.publish(OUT/f'{len(commands):03d}-{label}-command.json',raw)
    commands.append(pin)
    return pin
show_pin = record('original-service-show', original_show)
record('original-service-cat', ops.command(['systemctl','--user','cat',unit]))
record('original-service-invocation-journal',ops.command(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+owner['invocation_id'],'--no-pager','-o','short-iso-precise']))
timer_fields, timer_show = ops.show(timer)
record('original-timer-show',timer_show)
record('original-timer-cat',ops.command(['systemctl','--user','cat',timer]))
if timer_fields.get('InvocationID'):
    record('original-timer-invocation-journal',ops.command(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+timer_fields['InvocationID'],'--no-pager','-o','short-iso-precise']))
pins = {}
children = []
for p in [PROBE/'result.json',PROBE/'launch-manifest.json',PROBE/'ownership.json',LAUNCH/'root-original-parent-identity.json',LAUNCH/'root-launch-intent.json']:
    pins[str(p)] = ops.read_file(p)[1]
for role in ('ce18','resume','restart_ce'):
    for name in ('phase-result.json','child-exit.json','loaded-proof.json','private-serving-graphs-released.json','phase-record.json','role-input.json'):
        p = PROBE/role/name
        pins[str(p)] = ops.read_file(p)[1]
    child = json.loads((PROBE/role/'child-exit.json').read_text())
    assert child['actual_returncode'] == 0 and child['owned_identity']['ppid'] == owner['pid']
    children.append(child)
archive = ops.publish(OUT/'original-terminal-archive.json',dict(
    status='ORIGINAL_SUCCESSFUL_TERMINAL_ARCHIVED_BEFORE_RELEASE',observed_unix_s=time.time(),
    original_owner=owner, original_show=show_pin, ExecMainCode=1, ExecMainStatus=0,
    Result='success',NRestarts=0,whole_result=whole_pin,readiness_pass=True,qualification_pass=False,
    source_lock_sha256=whole['source_lock_sha256'],children=children,pins=pins,unit_not_released_yet=True,
    raw_commands=list(commands)))
launch = json.loads((PROBE/'launch-manifest.json').read_text())
def absent():
    for item in [owner]+[dict(pid=x['pid'],starttime_ticks=int(x['owned_identity']['start_ticks'])) for x in children]:
        assert ops.process_start(item['pid']) != item['starttime_ticks'], 'Original process remains'
    ops.cgroup_empty(owner['cgroup'])
    assert not Path(launch['tmpfs']).exists(), 'Private tmpfs remains'
    return dict(original_parent_and_three_children_absent=True,owned_cgroup_absent_or_empty=True,private_tmpfs_absent=True)
before_absent = ops.publish(OUT/'pre-release-owned-absence.json',absent())
cfg = json.loads((RUN/'CE543M-quality-binding-root-preparation-20261017/root-quality-binding-job.json').read_text())
capture = ops.pinned(cfg['evidence']['capture_result'])
history = ops.pinned(capture['root_job'])['history']
bindings = ops.pinned(history['outer_job']); activation_job = ops.pinned(history['activation_job'])
activation = ops.pinned(history['activation']); ce = ops.pinned(history['CE_return'])
before, raw = ops.current_ce_and_resources(bindings,activation_job,activation,ce,record)
pre = dict(proof=ops.publish(OUT/'pre-release-main192-and-resources.json',before),raw_API=ops.write_bytes(OUT/'pre-release-main-API.json',raw))
releases = []
for target in (timer, unit):
    absent()
    still, rawshow = ops.show(unit)
    ops.original_terminal(owner,still)
    assert still['ExecMainCode']=='1' and still['ExecMainStatus']=='0'
    record('before-release-'+target,ops.show(target)[1])
    stopped = ops.command(['systemctl','--user','stop',target],timeout=30)
    record('stop-'+target,stopped)
    assert stopped['returncode']==0, 'Exact owned stop failed'
    after, afterraw = ops.show(target)
    record('after-release-'+target,afterraw)
    assert after['LoadState']=='not-found', 'Exact owned unit not released'
    releases.append(dict(unit=target,actual_stop_returncode=0,final_load_state='not-found'))
after_absent = ops.publish(OUT/'post-release-owned-absence.json',absent())
after, raw = ops.current_ce_and_resources(bindings,activation_job,activation,ce,record)
post = dict(proof=ops.publish(OUT/'post-release-main192-and-resources.json',after),raw_API=ops.write_bytes(OUT/'post-release-main-API.json',raw))
receipt = ops.publish(OUT/'root-owned-cleanup-and-release.json',dict(
    status='PASS_ORIGINAL_CE2048_PRIVATE_READINESS_ARCHIVED_OWNED_CLEANUP_COMPLETE',
    original_terminal_archive=archive,original_owner=owner,original_parent_exit=0,original_three_child_exits=[0,0,0],
    whole_result=whole_pin,source_lock_sha256=whole['source_lock_sha256'],
    original_terminal_archived_before_release=True,owned_cleanup_complete=True,
    readiness_pass=True,qualification_pass=False,live_batch2048_activated=False,
    actual_training_attempts=18,applied_outcomes=18,owned_release=releases,
    pre_release_absence=before_absent,post_release_absence=after_absent,
    pre_release_health=pre,post_release_health=post,
    main192_and_resources_healthy=True,raw_commands=commands))
print(json.dumps(dict(status='PASS',receipt=receipt,learner_frames=json.loads(raw)['learner_frame_count'])))
