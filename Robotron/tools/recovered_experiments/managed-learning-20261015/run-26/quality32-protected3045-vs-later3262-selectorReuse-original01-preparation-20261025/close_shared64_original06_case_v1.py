"""Close one original capacity case and prepare its one original raw CPU review.

Never launches, restarts, pools, or evaluates the engineering comparison early.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=Path(__file__).resolve().parent
E=N/'evaluator-count-active600-counterbalanced-engineering-original06'
P=N/'future-capacity64-shared-slot-domain-UNSELECTED-original01/runtime-family-original03'
ORDER=('01-A1-control','02-B1-capacity64','03-B2-capacity64','04-A2-control')


def load(name,path,sha=None):
    if sha is not None:assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


class CloseOriginal:
    def __init__(self,case):
        self.h=load('_capacity_close_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
                    '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
        self.reader=load('_capacity_close_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
                        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
        self.arc=load('_capacity_close_arc',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
                     '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
        self.cpu=load('_capacity_close_cpu',G/'tools/training_connection_lifecycle_proposal_20261023/control_owned_health_CPU660_v2.py',
                     'a524ebb3be864bb03f13fff0af471782b2c6497c321da38ff83b679934cd03d1')
        self.case=case;self.directory=E/case
        self.qualified_pin=self.h.pin(E/'qualified-original-ABBA-launch-configs.json')
        assert self.qualified_pin['sha256']=='332a83d90457fb325cd862a4d255d2767f91653c5d624445f6f11fd73056280b'
        self.qualified=self.read(self.qualified_pin)
        self.record=next(c for c in self.qualified['cases']if c['case']==case)
        self.job=self.read(self.record['native_job']);self.count=self.record['actor_count']
        self.control=load('_capacity_close_native_control',Path(self.record['native_controller']['path']),
                          self.record['native_controller']['sha256'])

    def read(self,pin,as_json=True):return self.reader.read_pin(pin,as_json=as_json)

    def scope(self,owner_pin,closure_pin,config_pin,exit_code,cpu,memory,runtime,tasks,stop,native=False):
        owner,closure,cfg=map(self.read,(owner_pin,closure_pin,config_pin))
        fields=self.arc.archived_closure(closure,owner,self.read,exit_zero=exit_code==0)
        assert closure['original_exit']==exit_code
        assert self.arc.duration_seconds(fields['CPUQuotaPerSecUSec'])==cpu
        assert fields['MemoryMax']==str(memory)and fields['MemorySwapMax']=='0'
        assert self.arc.duration_seconds(fields['RuntimeMaxUSec'])==runtime
        assert fields['TasksMax']==str(tasks)and fields['SendSIGKILL']=='no'and fields['Restart']=='no'
        assert self.arc.duration_seconds(fields['TimeoutStopUSec'])==stop
        if native:assert fields['KillMode']=='mixed'
        assert ' '.join(cfg['argv'])+' ; ignore_errors=no ;'in fields['ExecStart']
        for pin in cfg['pins']:assert self.control.pin(pin['path'])==pin
        assert birth(owner['pid'])!=owner['starttime_ticks']
        for unit in (owner['unit'],owner['timer']):
            assert self.control.show(unit)['LoadState']=='not-found'
            assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists()
        return dict(owner=owner_pin,closure=closure_pin,config=config_pin,actual_exit=exit_code,
                    all6_original_descriptors_argv_resources_pins_and_release_verified=True,
                    original_birth_and_both_units_and_cgroups_absent=True,archived_fields=fields)

    def free_resources(self):
        lease=self.job['lease'];self.h.checked(lease)
        fd=os.open(lease['path'],os.O_RDWR|os.O_NOFOLLOW)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)
        assert self.h.pin(lease['path'])==lease
        # Ports may retain kernel teardown state after an honest closed scope.
        # This observes resource release only; it never extends native work.
        deadline=time.monotonic()+75
        while True:
            try:
                for port in (self.job['origin_port'],*self.job['proxy_ports'].values()):
                    with socket.socket()as sock:sock.bind(('127.0.0.1',port))
                break
            except OSError:
                if time.monotonic()>=deadline:raise
                print(json.dumps(dict(case=self.case,waiting_only_for_closed_native_kernel_ports=True)),flush=True)
                time.sleep(2)
        p=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],
                         capture_output=True,text=True,timeout=20)
        assert p.returncode==0 and self.job['gpu_uuid']not in p.stdout
        return dict(lease=lease,private_port_count=1+self.count,all_private_ports_free=True,
                    GPU=dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr),persistent_coordinator_preserved=True)

    def prepare_review(self,session,observed_exit):
        assert session>0 and observed_exit==1
        d=self.directory;out=Path(self.job['output'])
        owner_pin=self.h.pin(d/'execution-original01/root-original-identity.json')
        closure_pin=self.h.pin(d/'execution-original01/root-original-result-and-owned-release.json')
        native_scope=self.scope(owner_pin,closure_pin,self.record['launch_config'],1,12,24<<30,22260,512,30,True)
        result_pin=self.h.pin(out/'result.json');result=self.read(result_pin)
        assert result['errors'][0]=="ValueError('PRECOMMITTED_ACTIVE600_SELECTOR_LOAD_STOP_NOT_A_QUALITY_RESULT')"
        assert len(result['errors'])==self.count+1
        slots=[]
        for error in result['errors'][1:]:
            match=re.fullmatch(r"Original slot([0-9]+): ValueError\('(Original origin client disappeared|Original startup connection ended during a frame|Original full-tail exchange interrupted)'\)",error)
            assert match,error
            slot = int(match[1])
            if match[2] == 'Original full-tail exchange interrupted':
                bridge_pin = self.job['quota64_source_pins']['bridge']
                assert bridge_pin['sha256'] == 'af47c3dac80cc3888023e5ce8fb62b4b0934fab1df7576719adad4ef373832ca'
                bridge_source = self.h.checked(bridge_pin).read_text()
                assert bridge_source.count("require(not self.stop_event.is_set(),'Original full-tail exchange interrupted')") == 1
                runtime_source = self.h.checked(self.job['runtime']).read_text()
                assert runtime_source.count('bridge_stop.set()') == 1
                assert runtime_source.index('    finally:', runtime_source.index('def run(')) < runtime_source.index('        bridge_stop.set()')
                assert 'stop_event=bridge_stop' in runtime_source
                pin = result['original_slots'][str(slot)]['files']['proxy.jsonl']
                events = [json.loads(line) for line in self.read(pin,False).splitlines()]
                failed = [v for v in events if v['kind'] == 'original_proxy_failure']
                assert len(failed) == 1 and failed[0]['error'] == repr(ValueError('Original full-tail exchange interrupted'))
                assert failed[0]['sequence'] >= result['active_end']['slots'][str(slot)]['sequence']
            slots.append(slot)
        assert sorted(slots)==self.job['actor_slots']
        assert result['all_original_threads_stopped']is result['original_lease_released']is result['immutable_inputs_unchanged']is True
        assert result['main_health_failure']is None and result['main_health_report']is not None
        assert result['original_unsealed_journal_paths']==[] and len(result['original_slots'])==self.count
        reap=result['original_post_origin_child_reap']
        assert reap['all_original_children_reaped']is True and reap['unknown_slots']==[]
        assert reap['signals_sent']is reap['exit_statuses_normalized']is False
        for slot,entry in result['original_slots'].items():
            assert entry['actual_exit']==0 and entry['outputs_sealed_after_original_writer_closure']is True
            assert entry['original_unsealed_output_paths']==[] and birth(entry['pid'])!=entry['birth']
            for pin in entry['files'].values():self.h.checked(pin)
        for pin in result['journal'].values():self.h.checked(pin)
        family=self.read(self.job['source_family_manifest']);protocol=self.read(self.job['main_health_protocol'])
        verifier=load('_capacity_close_observer_verifier',Path(family['main_observer']['reviewer']['path']),
                      family['main_observer']['reviewer']['sha256'])
        checked=verifier.verify(self.job,self.record['native_job'],self.read(owner_pin),
                               self.read(self.record['launch_config'])['argv'],result['main_observer_lifecycle'],
                               protocol,family,[],self.read,self.h)
        assert checked['closed_report']==result['main_health_report']
        life=self.read(result['main_observer_lifecycle'])
        worker_scope=self.scope(life['worker_owner'],life['worker_closure'],life['worker_config'],0,2,4<<30,22260,128,5)
        rate=self.read(result['active_frame_rate'])
        assert rate['midpoint_elapsed_s']>=600 and rate['start']==result['active_start']and rate['end']==result['active_end']
        marker=self.read(self.h.pin(out/'original-all-slots-prefix-diagnostic-stop.json'))
        assert marker['reason']=='PRECOMMITTED_ACTIVE600_SELECTOR_LOAD_STOP'
        resources=self.free_resources()
        terminal=self.h.put(d/'independent-original-native-observer-terminal-closeout.json',dict(
            schema='robotron-capacity64-original-native-observer-terminal-closeout-v1',case=self.case,
            native_job=self.record['native_job'],native_result=result_pin,qualified_launches=self.qualified_pin,
            actual_native_tool_session=session,actual_native_tool_exit=1,native_scope=native_scope,
            observer_scope=worker_scope,original_observer_independent_metadata_review=checked,
            expected_only_precommitted_stop_and_declared_slot_EOF_errors=True,
            all_declared_MAME_exit0_threads_journals_and_inputs_closed_verified=True,
            active_duration_s=rate['midpoint_elapsed_s'],resources=resources,
            raw_startup_main_health_and_measurement_review_pending=True,quality_qualified=False,created_unix_s=time.time()))
        review_dir=d/'independent-original-active600-CPU-original01'
        assert not review_dir.exists();review_dir.mkdir(mode=0o700)
        template=N/'selector-active600-counterbalanced-engineering-original01/01-A1-baseline/independent-original-active600-CPU-original01/job.json'
        old=self.read(self.h.pin(template))
        source=self.record['reviewer']
        sources=self.read(self.h.pin(P/'CPU-fixture-index-v2.json'))['cases']
        components=next(c['sources']for c in sources if c['role']==self.record['role'])
        review={key:old[key]for key in ('helpers','reader','archive','initial_helpers')}
        review.update(schema='robotron-evaluator-count-active600-independent-review-job-v1',
            output=str(review_dir/'output-original01'),native_job=self.record['native_job'],native_result=result_pin,
            native_owner=owner_pin,native_closure=closure_pin,native_config=self.record['launch_config'],
            native_controller=self.record['native_controller'],original_wire_auditor=components['wire'],
            quota_game_auditor=components['games'],quota_runtime=components['drain'],
            source_family_guard_closeout=self.record['source_guard_closeout'],original_terminal_readback=terminal,
            selector_measurement_reader=family['independent_measurement_reader'],main_rate_reader=self.job['main_rate_reader'],
            engineering_design=self.qualified['design'])
        auditor=load('_capacity_review_quota_descriptor',Path(components['games']['path']),components['games']['sha256'])
        drain=load('_capacity_review_drain_descriptor',Path(components['drain']['path']),components['drain']['sha256'])
        assert auditor.COHORT_SELECTION==drain.COHORT_SELECTION
        assert auditor.ACTOR_COUNT==drain.ACTOR_COUNT==self.count
        pins=[v for v in review.values()if isinstance(v,dict)and {'path','sha256','bytes'}<=v.keys()]
        pins += [source,self.h.pin(__file__),*self.job['inputs']]
        review['inputs']=list({p['path']:p for p in pins}.values())
        review_pin=self.h.put(review_dir/'job.json',review)
        cfg=dict(unit='robotron-capacity64-'+self.case.lower()+'-independent-review-original06-20261026.service',
                 output=str(review_dir/'execution-original01'),
                 argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--job',review_pin['path'],
                       '--job-sha256',review_pin['sha256'],'--source-sha256',source['sha256']],
                 properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=660','TasksMax=128',
                             'TimeoutStopSec=5','SendSIGKILL=no'],observation_s=720,
                 pins=[self.cpu.pin(p['path'])for p in [review_pin,source,*review['inputs']]])
        cfg_pin=self.h.put(review_dir/'controller-config.json',cfg)
        assert self.cpu.checked_config(cfg_pin['path'])==cfg
        self.h.put(review_dir/'original-review-precommit.json',dict(native_terminal=terminal,review_job=review_pin,
            review_source=source,review_config=cfg_pin,original_attempt=1,no_retry=True,
            independent_full_raw_startup_main_and_runtime_review_required=True,quality_qualified=False))
        print(json.dumps(dict(terminal_closeout=terminal,review_job=review_pin,review_config=cfg_pin)),flush=True)

    def close_reviewed(self,session,observed_exit):
        assert session>0 and observed_exit==0
        d=self.directory;review_dir=d/'independent-original-active600-CPU-original01'
        closer=load('_capacity_case_CPU_closer',G/'tools/training_connection_lifecycle_proposal_20261023/independent_component_closeout_v3.py')
        cpu_scope=closer.closeout(review_dir,self.h,self.arc,self.read,0)
        owner=cpu_scope['owner'];closure=cpu_scope['closure'];cfg=self.h.pin(review_dir/'controller-config.json')
        reviewer_scope=self.scope(owner,closure,cfg,0,2,4<<30,660,128,5)
        report_pin=self.h.pin(review_dir/'output-original01/report.json');report=self.read(report_pin)
        assert report['schema']=='robotron-evaluator-count-active600-independent-review-v1'
        assert report['historical_transient_and_selected_coalescing_provenance_verified'] is True
        provenance=report['protocol_provenance']
        assert provenance['all_historical_derivations_and_retained_function_AST_verified'] is True
        assert provenance['selected_running_publisher_exact_source_and_guarded_behavior_verified'] is True
        assert provenance['coalescing_protocol_CPU']==self.qualified['observer_protocol_CPU']
        assert provenance['current_context_observer_CPU']==self.qualified['current_main_context_CPU']
        assert provenance['selected_protocol']==self.read(self.job['source_family_manifest'])['main_observer']['protocol']
        assert report['declared_actor_count']==self.count and len(report['all_declared_original_startup_prefixes'])==self.count
        prefixes=report['all_declared_original_startup_prefixes']
        assert [r['slot']for r in prefixes]==self.job['actor_slots']
        assert all(r['all1200_original_pairs_and_loaded_ROM_verified']is True for r in prefixes)
        assert report['native_job']==self.record['native_job']and report['native_result']['path']==str(Path(self.job['output'])/'result.json')
        for key in ('native_expected_exit1_verified','all_native_archives_resources_commands_pins_release_verified',
                    'private_resources_free','native600_load_requirement_achieved',
                    'all_original_fixed_query_kernel_epochs_and_raw_headers_independently_replayed'):
            assert report[key]is True
        assert report['quality_qualified']is report['scientific_case']is False
        raw=report['raw_replay'];assert raw['samples']==len(report['kernel_epochs'])and raw['deep_samples']>=100
        assert raw['maximum_observation_gap_s']<=.5
        measured=report['timing_analysis']
        assert measured['actor_count']==self.count and measured['active_duration_ns']>=600000000000
        assert measured['all_declared_original_slot_identities_and_counter_advances_verified']is True
        assert measured['all_active_statuses_advance_every_slot']is True
        assert measured['exact_rates_and_descriptive_costs_recomputed_without_runtime_measurement_helper']is True
        assert measured['selector_CPU_cross_shape_comparison_used']is False
        assert measured['main_rates']['both_optimizer_endpoints_fully_classified']is True
        terminal_pin=self.h.pin(d/'independent-original-native-observer-terminal-closeout.json');terminal=self.read(terminal_pin)
        assert terminal['native_job']==report['native_job']and terminal['native_result']==report['native_result']
        # Recheck the originally archived scopes without replaying/retrying them.
        for scope in (terminal['native_scope'],terminal['observer_scope']):
            actual=self.read(scope['owner'])
            assert birth(actual['pid'])!=actual['starttime_ticks']
            for unit in (actual['unit'],actual['timer']):assert self.control.show(unit)['LoadState']=='not-found'
        prior=[]
        for name in ORDER[:ORDER.index(self.case)]:
            pin=self.h.pin(E/name/'independent-original-capacity64-case-closeout.json');p=self.read(pin)
            assert p['status']=='VALID_ORIGINAL_CAPACITY64_ENGINEERING_CASE_NO_QUALITY'and p['case']==name
            prior.append(pin)
        # The original independent reviewer checked GPU/ports/lease after raw
        # replay; no later private case may have started before this closeout.
        for name in ORDER[ORDER.index(self.case)+1:]:
            assert not(E/name/'execution-original01').exists()
        outcome=self.read(terminal['original_observer_independent_metadata_review']['worker_outcome'])
        publication_stats=outcome['running_projection_publication_stats']
        assert publication_stats['attempts']==publication_stats['published']+publication_stats['coalesced_busy_reader']==outcome['observed_samples']
        assert publication_stats['errors']==0 and publication_stats['published']>0
        proof=dict(running_projection_publication_stats=publication_stats,schema='robotron-capacity64-original-case-independent-closeout-v1',
            status='VALID_ORIGINAL_CAPACITY64_ENGINEERING_CASE_NO_QUALITY',case=self.case,
            native_job=report['native_job'],native_result=report['native_result'],independent_report=report_pin,
            actual_native_tool_session=terminal['actual_native_tool_session'],actual_native_exit=1,actual_observer_exit=0,
            actual_reviewer_tool_session=session,actual_reviewer_exit=0,
            native_and_observer_terminal_closeout=terminal_pin,independent_reviewer_scope=reviewer_scope,
            original_owners=[terminal['native_scope']['owner'],terminal['observer_scope']['owner'],owner],
            all_native_observer_reviewer_archives_resources_pins_and_release_verified=True,
            all_declared_original_MAME_exit0_and_ROM1200_prefixes_verified=True,
            declared_actor_count=self.count,actual64_live_startup_verified=self.count==64,
            raw_samples=raw['samples'],deep_samples=raw['deep_samples'],maximum_observation_gap_s=raw['maximum_observation_gap_s'],
            active_duration_ns=measured['active_duration_ns'],active_accepted_frames=measured['accepted_frames'],
            accepted_frame_FPS=measured['aggregate_accepted_frame_FPS'],main_rates=measured['main_rates'],
            private_resources_free=True,prior_original_valid_closeouts=prior,completed_valid_originals=len(prior)+1,
            A_reference_not_fixed_until_all4_reviewed=True,B_gates_not_evaluated=True,
            quality_qualified=False,full_game_wall_time_gain_verified=False,learning_speed_gain_verified=False,
            useful_training_throughput_gain_verified=False,created_unix_s=time.time())
        pin=self.h.put(d/'independent-original-capacity64-case-closeout.json',proof)
        print(json.dumps(dict(closeout=pin,completed_valid_originals=len(prior)+1)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group();modes.add_argument('--prepare-review',action='store_true');modes.add_argument('--close-reviewed-case',action='store_true')
    p.add_argument('--case',choices=ORDER);p.add_argument('--observed-session',type=int);p.add_argument('--observed-exit',type=int)
    a=p.parse_args()
    if not(a.prepare_review or a.close_reviewed_case):print('PLAN_ONLY')
    else:
        assert a.case is not None and a.observed_session is not None
        c=CloseOriginal(a.case)
        if a.prepare_review:c.prepare_review(a.observed_session,a.observed_exit)
        else:c.close_reviewed(a.observed_session,a.observed_exit)
