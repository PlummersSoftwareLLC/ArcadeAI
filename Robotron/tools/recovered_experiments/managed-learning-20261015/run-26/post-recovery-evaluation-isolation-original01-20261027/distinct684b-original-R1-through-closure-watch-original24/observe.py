"""Passive observation of the same original R1 through its owned closure."""
import importlib.util
import json
import os
from pathlib import Path
import time

OUT=Path(__file__).resolve().parent
STUDY=OUT.parent/'distinct684b-buffered-family8-study-original01'
NATIVE=STUDY/'R1/deadline-output-original01'
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def read(path):return json.loads(path.read_bytes())


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def main():
    spec=importlib.util.spec_from_file_location('_passive_until_closure_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    owner=read(OUT.parent/'distinct684b-family8-original-launch-original01/actual-original-R1-live-owner.json')
    assert birth(owner['owner']['pid'])==owner['owner']['starttime_ticks']
    original=h.put(OUT/'original-watcher-owner.json',dict(pid=os.getpid(),birth=birth(os.getpid()),source=h.pin(Path(__file__).resolve()),
        original_native=owner['owner'],observed_live=True,original_scope_controls_used=False))
    anchor=read(NATIVE/'original-deadline-anchor.json')['anchor'];observer_job=read(NATIVE/'main-health-scope/job.json')
    deadline=anchor['deadline_monotonic_ns']/1e9+500
    observed=0;status='OBSERVATION_BOUND_REQUIRES_REPOLL'
    path=OUT/'observations.jsonl'
    with path.open('x')as stream:
        while time.monotonic()<deadline:
            closed=read(STUDY/'R1/controller-original-result.json')if(STUDY/'R1/controller-original-result.json').exists()else None
            row=dict(index=observed,unix_s=time.time(),monotonic_s=time.monotonic(),native_birth=birth(owner['owner']['pid']),
                wrapper_birth=birth(owner['wrapper_pid']),controller_birth=birth(owner['controller']['pid']),
                cutoff_remaining_s=(anchor['deadline_monotonic_ns']-time.monotonic_ns())/1e9)
            try:
                native=read(NATIVE/'status.json');row.update(phase=native['phase'],native_errors=native['errors'],
                    original_actors_alive=sum(birth(value['pid'])==value['birth']for value in native['slots'].values()),
                    minimum_wire_sequence=min(value['sequence']for value in native['slots'].values()))
                live=read(Path(observer_job['live_control_path'])/'live.json')
                row.update(health_samples=live['observed_samples'],health_age_s=time.monotonic()-live['updated_monotonic_s'])
            except (OSError,ValueError,KeyError)as error:row['observation_requires_repoll']=repr(error)
            if closed and birth(owner['wrapper_pid'])!=owner['wrapper_birth']:
                status='ORIGINAL_CONTROLLER_CLOSED_REVIEW_REQUIRED';row['actual_original_controller_result']=h.pin(STUDY/'R1/controller-original-result.json')
            stream.write(json.dumps(row,separators=(',',':'))+'\n');stream.flush();observed+=1
            print(json.dumps(row),flush=True)
            if status=='ORIGINAL_CONTROLLER_CLOSED_REVIEW_REQUIRED':break
            time.sleep(min(45,max(0,deadline-time.monotonic())))
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    result=h.put(OUT/'original-through-closure-observation.json',dict(status=status,original_watcher=original,observations=h.pin(path),
        count=observed,original_scope_controls_used=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(result=result,status=status)),flush=True)
    return 0 if status=='ORIGINAL_CONTROLLER_CLOSED_REVIEW_REQUIRED'else 2


if __name__=='__main__':raise SystemExit(main())
