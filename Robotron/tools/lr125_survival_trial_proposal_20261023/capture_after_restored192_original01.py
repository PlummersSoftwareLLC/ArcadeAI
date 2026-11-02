"""One independent later snapshot after a prospectively fixed quiet192 prefix."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import types
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
OLD = R/'quality32-protected1741-vs-currentLR125-firstSave-original01-preparation-20261023'
N = R/'quality32-protected1741-vs-currentLR125-restored192-firstSave-original01-preparation-20261023'
TAG = 'currentLR125_restored192_firstSave_original01_20261023'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_bytes(path, raw):
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())


def main():
    h = load('_restore_capture_helpers', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    w = load('_restore_capture_guard', G/'tools/lr125_survival_trial_proposal_20261023/window_observer.py')
    creator = load('_restore_capture_policy', G/'tools/quality_capacity_proposal/supervised_main_fleet197_v1.py')
    ctl = load('_restore_capture_CPU', G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    assert h.pin(w.__file__)['sha256'] == 'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a'
    prior_pin = h.pin(OLD/'fresh-study-launch-preparation-original01/current-main-binding.json')
    assert prior_pin['sha256'] == '969b22b6d7e621a470cb618a30a539d92baa7e2e85fc5b0bfc0d143d92e7bdce'
    binding = json.loads(h.checked(prior_pin).read_bytes())
    prior_API = json.loads(h.checked(binding['baseline_API']).read_bytes())
    w.owner_and_files(binding)
    N.mkdir(mode=0o700); (N/'restored192-preflight-original01').mkdir(mode=0o700)
    state_raw = (R.parent/'state.json').read_bytes()
    state = json.loads(state_raw)
    assert state['optimization_goal']['actual_running_wait'] is None and state['optimization_goal']['source_freeze'] is False
    write_bytes(N/'state-before-independent-selection.raw.json', state_raw)
    selection = h.put(N/'independent-current-policy-selection-precommit.json', dict(
        schema='robotron-independent-restored192-current-policy-selection-v1', tag=TAG,
        owner=binding['owner'], prior_main_binding=prior_pin,
        prior_closed_invalid_case=h.pin(OLD/'closed-invalid-extra-remote-slot0-independent-root-original01/readback.json'),
        selection='One first durable tagged snapshot after thirteen strict192 observations at five-second spacing; no alternative checkpoint selection.',
        prospective_quiet_prefix_s=60, prospective_sample_count=13, sample_interval_s=5,
        saved_clock_floor='All four clocks at the final accepted prefix observation; later than the prior candidate.',
        prior_invalid_candidate_retried=False, prior_invalid32M_window_completed=False,
        no_prior_scores_used=True, original_attempt=1, no_retry=True,
        prior_peer_restriction_proposal_applied=False, learning_recipe_changed=False,
        causal_LR_or_learning_speed_gain_claimed=False, created_unix_s=time.time()))
    print(json.dumps(dict(stage='RESTORED192_PREFIX_RUNNING', selection=selection,
                         pid=os.getpid(), birth=w.process_start(os.getpid()))), flush=True)
    started = time.monotonic(); samples=[]; raw=None; api=None
    try:
        for index in range(13):
            if index: time.sleep(max(0, started+index*5-time.monotonic()))
            w.owner_and_files(binding)
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
                raw=response.read(1048577)
            assert len(raw)<=1048576
            api=json.loads(raw); w.healthy(api, prior_API, binding['experiment'], time.time())
            assert sorted(row['client_slot'] for row in api['client_rows']) == list(range(192))
            path=N/'restored192-preflight-original01'/f'{index:02d}-API.raw.json'
            write_bytes(path,raw); samples.append(h.pin(path))
        floor={key:api[key] for key in ('training_steps','optimized_samples','learner_frame_count','frame_count')}
        assert floor['learner_frame_count']>2561076926
        latch=h.put(N/'restored192-preflight-original01/readback.json',dict(
            selection=selection, original_observations=samples, all13_strict192_samples=True,
            elapsed_s=time.monotonic()-started, actual_floor=floor, prior_candidate_retried=False))
        capture_job=dict(owner=binding['owner'], tag=TAG, selection=selection, clock_floor=floor,
                         current_binding=prior_pin, original_attempt=1, no_retry=True)
        h.put(N/'independent-current-policy-capture-job.json',capture_job)
        directory=N/'current-policy-capture-original01'; directory.mkdir(mode=0o700)
        # Keep the authenticated capture body. Helpers add complete eight-field
        # historical identities needed by the strict phase verifier.
        def full_publish(path,value,replace=False):
            w.publish(path,value,replace=replace)
            return h.pin(path)
        capture=types.FunctionType(w.capture.__code__,dict(w.capture.__globals__,pin=h.pin,publish=full_publish))
        result=capture(capture_job,directory,latch,samples[-1])
        result_pin=h.put(directory/'result.json',result)
        transition=result['completed_slot_transition']; slot=G/'models_dqn/managed_save.request.json.completed'
        assert transition['before']['actual_pin']['sha256']==binding['held_hashes'][str(slot)]
        assert transition['request']['archive']['sha256']==transition['after']['archive']['sha256']==h.pin(slot)['sha256']
        assert json.loads(slot.read_bytes())==dict(tag=TAG)
        binding=copy.deepcopy(binding); binding['held_hashes'][str(slot)]=transition['after']['actual_pin']['sha256']
        w.owner_and_files(binding)
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:after_raw=response.read(1048577)
        after=json.loads(after_raw);w.healthy(after,prior_API,binding['experiment'],time.time())
        reg=N/'postcapture-owned-slot-current-main-registration-original01';reg.mkdir(mode=0o700)
        write_bytes(reg/'baseline-API.raw.json',after_raw)
        old_policy=json.loads(h.checked(binding['supervision_policy']).read_bytes())
        policy,snapshot=creator.make_policy(binding,old_policy['fleet'])
        pp=h.put(reg/'current-main-supervision-policy.json',policy)
        binding.update(supervision_policy=pp, baseline_API=h.pin(reg/'baseline-API.raw.json'),
            prior_binding=prior_pin, owned_managed_save_slot_transition=transition,
            owned_completed_slot_only_source_hold_transition=True,
            current_binding_reason='Restored exact192 and one new independent snapshot; only owned completed-slot hash changed')
        bp=h.put(reg/'current-main-binding.json',binding)
        registration=h.put(reg/'readback.json',dict(current_binding=bp,prior_binding=prior_pin,
            current_census=snapshot, all196_other_source_holds_unchanged=True,
            owned_completed_slot_transition=transition, raw_API=h.pin(reg/'baseline-API.raw.json'),
            trainer_or_actors_restarted=False, prior_failed_case_requalified=False))
        monitor_text=(OLD/'fresh-study-launch-preparation-original01/root-current-main-readonly-monitor.py').read_text()
        tree=ast.parse(monitor_text);node=next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINS'for t in n.targets))
        pins=ast.literal_eval(node.value);pins['binding']=bp;lines=monitor_text.splitlines(True)
        lines[node.lineno-1:node.end_lineno]=['PINS = '+repr(pins)+'\n']
        write_bytes(reg/'root-current-main-readonly-monitor.py',''.join(lines).encode())
        source=h.pin(result['checkpoint']['path'])
        captured=h.put(N/'independent-current-policy-capture-readback.json',dict(
            status='INDEPENDENT_LATER_POLICY_CAPTURED_AFTER_RESTORED192_PREFIX_CPU_PENDING',
            selection=selection, original_result=result_pin, candidate=source, actual_clock_floor=floor,
            current_main_binding=bp, current_main_registration=registration,
            current_main_monitor=h.pin(reg/'root-current-main-readonly-monitor.py'),
            capture_function_body_unchanged=True, metadata_helpers_full_historical_identity_only=True,
            prior_candidate_retried=False, CPU_verified=False, policy_quality_qualified=False))
        cpu=N/'candidate-CPU-preparation-original01';cpu.mkdir(mode=0o700)
        oldjob=json.loads((OLD/'candidate-CPU-preparation-original01/candidate-CPU-job.json').read_bytes())
        acquisition=json.loads(Path(oldjob['phase_snapshot']['acquisition']['path']).read_bytes())
        acquisition.update(source_checkpoint={k:source[k]for k in ('path','sha256','bytes')},clock_floor=floor,
            tag=TAG,completed_slot_transition=transition,independent_capture_selection=selection,
            actual_original_capture_result=result_pin,current_main_registration=registration)
        ap=h.put(cpu/'actual-independent-current-policy-acquisition.json',acquisition)
        independent=cpu/'candidate-independent-readonly.pt'
        with Path(source['path']).open('rb')as inp,independent.open('xb')as out:
            shutil.copyfileobj(inp,out);out.flush();os.fchmod(out.fileno(),0o444);os.fsync(out.fileno())
        copy_pin=h.pin(independent);assert copy_pin['sha256']==source['sha256']and copy_pin['identity']['inode']!=source['identity']['inode']
        job=copy.deepcopy(oldjob);job.update(source=source,verification_copy=copy_pin,clock_floor=floor,
            output_directory=str(N/'candidate-CPU-verification-original01'))
        job['phase_snapshot']['acquisition']=ap
        job['source_control_context']['provenance']=[selection,result_pin,captured,registration]
        jp=h.put(cpu/'candidate-CPU-job.json',job)
        cfg=json.loads((OLD/'candidate-CPU-preparation-original01/candidate-CPU-controller-config.json').read_bytes())
        cfg.update(unit='robotron-restored192-LR125-firstSave-numerical-CPU-original01-20261023.service',
                   output=str(N/'candidate-CPU-execution-original01'))
        cfg['argv'][cfg['argv'].index('--job')+1]=jp['path']
        cfg['argv'][cfg['argv'].index('--expected-job-sha256')+1]=jp['sha256']
        cfg['pins']=[ctl.pin(entry['path'])for entry in [*cfg['pins'][:3],jp,source,copy_pin,ap,captured]]
        cp=h.put(cpu/'candidate-CPU-controller-config.json',cfg);ctl.checked_config(cp['path'])
        print(json.dumps(dict(status='NEW_CANDIDATE_CAPTURED_CPU_JOB_PREPARED',candidate=source,
            current_binding=bp,selection=selection['sha256'],CPU_config=cp['path'])),flush=True)
        return 0
    except Exception as error:
        h.put(N/'original-selection-or-capture-failure-no-retry.json',dict(error=repr(error),
            original_attempt=1,no_retry=True,samples=samples,selection=selection,ended_unix_s=time.time()))
        raise


if __name__=='__main__':
    raise SystemExit(main())
