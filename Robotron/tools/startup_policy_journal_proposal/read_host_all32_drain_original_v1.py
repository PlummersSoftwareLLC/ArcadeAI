"""Passive, one-use readback of the original eight host cohort-drain guards."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
D=G/'logs/managed-learning-20261015/run-26/host-all32-cohort-drain-contract-original01-preparation-20261022'


def require(value,message):
    if not value:raise ValueError(message)


def main():
    p=D.parent/'quality32-reference1597-vs-production1741-original01-preparation-20261021/winner-protection-original01-preparation-20261022/readback-original-final-disposition-v1.py'
    require(hashlib.sha256(p.read_bytes()).hexdigest()=='bae9e9c3e5eb552322285dc2422d5edd95549273aef58125e187f2305085fcdf','Helper source differs')
    spec=importlib.util.spec_from_file_location('_tail_wire_readback_helpers',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    output=D/'original-eight-host-all32-drain-independent-readback.json'
    require(not output.exists(),'Original readback already consumed')
    put=lambda p,v:m.put(p,(json.dumps(v,indent=2,allow_nan=False)+'\n').encode())
    intent=put(D/'original-eight-host-drain-readback-intent.json',dict(source=m.pin(__file__),original_attempt=1,no_retry=True,unix_s=time.time()))
    rd=m.load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','_tail_wire_reader')
    rt=m.load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_tail_wire_closure')
    ctl=m.load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_tail_wire_control')
    read=lambda e,as_json=True:rd.read_pin(e,as_json=as_json)
    pre=m.pin(D/'precommit.json');require(pre['sha256']=='24bbf01a1f3ffe407c9f47deb5be4467c8cbab0270f67b623d29da0458452428','Original precommit differs')
    commitment=read(pre)
    cfgp=m.pin(D/'controller-config.json');require(cfgp['sha256']=='32f42789c2b8ce941d5e9d6b6dc417ad95759670ba45f42b954852679f8ed637','Original config differs')
    cfg=read(cfgp)
    cp=m.pin(D/'controller-original-result.json');controller=read(cp)
    owner=read(m.pin(D/'execution-original01/root-original-identity.json'))
    require(controller['actual_exit']==0 and controller['original_attempt']==1 and controller['no_retry']is True,'Original actual controller exit differs')
    closure=read(controller['closure']);fields=rt.archived_closure(closure,owner,read,exit_zero=True)
    require(rt.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30)
        and fields['MemorySwapMax']=='0'and rt.duration_seconds(fields['RuntimeMaxUSec'])==180
        and fields['TasksMax']=='256'and rt.duration_seconds(fields['TimeoutStopUSec'])==5
        and fields['SendSIGKILL']=='no'and fields['Restart']=='no','Original resources differ')
    require(not Path('/proc',str(owner['pid'])).exists(),'Original payload remains')
    for unit in (owner['unit'],owner['timer']):
        require(ctl.show(unit)['LoadState']=='not-found','Original owned unit remains')
        require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists(),'Original cgroup remains')
    for entry in cfg['pins']:require(ctl.pin(entry['path'])==entry,'Original input changed')
    for entry in commitment['sources']:require(m.pin(entry['path'])==entry,'Full source identity changed')
    original_stderr=m.pin(D/'execution-original01/stderr.txt')
    raw_stderr=Path(original_stderr['path']).read_bytes()
    require(m.pin(original_stderr['path'])==original_stderr and hashlib.sha256(raw_stderr).hexdigest()==original_stderr['sha256'],'Terminal original stderr changed during capture')
    stderrp=m.put(D/'original-terminal-eight-host-drain-guard-stderr-captured444.txt',raw_stderr)
    stderr=read(stderrp,False).decode()
    cases=[line for line in stderr.splitlines()if line.startswith('test_')]
    require(len(cases)==8 and all(line.endswith(' ... ok')for line in cases)
            and '\nRan 8 tests in 'in stderr and stderr.rstrip().endswith('\nOK'),'Actual eight host-drain guard outcomes differ')
    require(sorted(line.split(' ',1)[0]for line in cases)==commitment['expected_new_methods'],'Precommitted original methods differ')
    require(cfg['argv']==['/usr/bin/python3.12','-I','-B',str(G/'tools/startup_policy_journal_proposal/test_cohort_drain_v1.py')],'Original host-drain guard entry differs')
    proof=put(output,dict(schema='robotron-host-all32-cohort-drain-original8-independent-readback-v1',
        status='PASS_EIGHT_ACTUAL_JOURNAL_AND_CONTROLLER_ALL32_HOST_DRAIN_GUARDS',source=m.pin(__file__),intent=intent,
        precommit=pre,controller_config=cfgp,original_controller_result=cp,original_closure=controller['closure'],
        actual_payload_exit=0,actual_controller_exit=0,all6_original_descriptors_verified=True,
        descriptor_actual_exits=[x['exit']for x in closure['full_original_archives']],
        original_pid_service_timer_cgroup_absent=True,actual_test_stderr=stderrp,original_terminal_stderr_identity=original_stderr,cases=cases,
        readonly_sources_unchanged=True,old_guard_methods_rerun=False,
        full_game_score_verified=False,quality_qualified=False,main_runtime_changed=False,
        limitations='Synthetic clocks/policy/ROM/accepted-input fixtures against unchanged source-bound GameJournal and ManagedMeasurement. All32 certified startup joins, pending/full tail, zero score, extra33rd late high-score tail, inclusive cutoff, source policy/window/clocks, one-use STOP, terminal reset and original membership guards passed. No actual neural-model/MAME/GPU full game, runtime/life validation or quality improvement is proved.',observed_unix_s=time.time()))
    print(json.dumps(dict(proof=proof,status='PASS_ORIGINAL_EIGHT_HOST_DRAIN_GUARDS')))
    return 0


if __name__=='__main__':sys.exit(main())
