"""One Root-selected continuous stop; exact inherited Linux/service kernels.

No work at import. Only an explicitly selected zero-frame FIFO probe; no
measurement/control edit, replacement or retry.
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
KERNEL=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-engineering-fullstate-preservation-original03-20261101/sources/stop_owned_current_round_training_v3.py')
KERNEL_SHA='32fb1bdb6a5242229e7f7991c045117edfe1a4ece9b0451962f9702d48284416'
FRONTIER_SOURCES={'connection_cleanup_receipts.py':'f27e38411238fcf62256e6b317836b757d31d5e0ac962ec8523dd380236d80ee',
    'game_journal.py':'6aa78cb40434793853d17a1032cc6454ac86b0168828848d9d390336ba8678f0'}
PROBE=dict(authorized=True,client_slot=1,eval_only=True,application_frames_to_send=0,
    scientific_or_natural_game_claimed=False)


def require(value,reason):
    if not value:raise ValueError(reason)


def load(path,sha,name):
    raw=Path(path).read_bytes();require(hashlib.sha256(raw).hexdigest()==sha,'Exact selected source required')
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def execute(job_pin,own_sha):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==own_sha,'Actual current stop producer changed')
    raw=Path(job_pin['path']).read_bytes();require(hashlib.sha256(raw).hexdigest()==job_pin['sha256'],'Actual stop job changed')
    job=json.loads(raw)
    require(job['schema']=='robotron-owned-current-round-stop-job-v1'and job['authorized']is True
        and job['operation_mode']=='CONTINUOUS_REMAINING_MAIN_AFTER_CLOSED_FLEET'
        and job['original_attempt']==1 and job['no_retry']is True,'Explicit one-shot current continuous operation required')
    old=load(KERNEL,KERNEL_SHA,'_unchanged_owned_stop_kernels')
    helper=load(job['current_inputs_source']['path'],job['current_inputs_source']['sha256'],'_current_stop_inputs')

    class CurrentStop(old.Stop):
        def preflight(self):
            self.live(self.owner);self.verify_preclosed_fleet()
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
            fleet_group=Path('/sys/fs/cgroup'+self.fleet['cgroup'])
            members=(set(map(int,(fleet_group/'cgroup.procs').read_text().split()))if fleet_group.exists()else set())
            require(not members,'Authenticated preclosed fleet cgroup became populated')
            for row in self.actor_births:
                if row['pid']not in members:continue
                proc=Path('/proc',str(row['pid']));parts=(proc/'stat').read_text().rsplit(')',1)[1].split()
                require(int(parts[1])==self.fleet['pid']and int(parts[19])==row['starttime_ticks']
                    and proc.stat().st_uid==os.getuid()and(proc/'cgroup').read_text().strip()=='0::'+self.fleet['cgroup']
                    and str((proc/'exe').resolve())==job['mame_executable']
                    and(proc/'cmdline').read_bytes().decode().rstrip('\0').split('\0')==job['actor_command'],
                    'Original physical actor birth/source/cgroup differs')
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

        def verify_preclosed_fleet(self):
            prior=helper.read(job['prior_failed_stop_outcome'])
            closed=helper.read(job['prior_original_scope_closeout'])
            original=helper.read(job['prior_original_stop_job'])
            require(prior['status']=='ORIGINAL_CONTINUOUS_STOP_INCOMPLETE'
                and prior['actual_stopped_authority']is None
                and prior['owned_hold_release_errors']==[]
                and prior['one_shot_manual_stop_requests']==dict(fleet=True,trainer=False)
                and closed['actual_exit']==1 and closed['all_original_controller_resources_closed']is True
                and original['trainer']==self.owner and original['fleet']==self.fleet,
                'Explicit original failed stop/fleet-only delivery and closed original scope required')
            original_scope=helper.read(closed['owner'])
            require(old.birth(original_scope['pid'])!=original_scope['starttime_ticks'],
                'Original failed operation still live; no continuation')
            require(old.birth(self.fleet['pid'])!=self.fleet['starttime_ticks'],
                'Preclosed original fleet remains live; never send another fleet stop')
            fields=old.show(self.fleet['unit'])
            require(all(fields.get(k)==v for k,v in dict(MainPID='0',ExecMainPID=str(self.fleet['pid']),
                ExecMainCode='1',ExecMainStatus='0',NRestarts='0',InvocationID=self.fleet['invocation_id']).items()),
                'Actual original fleet normal0/no-restart differs')
            archived=helper.read(job['prior_fleet_terminal_archive'])
            require(archived['owner']==self.fleet,'Prior actual fleet archive differs')
            command=helper.read(archived['archives']['show'])
            require(command['exit']==0 and command['argv']==['systemctl','--user','show',self.fleet['unit']],
                'Prior original fleet SHOW0 required')
            archived_fields=dict(line.split('=',1)for line in self.u.checked(command['stdout']).decode().splitlines()if'='in line)
            require(all(archived_fields.get(k)==fields[k]for k in
                ('MainPID','ExecMainPID','ExecMainCode','ExecMainStatus','NRestarts','InvocationID')),
                'Preclosed original fleet descriptor changed')
            population=helper.read(job['original_population'])
            require(population['trainer']==self.owner and population['fleet']==self.fleet,
                'Exact retained original population required')
            require(all(old.birth(a['pid'])!=a['starttime_ticks']for a in population['actors']),
                'An original actor remains live')
            group=Path('/sys/fs/cgroup'+self.fleet['cgroup'])
            require(not group.exists()or not(group/'cgroup.procs').read_text().strip(),
                'Preclosed original fleet cgroup populated')

        def close_population(self):
            self.verify_preclosed_fleet()
            require(self.signal_sent['fleet']is False,'Continuation must never resend fleet StopUnit')
            self.archive_unit(self.fleet,'fleet')
            self.wait(lambda:self.api()['client_count']==0,15,'Remaining ordinary clients did not disconnect')

        def candidates(self):
            # The original predicate still inspects EVERY nonpersistent
            # Thread/Timer. Temporarily stop HTTP admission so long-polling
            # dashboard requests cannot replenish that same census.
            if 'HTTP'in self.holds:return old.Stop.candidates(self)
            serial=getattr(self,'http_census_serial',0)+1;self.http_census_serial=serial
            kind='HTTP_CENSUS'+str(serial)
            self.hold(kind,'Thread-1 (serve')
            try:
                time.sleep(5.1)  # HTTP preview request declares a <=5s wait.
                result=old.Stop.candidates(self)
                self.event('http-sealed-census-'+str(serial)+'.json',dict(
                    HTTP_admission_hold=self.holds[kind],remaining_unfiltered_candidates=result,
                    no_thread_identity_excluded=True,original_census_kernel_unchanged=True))
                return result
            finally:self.release(kind)

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
            # Initially seal admission so no old actor reconnects during fleet closure.
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
            self.close_population()  # Unchanged one StopUnit/normal0/owned absence/client_count0 kernel.
            def old_handlers_gone():
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
                original_attempt=1,no_retry=True,replacement_started=False,payload_integrity_qualified=False)
            try:
                self.preflight();closure=self.close_inputs()
                selected=helper.read(job['current_selection']);selected.update(input_closure=closure,
                    fleet_terminal_archive=self.u.full_pin(self.out/'fleet-terminal-archive.json'),
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
                    no_managed_pause_or_prefetch_pause_claimed=True)
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
                outcome['prior_failed_stop_outcome']=job['prior_failed_stop_outcome']
                outcome['continuation_did_not_resend_fleet_stop']=self.signal_sent['fleet']is False
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
