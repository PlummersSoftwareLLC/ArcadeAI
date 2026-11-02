"""Observe the existing original case; run its precommitted review once on success.

No native relaunch, game signals, policy promotion or modification of main.
The review controller itself owns its single launch/observation/release.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

D=Path(__file__).resolve().parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'tools/startup_policy_journal_proposal'

def require(value,message):
    if not value:raise ValueError(message)

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def main():
    spec=importlib.util.spec_from_file_location('_review_after_original_helpers',B/'run_full_policy_startup_v3.py')
    h=importlib.util.module_from_spec(spec);sys.modules[spec.name]=h;spec.loader.exec_module(h)
    require(h.pin(spec.origin)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','Helper changed')
    cp=h.pin(D/'independent-review-execution-precommit.json')
    require(cp['sha256']=='c3e7d6bab67cda4d7ed5bbcd73debe453ebb00b9f2cc02f0fefe84fcbd26764a','Review execution precommit changed')
    commitment=json.loads(h.checked(cp).read_text())
    cfg=commitment['review_controller_config']
    require(cfg['sha256']=='d0038e893b241222a2934d067c6e37935519f835d7ba611e2ec6aea4ded9e0b4','Review config changed')
    source=commitment['review_controller_source']
    require(source['sha256']=='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','Review controller changed')
    ctl=h.load('_automatic_original_review_controller',h.checked(source))
    cfg_value=ctl.checked_config(h.checked(cfg))
    rd=h.load('_automatic_review_immutable_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    require(h.pin(rd.__file__)['sha256']=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','Reader changed')
    read=lambda entry,as_json=True:rd.read_pin(entry,as_json=as_json)
    owner=read(h.pin(D/'execution-original01/root-original-identity.json'))
    controller=read(h.pin(D/'controller-original-child.json'))
    require(owner['pid']==3032708 and owner['starttime_ticks']==77166040
        and owner['invocation_id']=='ffee2dfe38834d029ca4e2066cd226ae'
        and controller['pid']==3032478 and controller['starttime_ticks']==77165693,'Exact original case required')
    require(birth(owner['pid'])==owner['starttime_ticks']
        and birth(controller['pid'])==controller['starttime_ticks'],'Original native/controller must be live when this observer starts')
    require(not (D/'independent-review-controller-original-launch.json').exists()
        and not Path(cfg_value['output']).exists()
        and not (D/'independent-full-tail-review-original01').exists(),'Review already consumed or started')
    intent=h.put(D/'automatic-original-observer-intent.json',dict(source=h.pin(__file__),
        original_owner=owner,original_controller=controller,review_execution_precommit=cp,
        original_attempt=1,no_retry=True,main_runtime_changed=False,created_unix_s=time.time()))
    observer=h.put(D/'automatic-original-observer-live-identity.json',dict(pid=os.getpid(),
        birth=birth(os.getpid()),intent=intent,observed_live=True,observed_unix_s=time.time()))
    print(json.dumps(dict(state='OBSERVING_SAME_ORIGINAL',observer=observer)),flush=True)
    outcome=dict(schema='robotron-automatic-original-full-tail-and-review-once-outcome-v1',
        observer=observer,intent=intent,engineering_verified=False,quality_qualified=False,promotion=False,
        learning_speed_gain_verified=False,main_runtime_changed=False,original_attempt=1,no_retry=True,
        native_relaunched=False,review_launched=False)
    try:
        deadline=time.monotonic()+9900
        controller_gone_at=None
        while True:
            result_path=D/'controller-original-result.json'
            if result_path.exists()and result_path.stat().st_mode&0o777==0o444:break
            require(time.monotonic()<deadline,'Observer deadline reached; original state unknown, no retry')
            if birth(controller['pid'])!=controller['starttime_ticks']:
                if controller_gone_at is None:controller_gone_at=time.monotonic()
                require(time.monotonic()-controller_gone_at<40,'Original controller gone without a sealed result; no result inferred')
            time.sleep(5)
        native_controller_pin=h.pin(result_path);native_controller=read(native_controller_pin)
        outcome['native_controller_result']=native_controller_pin
        outcome['actual_native_controller_exit']=native_controller['actual_exit']
        require(native_controller['original_attempt']==1 and native_controller['no_retry']is True,
            'Original native controller receipt differs')
        require(birth(owner['pid'])!=owner['starttime_ticks']
            and birth(controller['pid'])!=controller['starttime_ticks'],'Original process remains; review forbidden')
        rt=h.load('_automatic_original_archived_closure',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
        require(h.pin(rt.__file__)['sha256']=='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','Closure reader changed')
        require(native_controller.get('closure')is not None,'Original native closure unavailable')
        native_closure=read(native_controller['closure'])
        fields=rt.archived_closure(native_closure,owner,read,exit_zero=False)
        outcome['native_closure']=native_controller['closure']
        outcome['actual_native_exit']=native_closure['original_exit']
        if native_controller['actual_exit']!=0 or native_closure['original_exit']!=0:
            outcome.update(status='ORIGINAL_NATIVE_INVALID_PRESERVED_REVIEW_NOT_LAUNCHED')
        else:
            reviewer=h.load('_automatic_original_review_preconditions',h.checked(commitment['reviewer']))
            native_config=json.loads((D/'controller-config.json').read_text())
            reviewer.validate_native_fields(fields,native_config,owner,rt.duration_seconds)
            for unit in (owner['unit'],owner['timer']):
                require(ctl.show(unit)['LoadState']=='not-found','Original native unit remains')
                require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists(),
                    'Original native cgroup remains')
            for entry in cfg_value['pins']:require(ctl.pin(entry['path'])==entry,'Review precommitted input changed')
            argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--config',cfg['path'],
                '--expected-source-sha256',source['sha256']]
            launch=h.put(D/'independent-review-controller-original-launch.json',dict(
                argv=argv,source=source,config=cfg,native_controller_result=native_controller_pin,
                native_closure=native_controller['closure'],observer_intent=intent,
                original_attempt=1,no_retry=True,unix_s=time.time()))
            outcome.update(review_launched=True,review_launch_intent=launch)
            with (D/'independent-review-controller-original-stdout.txt').open('xb')as stdout,\
                    (D/'independent-review-controller-original-stderr.txt').open('xb')as stderr:
                process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True)
                child=h.put(D/'independent-review-controller-original-child.json',dict(pid=process.pid,
                    birth=birth(process.pid),observed_live=process.poll()is None,intent=launch))
                print(json.dumps(dict(state='REVIEW_CONTROLLER_STARTED',child=child)),flush=True)
                code=process.wait()
                stdout.flush();stderr.flush();os.fsync(stdout.fileno());os.fsync(stderr.fileno())
                os.fchmod(stdout.fileno(),0o444);os.fchmod(stderr.fileno(),0o444)
            closure_path=Path(cfg_value['output'])/'root-original-result-and-owned-release.json'
            review_controller=h.put(D/'independent-review-controller-original-result.json',dict(
                actual_exit=code,original_attempt=1,no_retry=True,intent=launch,
                stdout=h.pin(D/'independent-review-controller-original-stdout.txt'),
                stderr=h.pin(D/'independent-review-controller-original-stderr.txt'),
                closure=h.pin(closure_path)if closure_path.exists()else None,ended_unix_s=time.time()))
            outcome.update(review_controller_result=review_controller,actual_review_controller_exit=code)
            require(closure_path.exists(),'Actual original review closure unavailable')
            review_closure=read(h.pin(closure_path))
            review_owner=read(h.pin(Path(cfg_value['output'])/'root-original-identity.json'))
            rt.archived_closure(review_closure,review_owner,read,exit_zero=False)
            for unit in (review_owner['unit'],review_owner['timer']):
                require(ctl.show(unit)['LoadState']=='not-found','Original review unit remains')
                require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',unit).exists(),
                    'Original review cgroup remains')
            require(birth(review_owner['pid'])!=review_owner['starttime_ticks'],'Original review process remains')
            report_pin=h.pin(D/'independent-full-tail-review-original01/review.json')
            report=read(report_pin)
            outcome.update(independent_review=report_pin,actual_review_payload_exit=review_closure['original_exit'],
                review_all6_archives_and_owned_release_verified=True)
            passed=code==review_closure['original_exit']==0 and report['valid']is True\
                and report['full_game_score_verified']is True and report['quality_qualified']is report['promotion']is False
            outcome.update(engineering_verified=passed,status='ORIGINAL_ENGINEERING_VERIFIED_NO_QUALITY_PROMOTION'
                if passed else 'ORIGINAL_ENGINEERING_REVIEW_INVALID_PRESERVED_NO_RETRY')
    except Exception as error:
        outcome.update(status='ORIGINAL_OBSERVATION_OR_REVIEW_FAILURE_PRESERVED_NO_RETRY',error=repr(error))
    outcome['ended_unix_s']=time.time()
    pin=h.put(D/'automatic-original-observer-outcome.json',outcome)
    print(json.dumps(dict(outcome=pin,status=outcome['status'],engineering_verified=outcome['engineering_verified'])),flush=True)
    return 0 if outcome['engineering_verified']else 1

if __name__=='__main__':sys.exit(main())
