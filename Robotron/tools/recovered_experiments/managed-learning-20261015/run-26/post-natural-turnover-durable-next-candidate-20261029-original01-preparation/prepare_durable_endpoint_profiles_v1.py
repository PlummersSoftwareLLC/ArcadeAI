"""Default inert. Future actual endpoint selection and existing profile envelopes.

Never launches CPU, GPU, MAME, controllers or studies. Only Root invokes an
explicit preparation/close mode after the original durable window has finished.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
CASE=B/'post-natural-turnover-durable-next-candidate-20261029-original01'
PROFILE=G/'tools/post_recovery_evaluation/prepare_and_close_profile_cpu_v2.py'
PROFILE_SHA='dc4b811b57b05e0a439ef2345d0dc73f6db42578b672511d13ec08ddda65ff8c'
CONTROLLER=G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'
CONTROLLER_SHA='218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'
PLAN_SHA='97206a8e82ff4f43f8d74b8ab564c682ef2504d2f3ec13195154f52888baee6a'
UNIT='robotron-durable-candidate-window-original01-20261029.service'
PID=4033444
BIRTH=12427111
INVOCATION='65c862e335c84b279e38494cf118487e'
CLOCKS=('learner_frame_count','training_steps','optimized_samples','frame_count')


def require(value,message):
    if not value:raise RuntimeError(message)


def metadata(path,expected=None):
    require(path.is_absolute() and not path.is_symlink() and path.is_file(), 'Actual regular metadata required')
    st=path.stat();require(st.st_size<=2<<20 and st.st_uid==os.getuid() and st.st_nlink==1
        and stat.S_IMODE(st.st_mode)==0o444, 'Owned immutable bounded metadata required: '+str(path))
    raw=path.read_bytes();require(path.stat()==st, 'Metadata changed during read')
    digest=hashlib.sha256(raw).hexdigest()
    if expected is not None:require(digest==expected,'Metadata source selection differs')
    return json.loads(raw),dict(path=str(path),sha256=digest,bytes=len(raw))


def profile_api():
    raw=PROFILE.read_bytes();require(hashlib.sha256(raw).hexdigest()==PROFILE_SHA,'Original profile preparer changed')
    require(hashlib.sha256(CONTROLLER.read_bytes()).hexdigest()==CONTROLLER_SHA,'Original CPU controller changed')
    spec=importlib.util.spec_from_file_location('_durable_endpoint_original_profiles',PROFILE)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m


def original_endpoint():
    # Check all original metadata before any output or profile/model-body read.
    plan,_=metadata(CASE/'window-plan.json',PLAN_SHA)
    result,rp=metadata(CASE/'result.json')
    anchor,ap=metadata(CASE/'anchor.raw.json');threshold,tp=metadata(CASE/'first-threshold.raw.json')
    authority,_=metadata(CASE/'entry-CPU-authority.json')
    report,cp=metadata(CASE/'endpoint-CPU.json');release,cl=metadata(CASE/'CPU-owned-release.json')
    require(result['state']=='captured_CPU_verified' and result['promotion']is False
        and result['quality_qualified']is False and result['owner']==plan['owner'], 'Original own completed capture required')
    require(plan['thresholds']==dict(applied_updates=5000,replay_inserts=1000000,elapsed_s=3600)
        and all(result['added'][key]>=value for key,value in plan['thresholds'].items()),'Own exposure thresholds not met')
    endpoint=result['endpoint'];require(endpoint['path']==str(CASE/'endpoint.pt')
        and endpoint==report['checkpoint'] and result['CPU_verification']==cp,'Actual selected endpoint/report binding differs')
    require(endpoint['sha256']not in {authority['endpoint']['sha256'],
        'a6e17a3c6cd8a9b6cb5479e6c6cbd1a284c1cd880372d0d02441680bc708e502',
        '444a14287789b26e3d84564cf4a9e49518d82d91d6a3ed82ca09526ef89c8523'},'A genuinely distinct endpoint is required')
    st=Path(endpoint['path']).stat();require(st.st_size==endpoint['bytes'] and stat.S_IMODE(st.st_mode)==0o444
        and st.st_uid==os.getuid() and st.st_nlink==1,'Immutable actual endpoint metadata differs')
    require(report['CUDA_initialized']is False and report['online_target_shapes_and_finiteness_verified']is True
        and report['priority_phase_valid']is True and report['Adam_parameters']==81
        and report['optimizer_lrs']==[3.125e-6] and report['Adam_step_min']>plan['entry_Adam_step'],
        'Actual new numerical/optimizer/CE recipe facts differ')
    for key in CLOCKS:
        require(type(report['clocks'][key])is int and report['clocks'][key]>=threshold[key]>=anchor[key],
            'Captured clocks predate own anchor/threshold')
    require(report['clocks']['training_steps']>anchor['training_steps'],'No actual saved update progression')
    own,terminal=release['original'],release['terminal']
    require(terminal['Id']==plan['CPU_unit'] and terminal['ExecMainPID']==own['MainPID']
        and terminal['InvocationID']==own['InvocationID'] and terminal['MainPID']=='0'
        and terminal['ExecMainCode']=='1' and terminal['ExecMainStatus']=='0'
        and release['original_birth_absent']is True and release['after_release']['ActiveState']=='inactive'
        and not Path('/proc',own['MainPID']).exists() and not Path('/sys/fs/cgroup'+own['ControlGroup']).exists(),
        'Actual original endpoint CPU exit/release proof differs')
    expected=dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',
        RuntimeMaxUSec='3min',Restart='no',NRestarts='0')
    require(all(terminal[k]==v for k,v in expected.items()),'Original endpoint CPU resource scope differs')
    raw=subprocess.check_output(['systemctl','--user','show',UNIT],text=True,timeout=5)
    values=dict(line.split('=',1)for line in raw.splitlines()if'='in line)
    scope=dict(Id=UNIT,MainPID='0',ExecMainPID=str(PID),InvocationID=INVOCATION,ExecMainCode='1',ExecMainStatus='0',
        Result='success',NRestarts='0',Restart='no',RemainAfterExit='yes',Type='exec',CPUQuotaPerSecUSec='1s',
        MemoryMax=str(256<<20),MemorySwapMax='0',TasksMax='32',RuntimeMaxUSec='4h 7min')
    require(all(values[k]==v for k,v in scope.items()),'Actual original durable observer terminal scope required')
    old=Path('/proc',str(PID),'stat');require(not old.exists() or int(old.read_text().rsplit(')',1)[1].split()[19])!=BIRTH,
        'Original durable observer birth remains')
    require(all(token in values['ExecStart']for token in ('/usr/bin/python3.12','watch_replay_progress_candidate.py',str(CASE/'window-plan.json'))),
        'Original durable observer command differs')
    return dict(result=rp,plan=dict(path=str(CASE/'window-plan.json'),sha256=PLAN_SHA),anchor=ap,first_threshold=tp,
        endpoint=endpoint,CPU_verification=cp,CPU_release=cl,report=report,observer_terminal=values)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group()
    m.add_argument('--prepare-canonical',action='store_true');m.add_argument('--close-canonical',action='store_true')
    m.add_argument('--prepare-frozen',action='store_true');m.add_argument('--close-frozen',action='store_true')
    a=p.parse_args(argv)
    if not any(vars(a).values()):print('PLAN_ONLY: no reads, outputs, model bodies, queries or launches');return
    original=original_endpoint();api=profile_api()
    canonical=CASE/'canonical-profile-CPU-original01';frozen=CASE/'frozen-profile-CPU-original01'
    if a.prepare_canonical:
        prepared=api.prepare(CASE/'result.json',canonical)
        h=api.helpers();h.put(canonical/'original-durable-observer-terminal.json',original['observer_terminal'])
        h.put(canonical/'independent-endpoint-selection.json',dict(schema='robotron-durable-endpoint-selection-v1',
            status='CAPTURE_AND_NUMERICAL_CPU_ONLY',**{k:v for k,v in original.items()if k not in ('report','observer_terminal')},
            policy=dict(checkpoint=original['endpoint'],expected_policy_clocks=original['report']['clocks'],
                training_experiment='CE4096-LR125-survival32M-original01-20261023',
                immutable_numerical_or_protection_authority=original['CPU_verification']),
            launcher_aware_observer_engineering_qualified=False,scientific_launch_qualified=False,quality_qualified=False,promotion=False))
    elif a.close_canonical:prepared=api.close(canonical)
    elif a.prepare_frozen:prepared=api.prepare(CASE/'result.json',frozen,
        canonical_closeout=canonical/'independent-original-canonical-CPU-closeout.json')
    else:prepared=api.close(frozen)
    print(json.dumps(dict(prepared=prepared,CPU_or_study_launched=False,controller_source=str(CONTROLLER),
        controller_expected_sha256=CONTROLLER_SHA)))


if __name__=='__main__':main()
