"""Three small metadata checks; no model body, Torch, service, request or source install."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('launchdata',HERE/'prepare_same_state_continuation_v1.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)


def main():
    template=h.read(h.small_pin(h.C/'stop-preparation-original01/current-LR125-phase-CPU-template.json'))
    assert template['verifier_sha256']==h.VERIFIER_SHA
    report_path=h.G/'logs/managed-learning-20261015/run-26/deadline-score32-later-policy-firstSave-original01-preparation-20261026/candidate-CPU-verification-original02/cpu-verification.json'
    report=json.loads(report_path.read_text())
    assert report['status']=='PASS' and report['script']['sha256']==h.VERIFIER_SHA
    # Historical real metadata is a fixture, never represented as future stopped state.
    saved=dict(checkpoint=dict(path=str(h.G/'models_dqn/robotron_dqn_latest.pt'),
        sha256=report['sha256'],bytes=report['bytes']),clocks={k:report['clocks'][k]for k in h.CLOCKS})
    record=h.resume_record(saved,report)
    phase=report['saved_priority_metric_phase']
    assert set(record)=={'schema','phase_id','metric','action','previous_metric','checkpoint','model_dir','root_precommit_sha256'}
    assert record['action']=='resume' and record['root_precommit_sha256']==phase['root_precommit_sha256']
    assert record['phase_id']==phase['phase_id'] and record['checkpoint']==saved['checkpoint']
    bad=copy.deepcopy(saved);bad['clocks']['optimized_samples']+=1
    try:h.resume_record(bad,report)
    except ValueError:pass
    else:raise AssertionError('Mismatched stopped clock accepted')
    floor=saved['clocks'];assert h.startup_delta(floor,floor)['startup_updates']==0
    one=dict(floor,training_steps=floor['training_steps']+1,optimized_samples=floor['optimized_samples']+4096)
    assert h.startup_delta(one,floor)['startup_updates']==1
    for bad in (dict(one,training_steps=floor['training_steps']+2),
                dict(one,learner_frame_count=floor['learner_frame_count']+1),
                dict(one,frame_count=floor['frame_count']+1)):
        try:h.startup_delta(bad,floor)
        except ValueError:pass
        else:raise AssertionError('Excess startup work/input accepted')
    inert=subprocess.run([sys.executable,'-I','-B',str(HERE/'prepare_same_state_continuation_v1.py')],
        capture_output=True,text=True,check=True)
    assert inert.stdout.startswith('INERT:') and not inert.stderr
    print(json.dumps(dict(status='PASS',checks=3,scope='resume phase/founder+clock mismatch; '
        'startup zero/one/excess/input clocks; default inert entry',python=sys.version,
        actual_stop_or_launch_qualified=False,model_body_reads=0,Torch_imported='torch'in sys.modules)))


if __name__=='__main__':main()
