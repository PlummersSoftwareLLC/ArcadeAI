from pathlib import Path
import importlib.util,json,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26';N=B/'future-fast-pending-physical-watch-source-original01-20261101';L=N/'published-pending-trigger-engineering-original03';C=B/'short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
h=load('_reviewPendingH',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');reader=load('_reviewPendingStrictReader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py');read=lambda pin,as_json=True:reader.read_pin(pin,as_json=as_json)
prep=read(h.pin(L/'prepared-not-launched.json'));job=read(prep['job']);native=read(h.pin(L/'report.json'));closed=read(h.pin(L/'original-engineering-result-and-positive-owned-closeout.json'));assert closed['actual_exit']==0 and closed['all_original_resources_closed'] and closed['controller_birth_absent']
physical=read(native['physical_health_report']);binding=read(job['bindings']);ap=json.loads((C/'prepared-with-review.json').read_text())['independent_owned_Main_auditor'];auditor=load('_reviewActualMainAuditor',h.checked(ap))
result=dict(main_health_report=native['physical_health_report'],main_samples=physical['samples'],main_observer_lifecycle=dict(original_observer_thread_closed=True,no_child_scope_created=True))
review=auditor.audit_main(binding,result,read,h)
assert review['accepted']==native['accepted_samples']>=40 and review['pending']==native['pending_samples'];assert native['original_observer_thread_closed'] and native['models_or_actors_or_GPU_context_created']is False and native['any_Main_control_changed']is False
raw=[read(s['physical_v6'])for s in physical['samples']];pending=[i for i,r in enumerate(raw)if not r['accepted']];transitions=[]
for i in pending:
 assert i+1<len(raw),'Pending observation requires actual subsequent observation'
 gap=raw[i+1]['started_monotonic_s']-raw[i]['completed_monotonic_s']
 # The exact extracted loop waits0.2s after a pending observation. Allow
 # scheduling overhead, but reject a return to the old5s pending sleep.
 assert .19<=gap<5,('No live fast-pending cadence proof',i,gap)
 j=next(j for j in range(i+1,len(raw))if raw[j]['accepted'])
 transitions.append(dict(pending_index=i,pending_slots=raw[i]['pending_slots'],projection_changed=raw[i]['projection_changed'],next_observation_gap_s=gap,next_accepted_index=j,until_accepted_s=raw[j]['completed_monotonic_s']-raw[i]['started_monotonic_s']))
covered=len(pending)>=1
assert covered is native['pending_branch_live_coverage']
for pin in job['inputs']:h.checked(pin)
seq=load('_reviewPendingSeq',G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py');ctl=load('_reviewPendingCtl',h.checked(prep['controller']));rt=load('_reviewPendingRT',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
scope=seq.verify_closed_scope(L,'',prep['controller_config'],h,read,rt,ctl,exit_zero=True);child=json.loads((L/'controller-original-child.json').read_text());assert seq.birth(child['pid'])!=child['starttime_ticks']
p=h.put(L/'independent-result-and-positive-owned-closeout.json',dict(status='PASS_LIVE_PENDING_BRANCH_AND_ACCEPTED_RECOVERY_INDEPENDENTLY_REPLAYED'if covered else 'STABLE_LIVE_REPLAY_PASS_PENDING_COVERAGE_INSUFFICIENT',observed_unix_s=time.time(),actual_original_tool_session=87673,actual_original_tool_exit=0,actual_original_native_exit=0,original_scope=scope,original_native_report=h.pin(L/'report.json'),independent_auditor=ap,independent_replay=review,actual_fast_pending_transitions=transitions,pending_branch_live_coverage=covered,all_original_resources_closed=True,original_native_and_controller_births_absent=True,unchanged_bounds=dict(cleanup_ACK_s=7,overlap_s=10,collection_s=10,observer_gap_s=15),models_actors_or_GPU_context_created=False,training_control_changed=False,qualification_scope='Actual read-only pending transition and stable integration under the current training workload. No private32 scientific workload was added. Original failed77f9R1 staysinvalid; no scores or policy quality qualification.',quality_qualified=False,promotion=False))
print(json.dumps(dict(result={k:p[k]for k in ['path','sha256','bytes']},replay=review,pending_branch_live_coverage=covered,transitions=transitions)),flush=True)
