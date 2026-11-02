"""New one-shot maintenance continuation after an authenticated failed stop.

The fleet is already closed. New GAME holds and a new last zero-frame FIFO
frontier precede the unchanged original trainer SIGINT/save/archive kernels.
Prior input closure is history, never a presently held admission fence.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import signal
import socket
import struct
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
KERNEL=ROOT/'logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/stop-sources/stop_owned_current_round_training_v3.py'
KERNEL_SHA='fe4a804db13347a74af512bca37adaf9aeb4660025cc9efe373b22a086ded7db'
FRONTIER_SOURCES={'connection_cleanup_receipts.py':'f27e38411238fcf62256e6b317836b757d31d5e0ac962ec8523dd380236d80ee',
    'game_journal.py':'6aa78cb40434793853d17a1032cc6454ac86b0168828848d9d390336ba8678f0'}
PROBE=dict(authorized=True,client_slot=1,eval_only=True,application_frames_to_send=0,
    scientific_or_natural_game_claimed=False)


def require(value,reason):
    if not value:raise ValueError(reason)


def load(path,sha,name):
    raw=Path(path).read_bytes();require(hashlib.sha256(raw).hexdigest()==sha,'Exact selected source required')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


ARCHIVE_REVIEW=ROOT/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
ARCHIVE_REVIEW_SHA='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'
PARENT_STOP=Path(__file__).with_name('stop_current_continuous_main_fifo_frontier_v2.py')
PARENT_STOP_SHA='65baffacb24d2b93cfa97a337dd212f968e10e3af5cdbbec34247dde46a7345b'
CONTINUATION_KEYS={'failed_stop_job','failed_stop_config','failed_stop_outcome',
    'failed_controller_closeout','prior_fleet_terminal_archive','original_population'}


def validate_history(job,read):
    """Authenticate closed failure and fleet archives without issuing any action."""
    history=job['closed_fleet_continuation']
    require(set(history)==CONTINUATION_KEYS,'Exact selected closed-fleet history required')
    prior=read(history['failed_stop_job']);cfg=read(history['failed_stop_config'])
    outcome=read(history['failed_stop_outcome']);closed=read(history['failed_controller_closeout'])
    fleet=read(history['prior_fleet_terminal_archive']);population=read(history['original_population'])
    require(prior['schema']=='robotron-owned-current-round-stop-job-v1'
        and prior['operation_mode']=='CONTINUOUS_INPUT_CLOSED_BUDGET_EXHAUSTED'
        and prior['source']['path']==str(PARENT_STOP)and prior['source']['sha256']==PARENT_STOP_SHA
        and prior['trainer']==job['trainer']and prior['fleet']==job['fleet']
        and prior['expected_current_cap']==job['expected_current_cap']
        and prior['original_population']==history['original_population']==job['original_population']
        and population['trainer']==job['trainer']and population['fleet']==job['fleet'],
        'Same failed original maintenance job/owners/population/cap required')
    oldout=Path(prior['output'])
    require(history['failed_stop_outcome']['path']==str(oldout/'original-current-stop-outcome.json')
        and history['prior_fleet_terminal_archive']['path']==str(oldout/'fleet-terminal-archive.json')
        and outcome['status']=='ORIGINAL_CONTINUOUS_STOP_INCOMPLETE'
        and outcome['actual_stopped_authority']is None and outcome['original_attempt']==1
        and outcome['no_retry']is True and outcome['replacement_started']is False
        and outcome['payload_integrity_qualified']is False and outcome['owned_hold_release_errors']==[]
        and outcome['one_shot_manual_stop_requests']==dict(fleet=True,trainer=False),
        'Failed stop must retain fleet-only stop and released holds, without stopped authority')
    original=closed['original']
    require(closed['original_exit']==1
        and closed['status']=='ORIGINAL_AUDIT_NONZERO_PRESERVED_ARCHIVED_AND_RELEASED'
        and cfg['unit']==original['unit']
        and history['failed_controller_closeout']['path']==str(Path(cfg['output'])/'root-original-result-and-owned-release.json')
        and cfg['argv']==['/usr/bin/python3','-I','-B',prior['source']['path'],'--execute',
            '--job',history['failed_stop_job']['path'],'--job-sha256',history['failed_stop_job']['sha256'],
            '--source-sha256',prior['source']['sha256']], 'Exact failed C218 controller/job join required')
    reviewer=load(ARCHIVE_REVIEW,ARCHIVE_REVIEW_SHA,'_original_closed_failure_archive_checks')
    reviewer.archived_closure(closed,original,read,exit_zero=False)
    # A GC timer CAT1 is preserved as CAT1; its original positive launch is separate.
    launch=read(closed['timer_launch_archive'])
    require(launch['schema']=='robotron-root-exact-audit-timer-launch-archive-v1'
        and launch['unit']==original['unit']and launch['timer']==original['timer']
        and launch['timer_invocation_id']==original['timer_invocation_id']
        and launch['original_attempt']==1 and launch['no_retry']is True,'Original timer launch binding differs')
    intent=read(launch['launch_intent'])
    require(all(intent[k]==v for k,v in cfg.items())and intent['timer']==original['timer']
        and intent['no_retry']is True and intent['original_attempt']==1,
        'Original timer launch must select this exact failed controller configuration')
    for key,command in [('timer_cat','cat'),('timer_show','show')]:
        row=launch[key];require(row['argv']==['systemctl','--user',command,original['timer']]
            and row['exit']==0 and row['timed_out']is False,'Original timer launch archive not positive')
        read(row['stdout'],False);read(row['stderr'],False)
    fields=dict(x.split('=',1)for x in read(launch['timer_show']['stdout'],False).decode().splitlines()if'='in x)
    require(fields.get('Id')==original['timer']and fields.get('LoadState')=='loaded'
        and fields.get('InvocationID')==original['timer_invocation_id']and fields.get('Unit')==original['unit'],
        'Original live timer identity differs')
    for released in closed['owned_release']:
        row=released['final'];require(row['argv']==['systemctl','--user','show',released['unit']]
            and row['exit']==0 and row['timed_out']is False,'Positive original owned-release SHOW required')
        fields=dict(x.split('=',1)for x in read(row['stdout'],False).decode().splitlines()if'='in x)
        read(row['stderr'],False)
        require(fields.get('Id')==released['unit']and fields.get('LoadState')=='not-found',
            'Original failed controller/timer not positively absent after release')
    require(fleet['owner']==job['fleet']and set(fleet['archives'])=={'show','cat','journal'},
        'Exact prior fleet terminal archive required')
    for key in ('show','cat','journal'):
        row=read(fleet['archives'][key]);expected=(['journalctl','--user','-u',job['fleet']['unit'],
            '--no-pager','-o','short-monotonic']if key=='journal'else['systemctl','--user',key,job['fleet']['unit']])
        require(row['owner']==job['fleet']and row['argv']==expected and row['exit']==0,
            'Original fleet archive command/owner/exit differs')
        read(row['stdout'],False);read(row['stderr'],False)
        if key=='show':
            fields=dict(x.split('=',1)for x in read(row['stdout'],False).decode().splitlines()if'='in x)
            expected_fields=dict(Id=job['fleet']['unit'],InvocationID=job['fleet']['invocation_id'],MainPID='0',
                ExecMainPID=str(job['fleet']['pid']),ExecMainCode='1',ExecMainStatus='0',NRestarts='0',Result='success')
            require(all(fields.get(k)==v for k,v in expected_fields.items()),'Original fleet not same normal0/no-restart')
    return prior


def execute(job_pin,own_sha):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==own_sha,'Actual current stop producer changed')
    raw=Path(job_pin['path']).read_bytes();require(hashlib.sha256(raw).hexdigest()==job_pin['sha256'],'Actual stop job changed')
    job=json.loads(raw)
    require(job['schema']=='robotron-owned-current-round-stop-job-v1'and job['authorized']is True
        and job['operation_mode']=='CONTINUOUS_ALREADY_CLOSED_FLEET_FRESH_FIFO_BUDGET_EXHAUSTED'
        and job['original_attempt']==1 and job['no_retry']is True,'Explicit one-shot current continuous operation required')
    old=load(KERNEL,KERNEL_SHA,'_unchanged_owned_stop_kernels')
    helper=load(job['current_inputs_source']['path'],job['current_inputs_source']['sha256'],'_current_stop_inputs')

    class CurrentStop(old.Stop):
        def preflight(self):
            self.live(self.owner)
            def history_read(value,as_json=True):
                require(type(value['bytes'])is int and 0<=value['bytes']<=4<<20,'Bounded original metadata archive required')
                raw=self.u.checked(value)
                return json.loads(raw)if as_json else raw
            self.prior_job=validate_history(job,history_read)
            selected=helper.read(job['current_selection']);self.anchor=helper.startup_anchor(selected)
            require(selected['owner']==self.owner and selected['fleet']==self.fleet
                and selected['expected_current_cap']==job['expected_current_cap'], 'Same current owner/cap required')
            env=dict(x.split('=',1)for x in Path('/proc',str(self.owner['pid']),'environ').read_bytes().decode().split('\0')if'='in x)
            require(env.get('ROBOTRON_CONTINUOUS_TRAINING_MODE')=='1'
                and env.get('DQN_MAX_SAMPLES_PER_FRAME')==str(job['expected_current_cap'])
                and env.get('DQN_BATCH_SIZE')=='4096'and env.get('DQN_N_STEP')=='3'
                and env.get('DQN_PER_PRIORITY_METRIC')=='ce'
                and env.get('DQN_PRIORITY_PHASE_RECORD_SHA256')==self.anchor['phase_record']['sha256'],
                'Actual current mode/cap/recipe/phase environment differs')
            self.actor_births=helper.read(job['original_population'])['actors']
            require(helper.read(job['original_population'])['trainer']==self.owner
                and helper.read(job['original_population'])['fleet']==self.fleet
                and len(self.actor_births)<=192 and len({(v['pid'],v['starttime_ticks'])for v in self.actor_births})==len(self.actor_births),
                'Actual unique original population binding required')
            self.closed_population_absent()
            require(job['zero_frame_FIFO_probe']==PROBE,'Explicit Root-selected unused slot1 zero-frame EVAL probe required')
            require(set(job['FIFO_frontier_sources'])==set(FRONTIER_SOURCES),'Exact FIFO source companions required')
            for name,sha in FRONTIER_SOURCES.items():
                selected=job['FIFO_frontier_sources'][name]
                require(selected['path']==str(ROOT/'Scripts/dqn'/name)and selected['sha256']==sha
                    and helper.pin(selected['path'])==selected,'FIFO/zero-frame source companion changed')
            self.api();self.old_handlers=self.candidates()
            self.event('current-stop-before-actions.json',dict(owner=self.owner,fleet=self.fleet,
                expected_current_cap=job['expected_current_cap'],actual_boot=self.anchor,
                original_population=job['original_population'],source=helper.pin(Path(__file__).resolve())))

        def closed_population_absent(self):
            require(old.birth(self.fleet['pid'])!=self.fleet['starttime_ticks']
                and all(old.birth(a['pid'])!=a['starttime_ticks']for a in self.actor_births),
                'Prior original fleet/actor birth remains; never stop it a second time')
            group=Path('/sys/fs/cgroup'+self.fleet['cgroup'])
            require(not group.exists()or not(group/'cgroup.procs').read_text().strip(),
                'Prior fleet cgroup repopulated')
            fields=old.show(self.fleet['unit'])
            require(fields.get('MainPID')=='0'and fields.get('NRestarts','0')=='0'
                and(fields.get('LoadState')=='not-found'or(fields.get('InvocationID')==self.fleet['invocation_id']
                    and fields.get('ExecMainPID')==str(self.fleet['pid'])and fields.get('ExecMainCode')=='1'
                    and fields.get('ExecMainStatus')=='0'and fields.get('Result')=='success')),
                'Prior fleet service is live, replaced, restarted or not normal0')
            return True

        def uncached(self,path,limit):
            self.live(self.owner)
            with urllib.request.urlopen('http://127.0.0.1:8771'+path,timeout=5)as r:raw=r.read(limit+1)
            require(len(raw)<=limit,'Bounded uncached cleanup evidence required');value=json.loads(raw)
            stamp=dict(pid=self.owner['pid'],birth=self.owner['starttime_ticks'],source_sha256=helper.CURRENT_SHAS['socket_server.py'])
            require(value['server_stamp']==stamp and value['continuous_training_mode']is True
                and value['main_measurement_entry_disabled']is True and value['measurement_active']is False,
                'Same original continuous server/uncached evidence required')
            require(0<=time.time()-value['observed_unix_s']<=5,'Fresh uncached original receipt required')
            return value

        def close_inputs(self):
            # Acquire a NEW seal; the failed attempt released all of its holds.
            self.hold('GAME_INITIAL','Thread-4 (start')
            snapshot=self.uncached('/api/continuous_training_connections',524288)
            require(snapshot['schema']=='robotron-continuous-active-connections-v1','Exact active-token getter required')
            active={v['token']:v for v in snapshot['connections']}
            require(len(active)==len(snapshot['connections'])<=192,'Unique original active tokens required')
            originals={}
            for token,row in active.items():
                value=self.uncached('/api/connection_cleanup_token?'+urllib.parse.urlencode({'token':token}),70000)
                require(all(value[a]==row[b]for a,b in [('token','token'),('client_id','client_id'),
                    ('client_slot','client_slot'),('eval_only','eval_only'),('connection_ns','connection_ns'),
                    ('socket_endpoints','socket_endpoints')]),'Original current TCP/token identity differs')
                originals[token]=value
            for evidence in job['historical_cleanup_receipts']:
                value=helper.read(evidence);token=value['token']
                require(token not in originals,'Historical/current token alias refused');originals[token]=value
            require(len(originals)<=512,'Bounded selected current/historical cleanup set required')
            initial=self.event('initial-current-connection-identities.json',snapshot)
            self.closed_population_absent()  # Authenticate/observe prior closure; no second FleetStop.
            def old_handlers_gone():
                self.closed_population_absent()
                api=self.api();current=self.uncached('/api/continuous_training_connections',524288)
                return api['client_count']==0 and api['client_rows']==[]and current['connections']==[]and not self.candidates()
            self.wait(old_handlers_gone,60,'Old handler/Timer producer remains; no FIFO frontier can be created')
            time.sleep(1.1);require(old_handlers_gone(),'Delayed old handler/Timer producer appeared')
            captured={}
            identity_keys=('token','server_stamp','client_id','client_slot','eval_only','connection_ns',
                'socket_endpoints','handler_native_id','server_cleanup_incarnation')
            for token,prior in originals.items():
                value=self.uncached('/api/connection_cleanup_token?'+urllib.parse.urlencode({'token':token}),70000)
                require(value['schema']=='robotron-prospective-connection-cleanup-receipt-v2'
                    and all(value[k]==prior[k]for k in identity_keys),'Original handler/connection identity changed')
                # Preserve original failures, raw readyFalse, and primitive results. This is
                # not a retroactive historical cleanup-success or CID-reuse classification.
                captured[token]=self.event('historical-token-'+hashlib.sha256(token.encode()).hexdigest()+'.json',value)
            before=self.api()
            require(before['client_count']==0 and before['client_rows']==[]and not self.candidates(),
                'No ordinary handler may survive the initial GAME hold')
            clock_keys=('frame_count','measurement_frames','learner_frame_count')
            frame_floor={k:before[k]for k in clock_keys}
            require(all(type(v)is int and v>=0 for v in frame_floor.values()),'Typed original frame clocks required')
            game_floor={k:before[k]for k in('eval_games','eval_life_count')}
            require(type(game_floor['eval_games'])is dict and type(game_floor['eval_life_count'])is int,
                'Actual original eval-game/life summaries required')
            gap_before=self.final_API
            before_native=self.candidates();require(before_native=={},'Old producer appeared before owned admission gap')
            intent=self.event('zero-frame-FIFO-probe-intent.json',dict(authority=job['zero_frame_FIFO_probe'],
                before_API=gap_before,initial_GAME_hold=self.holds['GAME_INITIAL'],original_attempt=1,no_retry=True,
                only_wire_bytes=struct.pack('>H',(1<<14)|(1<<1)).hex(),
                selected_source_companions=job['FIFO_frontier_sources']))
            # Only this admission gap is reopened. No application frame or marker is sent.
            self.release('GAME_INITIAL')
            self.probe=socket.create_connection(('127.0.0.1',9998),timeout=3)
            self.probe.settimeout(3)
            self.probe.sendall(struct.pack('>H',(1<<14)|(1<<1)))
            endpoint=dict(server=list(self.probe.getpeername()),peer=list(self.probe.getsockname()))
            probe_identity=None
            def registered():
                nonlocal probe_identity
                api=self.api();current=self.uncached('/api/continuous_training_connections',524288)
                require(all(api[k]==frame_floor[k]for k in clock_keys)
                    and all(api[k]==v for k,v in game_floor.items()),'Unexpected frame/game/life during owned probe admission gap')
                if api['client_count']!=1 or len(api['client_rows'])!=1 or len(current['connections'])!=1:return False
                row=api['client_rows'][0];connection=current['connections'][0]
                require(row['client_slot']==1 and row['eval']is True and row['session_seconds']==0
                    and connection['client_id']==row['client_id']and connection['client_slot']==1
                    and connection['eval_only']is True and connection['socket_endpoints']==endpoint
                    and connection['token']not in originals,'Only exact owned zero-frame EVAL TCP is allowed')
                value=self.uncached('/api/connection_cleanup_token?'+urllib.parse.urlencode({'token':connection['token']}),70000)
                require(value['schema']=='robotron-prospective-connection-cleanup-receipt-v2'
                    and all(value[k]==connection[k]for k in('token','client_id','client_slot','eval_only','connection_ns','socket_endpoints'))
                    and value['original_handler_stopped']is False and value['terminal_receipt']is None,
                    'Owned probe receipt/source identity differs or already ended')
                if probe_identity is not None:
                    require(all(value[k]==probe_identity[k]for k in identity_keys),'Owned probe token/native identity changed')
                native=self.candidates();tid=value['handler_native_id']
                require(type(tid)is int and tid not in before_native,'Owned probe native task was not fresh')
                if set(native)!={tid}:return False
                require(native[tid]['wchan'].startswith('poll_schedule_timeout'),'Owned probe is not in zero-frame receive wait')
                if probe_identity is not None:
                    require(native[tid]==self.probe_tid,'Original probe native birth/name/wait identity changed')
                self.probe_tid=native[tid];self.probe_id=row['client_id'];probe_identity=value
                return True
            self.wait(registered,10,'Exact owned zero-frame EVAL probe did not register; never retry')
            self.hold('GAME','Thread-4 (start')
            require(registered(),'Unknown connection/task appeared before GAME reseal')
            time.sleep(1.1);require(registered(),'Probe/frame/native identity changed after admission gap')
            gap_after=self.final_API
            probe_before=self.event('zero-frame-FIFO-probe-before-close.json',dict(receipt=probe_identity,
                native=self.probe_tid,API=gap_after,frame_counts=frame_floor,eval_summaries=game_floor,GAME_hold=self.holds['GAME']))
            # All other handlers and Timers have ended BEFORE this reset is enqueued.
            # The selected sole consumer sets its ACK only after every older FIFO command.
            self.probe.shutdown(socket.SHUT_RDWR);self.probe.close();self.probe=None
            probe_closed=None
            flags=('original_handler_stopped','original_owned_timer_stopped','owned_timer_callback_succeeded',
                'journal_disconnect_succeeded','FIFO_reset_executed','replay_consumer_healthy')
            def frontier_complete():
                nonlocal probe_closed
                value=self.uncached('/api/connection_cleanup_token?'+urllib.parse.urlencode({'token':probe_identity['token']}),70000)
                require(value['schema']=='robotron-prospective-connection-cleanup-receipt-v2'
                    and all(value[k]==probe_identity[k]for k in identity_keys),'Owned FIFO frontier identity changed')
                require(all(type(value[k])is bool for k in flags),'Typed owned frontier primitive results required')
                api=self.api();current=self.uncached('/api/continuous_training_connections',524288)
                require(all(api[k]==frame_floor[k]for k in clock_keys)
                    and all(api[k]==v for k,v in game_floor.items()),'A frame/game/life appeared after owned admission gap')
                if not all(value[k]is True for k in flags):return False
                require(value['replay_admission_open']is True and value['cleanup_error']is None
                    and value['ready_for_external_join']is True and value['terminal_receipt']is None
                    and value['terminal_line_sha256']is None,'Owned zero-frame cleanup frontier was not successful')
                if api['client_count']!=0 or api['client_rows']!=[]or current['connections']!=[]or self.candidates():return False
                probe_closed=value;return True
            self.wait(frontier_complete,15,'Owned last FIFO reset/handler/Timer frontier incomplete')
            time.sleep(1.1);require(frontier_complete(),'Post-frontier producer/frame/consumer changed')
            probe_after=self.event('zero-frame-FIFO-probe-after-close.json',dict(receipt=probe_closed,API=self.final_API,
                original_owned_probe_closed=True,all_older_FIFO_commands_completed=True,
                measurement_pause_or_application_frame_sent=False,game_completion_or_refill_authority_claimed=False))
            hold=self.holds['GAME'];group=Path(hold['path'])
            require(dict(x.split()for x in(group/'cgroup.events').read_text().splitlines()).get('frozen')=='1'
                and set(map(int,(group/'cgroup.threads').read_text().split()))=={hold['tid']},'Original GAME accept hold changed')
            result=self.event('input-closure.json',dict(schema='robotron-Root-continuous-input-closure-v1',
                owner=self.owner,fleet=self.fleet,source=helper.pin(Path(__file__).resolve()),old_kernel=helper.pin(KERNEL),
                closed_fleet_continuation=job['closed_fleet_continuation'],prior_input_closure_adopted=False,
                all_original_population_births_absent=True,all_GAME_handlers_and_FIFO_work_finished=True,
                no_deferred_callbacks_or_Timer_threads=True,GAME_listener_sealed_until_original_trainer_exit=True,
                GAME_hold=hold,initial_connections=initial,historical_tokens_preserved_without_success_reclassification=captured,
                FIFO_frontier=dict(intent=intent,before_close=probe_before,after_close=probe_after,
                    before_gap_API=gap_before,after_gap_API=gap_after,unchanged_frame_counts=frame_floor,
                    unchanged_eval_summaries=game_floor,source_receipt_book_maximum_records=4096,
                    source_capacity_at_least_original192_plus_probe=True,runtime_remaining_capacity_claimed=False,
                    source_companions=job['FIFO_frontier_sources'],owned_probe_not_a_physical_actor=True),
                source_pins=job['current_source_pins'],evidence=[initial,*captured.values(),intent,probe_before,probe_after],
                original_cleanup_success_CID_reuse_refill_or_quality_claimed=False))
            return result

        def run(self):
            outcome=dict(status='ORIGINAL_CONTINUOUS_STOP_INCOMPLETE',actual_stopped_authority=None,
                original_attempt=1,no_retry=True,replacement_started=False,payload_integrity_qualified=False,
                closed_fleet_continuation=job['closed_fleet_continuation'],second_fleet_stop_requested=False)
            try:
                self.preflight();closure=self.close_inputs()
                selected=helper.read(job['current_selection']);selected.update(input_closure=closure,
                    fleet_terminal_archive=job['closed_fleet_continuation']['prior_fleet_terminal_archive'],
                    parent_Root_selection=job['current_selection'],input_closure_producer=helper.pin(Path(__file__).resolve()))
                context=self.event('actual-current-stop-selection.json',selected)
                end=time.monotonic()+180
                while True:
                    try:seal=helper.seal(context,self.out/'budget-seal');break
                    except ValueError:
                        require(not(self.out/'budget-seal').exists(),'A partial seal is never retried')
                        require(time.monotonic()<end,'Existing selected cap budget did not positively exhaust')
                        time.sleep(.2)
                old_authority=self.stop_trainer(seal)  # Exact original SIGINT/final-console/archives/no-retry kernels.
                actual=helper.read(old_authority);actual.update(schema='robotron-continuous-budget-stopped-preservation-authority-v1',
                    original_selection=context,fleet=self.fleet,fleet_terminal_archive=selected['fleet_terminal_archive'],
                    no_managed_pause_or_prefetch_pause_claimed=True,
                    closed_fleet_continuation=job['closed_fleet_continuation'],prior_input_closure_adopted=False)
                final=self.event('current-continuous-stopped-preservation-authority.json',actual)
                outcome.update(status='ORIGINAL_CONTINUOUS_OWNER_STOPPED_STRICT_CPU_AND_BACKUP_REQUIRED',
                    actual_stopped_authority=final,actual_current_selection=context,actual_bank_seal=seal)
            except BaseException as error:outcome['error']=repr(error)
            finally:
                failures=[]
                if self.probe is not None:
                    try:self.probe.close();self.probe=None
                    except BaseException as error:failures.append(dict(kind='owned-zero-frame-probe',error=repr(error)))
                for kind in list(self.holds):
                    try:self.release(kind)
                    except BaseException as error:failures.append(dict(kind=kind,error=repr(error)))
                outcome['owned_hold_release_errors']=failures;outcome['one_shot_manual_stop_requests']=self.signal_sent
                self.event('original-current-stop-outcome.json',outcome)
            return outcome

    value=CurrentStop(job).run()
    print(json.dumps(value),flush=True)
    return 0 if value['actual_stopped_authority']is not None and value['owned_hold_release_errors']==[]else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--job',type=Path);p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if a.execute:
        def interrupted(signum,frame):raise KeyboardInterrupt('Owned stop controller signal '+str(signum))
        for number in(signal.SIGINT,signal.SIGTERM):signal.signal(number,interrupted)
        raise SystemExit(execute(dict(path=str(a.job),sha256=a.job_sha256),a.source_sha256))
    print('PLAN_ONLY_NO_READS_OR_ACTIONS')
