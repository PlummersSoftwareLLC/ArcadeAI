"""Independent new deadline32 score, raw prefix, health and ownership review."""
import argparse
import ast
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def require(ok,message):
    if not ok:raise ValueError(message)


def load(pin,name):
    path=Path(pin['path']);require(hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256'],'Review source differs')
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def validate_observer4260_derivation(historical_family,family,read):
    pin=family['observer_bound4260_derivation']
    assert pin['sha256']=='70dae0ef7ef3264b3556b848e3cc87177d9fde1069b1673bbf417f7f543f4299'
    d=read(pin)
    assert d['schema']=='robotron-deadline32-observer-bounded4260-source-derivation-v1'
    assert d['old_sources_changed'] is d['launched'] is False
    before,after=d['source_parents'],d['selected_sources']
    assert historical_family['main_observer']==before and family['main_observer']==after
    assert set(before)==set(after)=={'client','worker','controller','reviewer','protocol'}
    assert before['protocol']==after['protocol'] and after['protocol']['sha256']=='0ec8510b82783b6d47cad99ba63c59045f32e5b9acf6dbfa128b308f9641d2b9'
    assert d['bounds']==dict(native_work_s=4200,native_watchdog_s=4260,observer_watchdog_s=4260,
        outer_observation_s=4320,observer_cpu_cores=2,observer_memory_bytes=4<<30,observer_tasks_max=128)
    for role in ('client','worker','controller','reviewer'):
        source=read(before[role],False).decode();selected=read(after[role],False).decode()
        if role=='client':
            expected=source.replace('12e479b0eb0545dab32da1d8f8130be3622670207c79ecaf0a164b812fa0ec5a',after['controller']['sha256']).replace('22260','4260').replace('22320','4320')
        elif role=='worker':
            expected=source.replace('in (180,22260)','in (4260,)').replace("{180:'3min',22260:'6h 11min'}","{4260:'1h 11min'}")
        elif role=='controller':
            expected=source.replace("'22260'","'4260'").replace("22320<=c['observation_s']<=22380","4320<=c['observation_s']<=4320")
        else:expected=source.replace('22260','4260').replace('22320','4320').replace("'6h 11min'","'1h 11min'")
        assert expected!=source and selected==expected,'Unexpected bounded observer source/predicate delta: '+role
    return dict(derivation=pin,historical_sources=before,selected_bounded4260_sources=after,
        historical_coalescing_CPU_proof_preserved_at_original_node=True,
        exact_only_watchdog_observation_and_controller_pin_delta=True,health_and_protocol_algorithms_unchanged=True)

def validate_protocol_provenance(family, read):
    """Verify historical derivations at their own nodes, then the selected codec.

    Historical receipts describe their original sources. They remain immutable;
    continuity to the active running publisher requires its own guarded source.
    """
    def nodes(pin):
        return {n.name: n for n in ast.parse(read(pin, False)).body if isinstance(n, ast.FunctionDef)}

    def unchanged(parent, child, renamed):
        previous, current = nodes(parent), nodes(child)
        for name, original in previous.items():
            selected = current[renamed.get(name, name)]
            selected.name = name
            assert ast.dump(selected) == ast.dump(original), name

    RAM_contracts = read(family['RAM_control_components']['contracts'])
    assert RAM_contracts['original_codec_guards'] == 38 and RAM_contracts['RAM_negative_guards'] == 31
    RAM_provenance = read(family['RAM_control_components']['source_provenance'])
    assert RAM_provenance['helper'] == family['main_live_control']
    for record in RAM_provenance['source_changes']:
        source = read(record['prospective'], False).decode()
        for before, after in reversed(record['changes']):
            assert source.count(after) == 1
            source = source.replace(after, before)
        assert source == read(record['original'], False).decode()

    transient = family['transient_live_protocol_components']
    tproof = read(transient['protocol'])
    tprov = read(transient['source_provenance'])
    assert RAM_provenance['codec'] == tprov['prospective_protocol']
    assert tproof['original_guards'] == 38 and tproof['concurrent_publications'] == 5000
    assert tproof['strict_original_reader_and_validation_and_lock_AST_unchanged'] is True
    assert tproof['immutable_finish_and_authoritative_raw_and_outcome_unchanged'] is True
    unchanged(tprov['original_protocol'], tprov['prospective_protocol'], {'publish_live': '_publish_live_serialized_durable_v4'})
    # Preserve the original transient-publisher checks at the historical v5 node.
    publisher = nodes(tprov['prospective_protocol'])['publish_live']
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'fsync' for n in ast.walk(publisher))
    protected = next(n for n in publisher.body if isinstance(n, ast.With) and isinstance(n.items[0].context_expr, ast.Call) and isinstance(n.items[0].context_expr.func, ast.Name) and n.items[0].context_expr.func.id == '_live_lock')
    assert all(isinstance(n, (ast.If, ast.Expr)) for n in protected.body)
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'replace' for n in ast.walk(protected))

    proofs = family['serialized_protocol_components']
    component = read(proofs['protocol'])
    assert component['original_guards'] == 38 and component['concurrent_publications'] == 5000
    assert component['strict_original_read_and_publish_bodies_AST_unchanged'] and component['finish_protocol_unchanged']
    provenance = read(proofs['source_provenance'])
    assert provenance['prospective_protocol'] == tprov['original_protocol']
    unchanged(provenance['original_protocol'], provenance['prospective_protocol'], {'checked_read': '_checked_read_strict', 'publish_live': '_publish_live_unlocked'})

    selected = family['main_observer']['protocol']
    assert selected['sha256'] == '0ec8510b82783b6d47cad99ba63c59045f32e5b9acf6dbfa128b308f9641d2b9'
    unchanged(tprov['prospective_protocol'], selected, {'publish_live': '_publish_live_required_v5'})
    cpupin = family['coalescing_protocol_CPU']
    assert cpupin['sha256'] == '4ed599c14b1270619c2479aec3c33af48c0b38cc636ae8d079229dbbc0b75ec6'
    cpu = read(cpupin)
    assert cpu['actual_tool_terminal_exit'] == 0
    assert cpu['original38_contracts_4_interleaves_6_lock_negatives_2_timeouts_and5000_generic_concurrency_passed'] is True
    assert cpu['all6_descriptors_argv_resources_pins_birth_unit_cgroup_release_verified'] is True
    assert cpu['original_reader500ms_freshness_required_publications_and100ms_bounds_unchanged'] is True
    guarded = read(cpu['report'])
    assert guarded['protocol'] == selected
    assert guarded['coalescing']['groups'] == cpu['coalescing_feature_groups'] == 7
    assert guarded['coalescing']['original_reader_and_raw_validity_rules_unchanged'] is True
    assert guarded['coalescing']['coalescing_only_running_control_projections'] is True
    assert guarded['coalescing']['required_terminal_and_start_publications_unchanged'] is True
    assert guarded['coalescing']['all_children_and_threads_joined'] is True
    derivation = read(guarded['source_provenance'])
    assert derivation['derived'] == selected
    before, after = derivation['exact_change']
    parent = read(derivation['parent'], False).decode()
    assert parent.count(before) == 1 and parent.replace(before, after) == read(selected, False).decode()

    actualpin = family['coalescing_observer_component_CPU']
    actual = read(actualpin)
    assert actual['actual_tool_terminal_exit'] == actual['parent_actual_exit'] == actual['observer_actual_exit'] == 0
    assert actual['actual_protocol'] == selected
    assert actual['current_main_binding'] == family['current_component_main_binding']
    assert actualpin == family['current_main_context_CPU']
    assert actual['original500ms_freshness_and_max_gap_limits_unchanged'] is True
    assert actual['all_original_raw_indices_complete'] is True
    assert actual['all6_descriptors_resources_argv_pins_birth_units_cgroups_release_verified'] is True
    assert actual['maximum_observation_gap_s'] <= .5
    stats = actual['running_projection_publication_stats']
    assert stats['attempts'] == stats['published'] + stats['coalesced_busy_reader'] == actual['original_raw_main_samples']
    assert stats['published'] > 0 and stats['coalesced_busy_reader'] > 0 and stats['errors'] == 0
    observer420 = validate_observer4260_derivation(read(actual['component_family']), family, read)
    return dict(historical_RAM_codec=RAM_provenance['codec'], historical_serialized_codec=provenance['prospective_protocol'],
                selected_protocol=selected, coalescing_protocol_CPU=cpupin, current_context_observer_CPU=actualpin,
                observer4260_historical_to_selected_bridge=observer420,
                all_historical_derivations_and_retained_function_AST_verified=True,
                selected_running_publisher_exact_source_and_guarded_behavior_verified=True,
                raw_runtime_ROM_quality_and_rate_checks_unchanged=True)


def review_health(review,job,jp,result,owner,cfg,started,ended,family,protocol,read,h):
    verifier=load(family['main_observer']['reviewer'],'_deadline_actual_observer_review')
    checked=verifier.verify(job,jp,owner,cfg['argv'],result['main_observer_lifecycle'],protocol,family,[],read,h)
    assert checked['closed_report']==result['main_health_report']
    closed=read(result['main_health_report'])
    assert closed['actual_status']==result['main_samples'] and len(closed['samples'])>=2 and closed['deep_samples']>=1
    capture=family['inet_diag_capture_components'];contracts=read(capture['contracts']);capacity=read(capture['resource']);query=read(capture['query'])
    assert contracts['typed_negative_rejections']==187 and capacity['resource_passed'] is True
    assert capacity['synthetic_samples']==48332 and capacity['actual_elapsed_s']<600
    assert query['exact_original_source_OR_destination_port9998_predicate'] is True
    provenance=read(capture['capture_provenance'])
    selected={Path(r['prospective']['path']).name:r['prospective']for r in provenance['source_changes']}
    for key in ('io','primitives'):
        pin=protocol['health_job']['sources'][key];assert selected[Path(pin['path']).name]==pin
    collector=load(protocol['health_job']['sources']['collector'],'_deadline_actual_raw_collector')
    engine=load(protocol['health_job']['sources']['full_health_engine'],'_deadline_actual_full_health_engine')
    sample_paths={p['path']for p in closed['samples']};epochs=[]
    def kernel_read(pin,as_json=True):
        value=read(pin,as_json)
        if as_json and pin['path']in sample_paths:
            sample=collector.unpacked(value);snapshot=json.loads(sample['raw_tcp'])
            assert snapshot['schema']=='robotron-original-inet-diag-port9998-snapshot-v3' and snapshot['error'] is None
            assert snapshot['begin_unix_s']==sample['tcp_begin_unix_s'] and snapshot['end_unix_s']==sample['tcp_end_unix_s']
            assert sample['index']==len(epochs)
            epochs.append(dict(index=sample['index'],begin_unix_s=snapshot['begin_unix_s'],end_unix_s=snapshot['end_unix_s'],
                datagrams=len(snapshot['datagrams']),raw_envelope_bytes=len(sample['raw_tcp'])))
        return value
    replay=engine.replay(protocol['health_job'],closed['samples'],read(closed['initial_cursors']),kernel_read,h,
        prior_groups=[],original_statuses=closed['actual_status'])
    assert len(epochs)==replay['samples'] and replay['transport']==closed['transport'] and replay['deep_samples']==closed['deep_samples']
    assert started<=closed['guard_started_monotonic_s']<=replay['first_deep_monotonic_s']<=replay['last_deep_monotonic_s']<=closed['guard_ended_monotonic_s']<=ended
    seal=read(result['deadline_score_seal'])
    assert closed['guard_started_monotonic_s']<=seal['anchor_monotonic_ns']/1e9<seal['deadline_monotonic_ns']/1e9<=closed['guard_ended_monotonic_s']
    outcome=read(checked['worker_outcome'])
    assert outcome['interpreter']['GIL_enabled'] is False and outcome['interpreter']['major_minor']==[3,14]
    life=read(result['main_observer_lifecycle']);release=read(life['live_control_release']);intent=read(release['intent'])
    lock=next(r for r in intent['files']if Path(r['original']['path']).name=='live.json.lock')
    assert read(lock['archived'],False)==b'' and lock['original']['identity']['mode']=='0o600'
    assert not Path(lock['original']['path']).exists() and not Path(release['binding']['root']).exists()
    out=Path(job['output']);assert not(out/'main-observations/live.json').exists() and not(out/'main-observations/live.json.lock').exists()
    protocol_proof=validate_protocol_provenance(family,read)
    initial=load(review['initial_helpers'],'_deadline_actual_initial_readiness')
    anchor=read(result['deadline_anchor'])
    initial_proof=initial.validate_initial_readiness(read(result['initial_main_readiness']),result['initial_main_readiness'],job,jp,
        replay,h.pin(out/'original-loaded-policy.json'),anchor['fixed_admission'],started,ended)
    return dict(observer=checked,replay=replay,kernel_epochs=epochs,protocol_provenance=protocol_proof,initial_readiness=initial_proof)


def review_closed(review,read,h):
    jp=review['native_job'];job=read(jp);result=read(review['native_result']);out=Path(job['output'])
    assert job['schema']=='robotron-deadline32-one-original-leg-v1' and result['schema']=='robotron-deadline32-original-leg-result-v1'
    assert result['original_job']==jp and result['complete'] is True and result['errors']==[]
    assert result['status']=='ORIGINAL_DEADLINE32_SEALED_AND_CLOSED' and result['attempt']==1 and result['no_retry'] is True
    assert result['original_lease_released'] is result['all_original_threads_stopped'] is result['immutable_inputs_unchanged'] is True
    assert result['main_health_failure'] is None and result['policy_before']==result['policy_after']
    assert result['full_game_quality_qualified'] is result['deadline_metric_independently_qualified'] is result['improvement_qualified'] is False
    owner=read(review['native_owner']);cfg=read(review['native_config'])
    archive=load(review['archive'],'_deadline_native_scope_archive')
    fields=archive.archived_closure(read(review['native_closure']),owner,read,exit_zero=True)
    expected=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus='0',
        CPUQuotaPerSecUSec='12s',MemoryMax=str(24<<30),MemorySwapMax='0',RuntimeMaxUSec='1h 11min',TasksMax='512',
        TimeoutStopUSec='30s',KillMode='mixed',SendSIGKILL='no',Restart='no',NRestarts='0')
    for k,v in expected.items():assert fields[k]==v,(k,fields[k],v)
    command='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(Path(cfg['output'])/'tmp')+' '+' '.join(cfg['argv'])
    assert command+' ; ignore_errors=no ;'in fields['ExecStart']
    control=load(review['native_controller'],'_deadline_actual_native_controller')
    validate_controller_pins(cfg,control)
    control.checked_config(review['native_config']['path'])
    for unit in (owner['unit'],owner['timer']):assert control.show(unit)['LoadState']=='not-found'
    assert birth(owner['pid'])!=owner['starttime_ticks']
    assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',owner['unit']).exists()
    started=int(fields['ExecMainStartTimestampMonotonic'])/1e6;ended=int(fields['ExecMainExitTimestampMonotonic'])/1e6
    assert 0<started<ended<=time.monotonic() and ended-started<=4320
    family=read(job['source_family_manifest']);protocol=read(job['main_health_protocol'])
    assert family['runtime']==job['runtime'] and family['deadline_components']==job['components']
    health=review_health(review,job,jp,result,owner,cfg,started,ended,family,protocol,read,h)
    guard=read(review['source_family_guard_closeout'])
    assert guard['schema']=='robotron-deadline32-original-prelaunch-family-guard-v1' and guard['native_job']==jp and guard['runtime']==job['runtime']
    assert guard['status']=='PASS' and guard['actual_exit']==0 and guard['actual_CPU_cores']==2 and guard['actual_memory_bytes']==4<<30 and guard['actual_runtime_limit_s']==180
    loaded=read(h.pin(out/'original-loaded-policy.json'));policy=result['policy_before']
    assert loaded['policy']==policy and policy['checkpoint_sha256']==job['checkpoint']['sha256']
    assert policy['training_enabled'] is policy['replay_enabled'] is False and policy['epsilon']==policy['expert_ratio']==0
    assert loaded['gpu_uuid']==job['gpu_uuid'] and loaded['memory_is_none'] is loaded['optimizer_is_none'] is True
    assert loaded['compile_report']==result['compile_report'] and result['compile_report']['all_shapes_verified']==list(range(1,17))
    anchor=read(result['deadline_anchor']);seal=read(result['deadline_score_seal']);cleanup=read(result['intentional_cleanup'])
    assert seal['recorder_implementation_revision']==3
    assert cleanup['original_score_seal']==result['deadline_score_seal'] and cleanup['original_barrier']==result['original_barrier']
    assert started<=result['native_started_monotonic_s']<anchor['anchor']['anchor_monotonic_ns']/1e9<=result['native_started_monotonic_s']+300
    assert result['native_deadline_monotonic_s']==result['native_started_monotonic_s']+4200
    failures=result['private_failure_events'];assert len(failures)==32 and {r['slot']for r in failures}==set(range(4096,4128))
    for event in failures:
        assert event['expected_deadline_retirement'] is event['intentional_cleanup_flag'] is True
        assert event['error'].startswith('DeadlineRetired(') and event['observed_monotonic_ns']>=cleanup['begin_monotonic_ns']
    reaped=result['original_post_origin_child_reap']
    writers=result['original_writer_capture']
    assert writers['all32_client_thread_objects_retained_before_shutdown'] is writers['retained_inference_thread'] is writers['all_retained_writers_stopped'] is True
    assert writers['retained_client_threads']==32 and type(writers['original_cleanup_timers_joined']) is int
    assert reaped['all_original_children_reaped'] is True and reaped['unknown_slots']==[]
    assert reaped['signals_sent'] is reaped['exit_statuses_normalized'] is False
    def index(pin):
        rows=[json.loads(line)for line in read(pin,False).splitlines()]
        values={r['journal_game_id']:r for r in rows};assert len(values)==len(rows);return values
    starts=index(result['journal']['measurement_starts.jsonl']);games=index(result['journal']['games.jsonl'])
    auditor=load(job['components']['prefix_auditor'],'_deadline_independent_actual_first_START');auditor.dependencies()
    prefix_result=dict(result,_admission=anchor['fixed_admission']);prefixes=[]
    assert anchor['fixed_admission']['close_unix_ns']-anchor['fixed_admission']['open_unix_ns']==300_000_000_000
    for slot in range(4096,4128):
        row=result['original_slots'][str(slot)];child=reaped['original_children'][str(slot)]
        assert child['pid']==row['pid'] and child['birth']==row['birth'] and child['actual_exit']==row['actual_exit']
        assert type(row['actual_exit']) is int and row['outputs_sealed_after_original_writer_closure'] is True and row['original_unsealed_output_paths']==[]
        assert row['expected_deadline_retirement'] is True and row['actual_proxy_error'].startswith('DeadlineRetired(')
        assert row['intentional_cleanup']=={k:cleanup[k]for k in ('begin_monotonic_ns','declared_monotonic_ns','after_flags_monotonic_ns','score_sealed_monotonic_ns')}
        prefixes.append(auditor.audit_first_start_prefix(slot,row,job,prefix_result,starts,games,read,h.pin,expected_job_sha256=jp['sha256']))
    score_auditor=load(job['components']['score_auditor'],'_deadline_actual_score_cutoff_audit')
    score=score_auditor.audit(job,result,seal,anchor,cleanup,prefixes,starts,games)
    restored=result['measurement_restoration']
    assert restored['metric_sealed'] is restored['all_original_threads_stopped'] is restored['complete_game_judgment_not_requested'] is True
    assert restored['original_cutoff_seal']==result['deadline_score_seal'] and restored['measurement_active_after'] is restored['owns_mode_after'] is False
    for pin in job['inputs']:h.checked(pin)
    assert h.pin(result['acquired_checkpoint']['path'])==result['acquired_checkpoint']
    fd=os.open(job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    return dict(schema='robotron-deadline32-original-leg-independent-review-v1',status='PASS',original_job=jp,
        native_result=review['native_result'],leg=job['leg'],source_family=job['source_family_manifest'],
        actual_native_exit=0,all32_original_prefixes=prefixes,score_cutoff=score,main_health=health,
        actual_actor_exit_statuses_retained=True,positive_owned_native_observer_children_threads_and_lease_closure=True,
        deadline_metric_independently_qualified=True,complete_game_quality_qualified=False,improvement_qualified=False)


def validate_controller_pins(cfg,control):
    # Controller envelopes deliberately retain their own reduced identity shape.
    # Full immutable job inputs remain checked by the independent full helper.
    for pin in cfg['pins']:assert control.pin(pin['path'])==pin
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256;review=json.loads(raw)
    assert review['schema']=='robotron-deadline32-original-leg-independent-review-job-v1'
    h=load(review['helpers'],'_deadline_review_helpers');reader=load(review['reader'],'_deadline_review_reader')
    for pin in review['inputs']:h.checked(pin)
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    value=review_closed(review,read,h)
    entry=h.put(Path(review['output']),value);print(json.dumps(dict(review=entry,status='PASS')),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
