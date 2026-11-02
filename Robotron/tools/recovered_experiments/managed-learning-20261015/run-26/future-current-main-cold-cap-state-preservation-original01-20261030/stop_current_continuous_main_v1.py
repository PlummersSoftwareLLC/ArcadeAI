"""One Root-selected continuous stop; exact inherited Linux/service kernels.

No work at import. No measurement probe, control edit, replacement or retry.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import signal
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
KERNEL=ROOT/'logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/stop-sources/stop_owned_current_round_training_v3.py'
KERNEL_SHA='fe4a804db13347a74af512bca37adaf9aeb4660025cc9efe373b22a086ded7db'


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
        and job['operation_mode']=='CONTINUOUS_INPUT_CLOSED_BUDGET_EXHAUSTED'
        and job['original_attempt']==1 and job['no_retry']is True,'Explicit one-shot current continuous operation required')
    old=load(KERNEL,KERNEL_SHA,'_unchanged_owned_stop_kernels')
    helper=load(job['current_inputs_source']['path'],job['current_inputs_source']['sha256'],'_current_stop_inputs')

    class CurrentStop(old.Stop):
        def preflight(self):
            self.live(self.owner);self.live(self.fleet)
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
            members=set(map(int,(Path('/sys/fs/cgroup'+self.fleet['cgroup'])/'cgroup.procs').read_text().split()))
            selected_pids={v['pid']for v in self.actor_births}
            require(self.fleet['pid']in members and members<={self.fleet['pid'],*selected_pids},'Foreign original fleet cgroup member')
            for row in self.actor_births:
                if row['pid']not in members:continue
                proc=Path('/proc',str(row['pid']));parts=(proc/'stat').read_text().rsplit(')',1)[1].split()
                require(int(parts[1])==self.fleet['pid']and int(parts[19])==row['starttime_ticks']
                    and proc.stat().st_uid==os.getuid()and(proc/'cgroup').read_text().strip()=='0::'+self.fleet['cgroup']
                    and str((proc/'exe').resolve())==job['mame_executable']
                    and(proc/'cmdline').read_bytes().decode().rstrip('\0').split('\0')==job['actor_command'],
                    'Original physical actor birth/source/cgroup differs')
            self.api();self.old_handlers=self.candidates()
            self.event('current-stop-before-actions.json',dict(owner=self.owner,fleet=self.fleet,
                expected_current_cap=job['expected_current_cap'],actual_boot=self.anchor,
                original_population=job['original_population'],source=helper.pin(Path(__file__).resolve())))

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
            self.hold('GAME','Thread-4 (start')  # Exact source-bound accept task, inherited threaded cgroup seal.
            snapshot=self.uncached('/api/continuous_training_connections',524288)
            require(snapshot['schema']=='robotron-continuous-active-connections-v1','Exact active-token getter required')
            active={v['token']:v for v in snapshot['connections']}
            require(len(active)==len(snapshot['connections'])<=192,'Unique original active tokens required')
            originals={}
            for token,row in active.items():
                value=self.uncached('/api/connection_cleanup_token?'+urllib.parse.urlencode({'token':token}),70000)
                require(all(value[a]==row[b]for a,b in [('token','token'),('client_id','client_id'),
                    ('client_slot','client_slot'),('eval_only','eval_only'),('connection_ns','connection_ns'),
                    ('socket_endpoints','socket_endpoints')]), 'Original current TCP/token identity differs')
                originals[token]=value
            for evidence in job['historical_cleanup_receipts']:
                value=helper.read(evidence);token=value['token']
                require(token not in originals,'Historical/current token alias refused');originals[token]=value
            require(len(originals)<=512,'Bounded selected current/historical cleanup set required')
            initial=self.event('initial-current-connection-identities.json',snapshot)
            self.close_population()  # Exactly one original fleet StopUnit, normal0/archive, all recorded births absent.
            captured={}
            def drained():
                for token,prior in originals.items():
                    if token in captured:continue
                    value=self.uncached('/api/connection_cleanup_token?'+urllib.parse.urlencode({'token':token}),70000)
                    require(value['schema']=='robotron-prospective-connection-cleanup-receipt-v2'
                        and all(value[k]==prior[k]for k in ('token','server_stamp','client_id','client_slot',
                            'eval_only','connection_ns','socket_endpoints','handler_native_id','server_cleanup_incarnation')),
                        'Original handler/connection identity changed')
                    flags=('original_handler_stopped','original_owned_timer_stopped','owned_timer_callback_succeeded',
                        'journal_disconnect_succeeded','FIFO_reset_executed','replay_consumer_healthy')
                    require(all(type(value[k])is bool for k in flags),'Typed exact cleanup primitive results required')
                    if not all(value[k]is True for k in flags):continue
                    require(value['replay_admission_open']is True,'Healthy open replay consumer required')
                    require(value['cleanup_error']is None or value['cleanup_error']=='Original connection cleanup failed',
                        'Unknown recorded cleanup error refused')
                    require(value['ready_for_external_join']is (value['cleanup_error']is None),
                        'Original error/ready semantics must remain unchanged')
                    # This is only no-more-producers/FIFO/Timer evidence. No game completion,
                    # original cleanup success, CID reuse, refill or actor replacement is claimed.
                    captured[token]=self.event('closed-token-'+hashlib.sha256(token.encode()).hexdigest()+'.json',value)
                api=self.api();now=self.uncached('/api/continuous_training_connections',524288)
                return len(captured)==len(originals)and api['client_count']==0 and api['client_rows']==[]and now['connections']==[]and not self.candidates()
            self.wait(drained,60,'Original handlers/FIFO/Timer cleanup not positively complete')
            time.sleep(1.1);require(drained(),'Delayed original handler/Timer appeared')
            hold=self.holds['GAME'];group=Path(hold['path'])
            require(dict(x.split()for x in(group/'cgroup.events').read_text().splitlines()).get('frozen')=='1'
                and set(map(int,(group/'cgroup.threads').read_text().split()))=={hold['tid']},'Original GAME accept hold changed')
            sourcepins=job['current_source_pins']
            result=self.event('input-closure.json',dict(schema='robotron-Root-continuous-input-closure-v1',
                owner=self.owner,fleet=self.fleet,source=helper.pin(Path(__file__).resolve()),old_kernel=helper.pin(KERNEL),
                all_original_population_births_absent=True,all_GAME_handlers_and_FIFO_work_finished=True,
                no_deferred_callbacks_or_Timer_threads=True,GAME_listener_sealed_until_original_trainer_exit=True,
                GAME_hold=hold,initial_connections=initial,closed_tokens=captured,source_pins=sourcepins,
                evidence=[initial,*captured.values()],original_cleanup_success_CID_reuse_refill_or_quality_claimed=False))
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
