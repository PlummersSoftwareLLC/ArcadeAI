#!/usr/bin/env python3
"""Read-only bounded progress; never imports experimental/helper/model modules."""
import collections
import json
from pathlib import Path
import subprocess
import urllib.request

BASE=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
UNIT='robotron-live8-maintenance-reviewed4-20261017.service'
OUTPUT=BASE/'live8-owned-maintenance-reviewed4-20261017'
def main():
    show=subprocess.run(['systemctl','--user','show',UNIT,'-p','MainPID','-p','ExecMainPID','-p','ExecMainCode',
                         '-p','ExecMainStatus','-p','ActiveState','-p','SubState','-p','Result','-p','InvocationID'],
                         capture_output=True,text=True,timeout=5)
    result=dict(unit=dict(line.split('=',1) for line in show.stdout.splitlines() if '=' in line))
    if OUTPUT.exists():
        result['events']=[]
        for path in sorted(OUTPUT.glob('event-*.json')):
            try:
                item=json.loads(path.read_text());result['events'].append(dict(file=path.name,phase=item['phase']))
            except (OSError,ValueError):pass
        for name in ('result.json','controller-error.json'):
            path=OUTPUT/name
            if path.exists():
                item=json.loads(path.read_text());result[name]={key:item.get(key) for key in ('status','error','manual_recovery_required','capture_complete','recovery_errors')}
        capture=OUTPUT/'ce-recomputed-capture-original8'
        if capture.exists():
            result['capture']={key:len(list(capture.glob(pattern))) for key,pattern in [('entered','attempt-*.entered.json'),('rows','attempt-??.json'),('payloads','attempt-*.payload.pt')]}
            result['capture']['bytes']=sum(p.stat().st_size for p in capture.iterdir() if p.is_file())
        job=json.loads((OUTPUT/'root-job.json').read_text());states=collections.Counter()
        for actor in job['before']['bindings']['actors']:
            try:
                fields=(Path('/proc')/str(actor['pid'])/'stat').read_text().rsplit(')',1)[1].split()
                states[fields[0] if int(fields[19])==actor['starttime_ticks'] else 'REUSED']+=1
            except OSError:states['ABSENT']+=1
        result['original_actor_states']=dict(states)
    try:
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as response:item=json.load(response)
        result['api']={key:item.get(key) for key in ('learner_frame_count','training_steps','optimized_samples','frame_count','client_count','training_enabled','loss')}
        result['api']['process_id']=item.get('host_pipeline',{}).get('learning_exposure',{}).get('optimizer',{}).get('process_id')
    except (OSError,ValueError) as error:result['api_error']=str(error)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
