#!/usr/bin/env python3
"""Inspect or atomically adjust the explicitly managed Robotron experiment."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'logs'/'managed-learning-20261015'
CONTROL = ROOT/'models_dqn'/'learning_control.json'


def snapshot():
    with urllib.request.urlopen('http://localhost:8771/api/now', timeout=10) as response:
        return json.load(response)


def atomic_json(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2))
    os.replace(tmp,path)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action', choices=['status','ramp','hold','lr','checkpoint','measure','resume'])
    parser.add_argument('--label')
    parser.add_argument('--end',type=float)
    parser.add_argument('--scale',type=float)
    parser.add_argument('--checkpoint')
    parser.add_argument('--cohort',type=float,default=120)
    parser.add_argument('--timeout',type=float,default=600)
    parser.add_argument('--duration',type=int,default=2000000)
    args=parser.parse_args()
    now=snapshot()
    if args.action == 'status':
        keys=['ts','frame_count','learner_frame_count','optimized_samples','managed_experiment',
              'eval_games','eval_life_score','fps','loss','grad_norm','lr','epsilon','expert_ratio',
              'client_count','c51_diagnostics','measurement_active','managed_measurement']
        print(json.dumps({k:now.get(k) for k in keys},indent=2))
    else:
        if not args.label and args.action != 'resume':
            parser.error('--label is required')
        previous=json.loads(CONTROL.read_text()) if CONTROL.exists() else {}
        if args.action == 'checkpoint':
            atomic_json(ROOT/'models_dqn'/'managed_save.request.json',dict(tag=args.label))
            current=previous
        elif args.action == 'measure':
            if not 30 <= args.cohort <= 3600 or not args.cohort+30 <= args.timeout <= 7200:
                parser.error('invalid cohort or timeout')
            current={**previous, 'measurement':dict(label=args.label,
                checkpoint=str(Path(args.checkpoint).resolve()) if args.checkpoint else None,
                cohort_s=args.cohort,timeout_s=args.timeout)}
            atomic_json(CONTROL,current)
        elif args.action == 'resume':
            current=dict(previous)
            current.pop('measurement',None)
            atomic_json(CONTROL,current)
        else:
            current={**previous,'experiment':args.label,
                     'reason':f'Managed {args.action} after whole-game baseline measurement.'}
            current.pop('measurement',None)
            if args.action == 'ramp':
                if args.end is None or not .02 <= args.end <=1 or args.duration<=0:
                    parser.error('ramp requires --end within .02..1 and positive duration')
                current['epsilon_ramp']=dict(anchor=now['learner_frame_count'],
                                             start=now['epsilon'],end=args.end,duration=args.duration)
            elif args.action == 'lr':
                if args.scale is None or not .01 <= args.scale <= 2:
                    parser.error('lr requires --scale within .01..2')
                current['lr_scale']=args.scale
            atomic_json(CONTROL,current)
        event=dict(utc=datetime.now(timezone.utc).isoformat(),action=args.action,
                   snapshot=now,previous=previous,current=current,label=args.label)
        with (WORK/'decisions.jsonl').open('a') as stream:
            stream.write(json.dumps(event)+'\n')
        print(json.dumps({'action':args.action,'current':current,'label':args.label},indent=2))
