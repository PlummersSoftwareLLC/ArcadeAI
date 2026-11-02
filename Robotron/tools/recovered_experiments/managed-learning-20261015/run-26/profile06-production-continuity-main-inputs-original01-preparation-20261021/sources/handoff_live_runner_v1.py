"""Prepare/own one original bounded live controller and independent rescue.

No action by default. Preparation creates immutable files only. Execution pins
all inputs, captures original systemd births and preserves actual outcomes.
Observation expiry leaves the same handles untouched and available to --observe.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'
H = RUN/'profile06-production-continuity-main-inputs-original01-preparation-20261021'
CASE = 'scorecarry-profile06-main-original01-20261021'
PREPARATION_NAME = 'profile06-production-continuity-live-controller-original01-preparation-20261021'


def load(path,name):
    spec = importlib.util.spec_from_file_location(name,path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def linux_module():
    return load(Path(__file__).parent/'handoff_linux_v1.py','_runner_linux')


def prepare(output):
    l = linux_module()
    l.require(output.parent == RUN and output.name == PREPARATION_NAME
              and not output.exists(),'One new original live preparation required')
    prepared_pin = l.full_pin(H/'prepared-inputs.json')
    p = json.loads(l.checked(prepared_pin))
    main = json.loads(l.checked(p['original_main']))
    guard_pin = l.full_pin(RUN/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
    guard = l.module(guard_pin,'_runner_prepare_guard')
    guard.owner_and_files(main)
    proofs = dict(
        contracts=l.full_pin(H/'current-owner-handoff-contracts-CPU-original01/root-independent-readback.json'),
        two_pause=l.full_pin(RUN/'future-handoff-threaded-accept-freeze-CPU-original05-two-pause-preparation-20261019/root-independent-readback.json'),
        recovery_before_commit=l.full_pin(RUN/'handoff-recovery-integration-CPU-original01-preparation-20261019/root-independent-readback.json'),
        recovery_save_pause=l.full_pin(H/'current-cgroup-save-recovery-kernel-original01/root-independent-readback.json'),
        CPU_bridge=l.full_pin(RUN/'future-handoff-poststop-CPU-bridge-original05-preparation-20261019/root-independent-readback.json'))
    for entry in proofs.values():
        value = json.loads(l.checked(entry))
        l.require(value['status'].endswith('PASS') or value['status'].endswith('VERIFIED'),'An actual component proof did not pass')
    contract = json.loads(l.checked(proofs['contracts']))
    for name,entry in contract['tested_sources'].items():
        l.require((Path(__file__).parent/name).read_bytes() == l.checked(entry),'A contract-tested source changed')
    bridge = json.loads(l.checked(proofs['CPU_bridge']))
    for entry in bridge['source_pins'].values():
        l.checked(entry)
    # The new historical CPU-bridge entry point does not alter committed
    # recovery. Authenticate its exact tested function bodies independently.
    recovery = json.loads(l.checked(proofs['recovery_save_pause']))
    old = ast.parse(l.checked(recovery['source_pins']['handoff_poststop_v1.py']))
    now = ast.parse((Path(__file__).parent/'handoff_poststop_v1.py').read_bytes())
    for name in ('recover_committed','load_linux','require'):
        body = lambda tree: [ast.dump(n,include_attributes=False) for n in tree.body
                             if isinstance(n,ast.FunctionDef) and n.name == name]
        l.require(body(old) == body(now) and len(body(now)) == 1,'Tested committed recovery changed')
    l.require(not (H/'live-original01').exists(),'This live output has already been consumed')
    output.mkdir(mode=0o700)
    sources = output/'sources'
    sources.mkdir()
    pins = {}
    for name in ('handoff_controller_v1.py','handoff_linux_v1.py','handoff_recovery_v1.py',
                 'handoff_poststop_v1.py','handoff_socket_seal_v1.py','handoff_live_runner_v1.py','bank_shutdown_intent_v1.py'):
        raw = (Path(__file__).parent/name).read_bytes()
        compile(raw,name,'exec')
        pins[name] = l.publish(sources/name,raw)
    dependencies = dict(reader=l.full_pin(GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'),
        raw_API=l.full_pin(GAME/'tools/eval_capacity_proposal/raw_api_witness_v1.py'),main_guard=guard_pin,
        bank_shutdown_intent=pins['bank_shutdown_intent_v1.py'],
        bank_witness=p['tested_bank_witness'],socket_seal=pins['handoff_socket_seal_v1.py'])
    poststop_result = json.loads((H/'poststop-inputs-original01/preparation-result.json').read_bytes())
    base_job = dict(schema='robotron-score-carry-live-handoff-job-v1',authorized=True,case=CASE,
        prepared=prepared_pin,output=str(H/'live-original01'),backend_source=pins['handoff_linux_v1.py'],
        recovery_source=pins['handoff_recovery_v1.py'],poststop_adapter=pins['handoff_poststop_v1.py'],
        poststop_inputs=poststop_result['poststop_inputs'],dependencies=dependencies,
        base_control_archive=poststop_result['base_control_archive'],base_control_sha256=poststop_result['base_control_sha256'],
        control_path=str(l.CONTROL),probe_endpoint=['192.168.1.131',9998])
    plan = dict(schema='robotron-original-score-carry-live-runner-plan-v1',authorized=True,case=CASE,
        output=str(output),sources=pins,runner_source=pins['handoff_live_runner_v1.py'],prepared=prepared_pin,
        controller_unit='robotron-'+CASE+'-controller.service',rescue_unit='robotron-'+CASE+'-rescue.service',
        base_live_job=base_job,live_job_path=str(output/'live-job.json'),live_output=base_job['output'],proofs=proofs,
        lifecycle_controller=l.full_pin(GAME/'tools/quality_capacity_proposal/control_quality32_review_v1.py'),
        archive_checker=l.full_pin(GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'),
        prior_original_owner=main['owner'],observation_s=1900,controller_runtime_s=1800,rescue_runtime_s=2300,
        main_source_changed=False,live_execution_started=False,goal_complete=False)
    guard.owner_and_files(main)
    return l.publish(output/'plan.json',plan)


class Runner:
    def __init__(self,plan):
        self.l = linux_module()
        self.plan = plan
        self.out = Path(plan['output'])
        self.l.require(plan['schema'] == 'robotron-original-score-carry-live-runner-plan-v1'
            and plan['authorized'] is True and plan['case'] == CASE
            and self.out.parent == RUN and self.out.name == PREPARATION_NAME,
            'One exact original live runner scope required')
        for entry in plan['sources'].values():
            self.l.checked(entry)
        self.c = self.l.module(plan['lifecycle_controller'],'_runner_original_lifecycle')
        self.reader = self.l.module(plan['base_live_job']['dependencies']['reader'],'_runner_original_reader')
        self.reviewer = self.l.module(plan['archive_checker'],'_runner_original_archive_checker')
        self.commands = 0

    def command(self,output,label,argv):
        return self.c.command(output,label,argv)

    def wait(self,predicate,seconds,message):
        deadline = time.monotonic()+seconds
        while time.monotonic()<deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.03)
        raise RuntimeError(message+'; preserve the same original handles')

    def launch(self,role,argv):
        l = self.l
        unit = self.plan[role+'_unit']
        timer = unit.removesuffix('.service')+'.timer'
        l.require(unit == 'robotron-'+CASE+'-'+role+'.service'
                  and role in ('rescue','controller'),'Unknown live unit scope')
        l.require(l.show(unit).get('LoadState') == l.show(timer).get('LoadState') == 'not-found',
                  'Original live unit or timer already exists; do not launch again')
        output = self.out/(role+'-unit')
        output.mkdir(mode=0o700)
        runtime = self.plan[role+'_runtime_s']
        l.require(runtime == (2300 if role == 'rescue' else 1800),'Live unit wall bound differs')
        properties = ['Type=exec','RemainAfterExit=yes','Restart=no','CPUQuota=200%',
            'MemoryMax='+('1G' if role == 'rescue' else '4G'),'MemorySwapMax=0','TasksMax=256',
            'RuntimeMaxSec='+str(runtime),'TimeoutStopSec=5','SendSIGKILL=no',
            'WorkingDirectory='+str(GAME.parent),'StandardOutput=append:'+str(output/'stdout.txt'),
            'StandardError=append:'+str(output/'stderr.txt')]
        actual = ['systemd-run','--user','--unit='+unit,'--on-active=3s','--timer-property=AccuracySec=100ms']
        actual += ['--property='+value for value in properties]
        actual += ['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
                   'PYTHONDONTWRITEBYTECODE=1']+argv
        l.publish(output/'launch-intent.json',dict(unit=unit,timer=timer,argv=argv,actual_argv=actual,
            properties=properties,original_attempt=1,restart_retry=False))
        record = self.command(output,'scheduling-carrier',actual)
        l.require(record['exit'] == 0 and not record['timed_out'],'Original scheduling outcome is uncertain; never retry')
        shown = self.command(output,'original-launch-timer-show',['systemctl','--user','show',timer])
        cat = self.command(output,'original-launch-timer-cat',['systemctl','--user','cat',timer])
        value = self.c.fields(shown)
        context = dict(unit=unit,timer=timer,timer_invocation_id=value['InvocationID'])
        l.require(self.c.timer_state(value,context) == 'original_loaded' and cat['exit'] == 0,
                  'Original timer launch archive is incomplete')
        l.publish(output/'original-timer-launch-archive.json',dict(**context,timer_show=shown,timer_cat=cat))
        def born():
            value = l.show(unit)
            pid = int(value.get('MainPID','0'))
            if not pid:
                return None
            owner = dict(pid=pid,starttime_ticks=l.process_start(pid),unit=unit,invocation_id=value['InvocationID'],
                cgroup=value['ControlGroup'],timer=timer,timer_invocation_id=context['timer_invocation_id'],observed_live=True)
            l.live_owner(owner)
            command = [x.decode() for x in Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if x]
            l.require(command == argv,'Original controller/rescue command differs')
            l.publish(output/'original-owner.json',owner)
            l.require(value.get('RuntimeMaxUSec') in (str(runtime*1000000),str(runtime)+'s',
                      '38min 20s' if role == 'rescue' else '30min'),
                      'Actual live runtime property differs')
            return owner
        owner = self.wait(born,15,'Original live birth has not been captured')
        return owner

    def close_if_terminal(self,role):
        l = self.l
        output = self.out/(role+'-unit')
        completed = output/'root-original-result-and-owned-release.json'
        if completed.exists():
            return json.loads(completed.read_bytes())
        owner_path = output/'original-owner.json'
        if not owner_path.exists():
            return None
        owner = json.loads(owner_path.read_bytes())
        value = l.show(owner['unit'])
        l.require(value.get('InvocationID') == owner['invocation_id'] and value.get('NRestarts') == '0'
                  and int(value.get('MainPID','0')) in (0,owner['pid']),'Original live unit identity changed')
        if value.get('MainPID') == str(owner['pid']):
            l.live_owner(owner)
            return None
        l.require(value.get('ExecMainPID') == str(owner['pid'])
                  and l.process_start(owner['pid']) != owner['starttime_ticks'],'Original live terminal birth differs')
        archives = []
        for kind,unit in (('service',owner['unit']),('timer',owner['timer'])):
            for action in ('show','cat','journal'):
                argv = ['journalctl','--user','--no-pager','-o','short-iso',
                    '_SYSTEMD_INVOCATION_ID='+owner['invocation_id' if kind == 'service' else 'timer_invocation_id']] if action == 'journal' else [
                    'systemctl','--user',action,unit]
                archives.append(self.command(output,'original-'+kind+'-'+action,argv))
        result = dict(original=owner,original_exec_code=int(value['ExecMainCode']),
            original_exit=int(value['ExecMainStatus']) if value['ExecMainCode'] == '1' else None,
            original_signal=int(value['ExecMainStatus']) if value['ExecMainCode'] != '1' else None,
            original_result=value['Result'],full_original_archives=archives,original_archived_before_release=True,
            payload_retried=False,owned_release=[],unit_released=False,lifecycle_complete=False)
        l.publish(output/'original-terminal-archive.json',result)
        l.require(all(row['exit'] == 0 and not row['timed_out'] for row in archives[:3]+archives[5:])
                  and archives[3]['exit'] == 0 and archives[4]['exit'] in (0,1),'Original descriptors are incomplete')
        if result['original_exec_code'] != 1:
            result['status'] = 'ORIGINAL_SIGNAL_ARCHIVED_NO_RESTART_OR_RELEASE'
            return json.loads(l.checked(l.publish(completed,result)))
        context = {k:owner[k] for k in ('unit','timer','timer_invocation_id')}
        self.c.original_terminal(l.show(owner['unit']),owner)
        for kind in ('timer','service'):
            record = {}
            result['owned_release'].append(record)
            self.c.release_original(output,kind,owner,context,record)
        l.require(all(row['confirmed_absent'] for row in result['owned_release']),'Original owned release incomplete')
        result.update(unit_released=True,lifecycle_complete=True,status='ORIGINAL_OUTCOME_ARCHIVED_AND_OWNED_RELEASED')
        read = lambda entry,as_json=True:self.reader.read_pin(entry,as_json=as_json)
        self.reviewer.archived_closure(result,owner,read,exit_zero=False)
        l.publish(completed,result)
        return result

    def observe(self):
        started = time.monotonic()
        closed = {}
        while time.monotonic()-started < self.plan['observation_s']:
            for role in ('controller','rescue'):
                if role not in closed:
                    value = self.close_if_terminal(role)
                    if value is not None:
                        closed[role] = value
            if len(closed) == 2:
                break
            time.sleep(.2)
        output = Path(self.plan['live_output'])/'result.json'
        outcome = json.loads(output.read_bytes()) if output.exists() else None
        result = dict(status='ORIGINAL_LIVE_HANDLES_OBSERVATION_PENDING',closed_roles=list(closed),
            original_closures=closed,controller_outcome=outcome,goal_complete=False,
            restart_retry=False,observed_unix_s=time.time())
        if len(closed) == 2:
            result['status'] = 'ORIGINAL_LIVE_CONTROLLER_AND_RESCUE_TERMINAL_ARCHIVED'
        suffix = str(time.time_ns())
        return self.l.publish(self.out/('root-observation-'+suffix+'.json'),result)

    def execute(self):
        l = self.l
        for value in self.plan['proofs'].values():
            l.checked(value)
        l.require(not (self.out/'execution-intent.json').exists(),'One original live execution only; use --observe')
        p = json.loads(l.checked(self.plan['prepared']))
        main = json.loads(l.checked(p['original_main']))
        guard = l.module(self.plan['base_live_job']['dependencies']['main_guard'],'_runner_execute_guard')
        guard.owner_and_files(main)
        l.publish(self.out/'execution-intent.json',dict(original_attempt=1,case=CASE,unix_s=time.time(),
            original_owner=main['owner'],restart_retry=False))
        rescue_job = dict(schema='robotron-score-carry-independent-rescue-job-v1',case=CASE,
            unit=self.plan['rescue_unit'],controller_unit=self.plan['controller_unit'],
            output=str(self.out/'rescue-output'),owner_path=str(self.out/'rescue-owner.json'),
            ready_path=str(self.out/'rescue-ready.json'),controller_source=self.plan['sources']['handoff_controller_v1.py'],
            recovery_source=self.plan['sources']['handoff_recovery_v1.py'],backend_source=self.plan['sources']['handoff_linux_v1.py'],
            prepared=self.plan['prepared'],live_job_path=self.plan['live_job_path'],live_output=self.plan['live_output'])
        rescue_pin = l.publish(self.out/'rescue-job.json',rescue_job)
        rescue_command = ['/usr/bin/python3.12','-I','-B',rescue_job['recovery_source']['path'],'--watch','--job',
                          rescue_pin['path'],'--expected-job-sha256',rescue_pin['sha256']]
        self.launch('rescue',rescue_command)
        self.wait(lambda: (self.out/'rescue-ready.json').exists(),15,'Original independent rescue has not become ready')
        live_job = dict(self.plan['base_live_job'],rescue_owner=l.full_pin(self.out/'rescue-owner.json'),
                        rescue_ready=l.full_pin(self.out/'rescue-ready.json'),rescue_job=rescue_pin,rescue_command=rescue_command)
        live_pin = l.publish(Path(self.plan['live_job_path']),live_job)
        command = ['/usr/bin/python3.12','-I','-B',self.plan['sources']['handoff_controller_v1.py']['path'],
                   '--execute','--job',live_pin['path'],'--expected-job-sha256',live_pin['sha256']]
        self.launch('controller',command)
        return self.observe()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--observe',action='store_true')
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--expected-plan-sha256')
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare(args.output)))
        return 0
    if not (args.execute or args.observe):
        print('PLAN_ONLY: no reads, outputs, queries or runtime actions')
        return 0
    l = linux_module()
    l.require(args.execute is not args.observe and args.plan and args.expected_plan_sha256
              and hashlib.sha256(args.plan.read_bytes()).hexdigest() == args.expected_plan_sha256,'Exact original plan required')
    plan = json.loads(args.plan.read_bytes())
    l.checked(plan['runner_source'])
    l.require(Path(plan['runner_source']['path']) == Path(__file__).resolve(),'Use the exact selected immutable runner')
    runner = Runner(plan)
    print(json.dumps(runner.execute() if args.execute else runner.observe()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
