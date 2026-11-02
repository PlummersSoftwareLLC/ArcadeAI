"""Metadata-only root preparation for the fixed trial02 closure helper. PLAN default."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

RUN=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
CAMPAIGN=RUN.parent/'quality-448M-vs-rawKL-trial02-first8M-20261017'
UNIT='robotron-quality-448M-vs-rawkl-trial02-first8M-20261017.service'
PID,START,INV=638119,33529197,'325ea02d8cde47869eb8340b3de73f69'
PLAN='b502625ed8e39f01fa57af1c9f9cc8283794aa14e351e2b9bc9ec1268b267ecf'
BINDING='3b16c36da91c63fd4fb218f1fed3c1c5a5fe8caff73534d880aeaeccfe4c81fe'
R2_INDEX='3befb4d3b5887ec75782e985b87742356eb9bcd000275985ab8fbdb8d91d5abb'
PIN_KEYS={'path','sha256','bytes','identity'}

def require(value,message):
    if not value: raise RuntimeError(message)

def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,mtime_ns=info.st_mtime_ns,
        ctime_ns=info.st_ctime_ns,mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)

def read_file(path):
    path=Path(path)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        before=os.fstat(stream.fileno()); require(stat.S_ISREG(before.st_mode) and 0<before.st_size<=8<<20,'Bounded regular metadata only')
        raw=stream.read((8<<20)+1)
        require(len(raw)==before.st_size and identity(before)==identity(os.fstat(stream.fileno()))==identity(path.lstat()),'Metadata changed during read')
    return raw,dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))

def pinned(pin):
    require(isinstance(pin,dict) and set(pin)==PIN_KEYS,'Actual full PIN required; no UNBOUND/null accepted')
    raw,actual=read_file(pin['path']); require(actual==pin,'Exact metadata PIN changed: '+pin['path']); return json.loads(raw)

def fields(text): return dict(line.split('=',1) for line in text.splitlines() if '=' in line)

def publish(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:
        require(stream.write(raw)==len(raw),'Short preparation write'); stream.flush(); os.fchmod(stream.fileno(),0o444); os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return read_file(path)[1]

def prepare(known,late):
    require(known['schema']=='robotron-trial02-closure-known-metadata-v1' and [x['index'] for x in known['legs']]==[1,2,3],'Wrong preserved known input bundle')
    require(set(late)=={'schema','terminal_status','terminal_summary','parent_terminal','campaign_outcome','root_acceptance','C2','preparation_directory','closure_output_directory'}
        and late['schema']=='robotron-trial02-closure-actual-late-bindings-v1','Wrong actual late-binding fields')
    require(late['campaign_outcome'] in ('qualified_improvement','not_improved'),'Actual final outcome is still UNBOUND')
    require(set(late['C2'])=={'receipt','finished_record','audit_receipt','audit_execution','independent_review','startup_observation'},'All actual C2 bindings required')
    for name in ('terminal_status','terminal_summary','parent_terminal','root_acceptance'): pinned(late[name])
    for value in late['C2'].values(): pinned(value)
    for name in ('closure_helper','closure_manifest','closure_schema','binding_job','original_timer_show','original_parent_identity','original_parent_show','R2_full_source_review'):
        if name=='closure_helper':
            _,actual=read_file(known[name]['path']); require(actual==known[name],'Closure helper source changed')
        else: pinned(known[name])
    require(known['closure_helper']['sha256']=='6f2f6fb96b84448da085512c4bfd9cef10a08b33bce7278c34af61640d89c6dd'
        and known['closure_manifest']['sha256']=='eb890f858cff5250fd457ac0143d63cd342d47cdde1c36471d9485a0f2c9b1d1'
        and known['binding_job']['sha256']==BINDING,'Wrong fixed source/binding')
    owner=pinned(known['original_parent_identity']); old=fields(pinned(known['original_parent_show'])['stdout'])
    timer=fields(pinned(known['original_timer_show'])['stdout'])
    require((owner['pid'],owner['starttime_ticks'],owner['invocation_id'],owner['unit'])==(PID,START,INV,UNIT)
        and old['MainPID']==str(PID) and old['InvocationID']==INV and old['ControlGroup'],'Original saved owner differs')
    require(known['original_timer_show']['sha256']=='462ee8ede7dbd5c4b315dea9112fbf7753febb50d9ee6c0398431b2e5f358a07'
        and timer['Triggers']==UNIT and len(timer['InvocationID'])==32,'Original timer invocation not authentic')
    command=pinned(late['parent_terminal']); terminal=fields(command['stdout'])
    require(command['argv']==['systemctl','--user','show',UNIT,'--all'] and command['returncode']==0
        and terminal['MainPID']=='0' and terminal['ExecMainPID']==str(PID) and terminal['InvocationID']==INV
        and terminal['NRestarts']=='0' and int(terminal['ExecMainCode'])!=0
        and terminal['ControlGroup'] in ('',old['ControlGroup']),'Authentic original terminal parent is still UNBOUND/foreign')
    state=pinned(late['terminal_status']); summary=pinned(late['terminal_summary']); acceptance=pinned(late['root_acceptance'])
    require(late['terminal_status']['path']==str(CAMPAIGN/'status.json') and late['terminal_summary']['path']==str(CAMPAIGN/'summary.json')
        and state['state']=='finished' and state['plan_sha256']==summary['plan_sha256']==PLAN
        and summary['outcome']==late['campaign_outcome'],'Genuine final campaign metadata differs')
    require(str(acceptance['status']).startswith('PASS') and acceptance['plan_sha256']==PLAN and acceptance['binding_job_sha256']==BINDING
        and acceptance['accepted_leg_indices']==[1,2,3,4] and acceptance['campaign_outcome']==summary['outcome'],'External root all-four acceptance required')
    legs=[]; receipt_shas=[]; audit_shas=[]; exit_codes=[]; review_shas=[]; dispositions=[]
    for entry in [*known['legs'],dict(index=4,**late['C2'])]:
        n=entry['index']; record=pinned(entry['finished_record']); receipt=pinned(entry['receipt'])
        audit=pinned(entry['audit_receipt']); execution=pinned(entry['audit_execution']); review=pinned(entry['independent_review'])
        observed=pinned(entry['startup_observation']); label=('R1','C1','R2','C2')[n-1]
        evaluator=observed['evaluator'] if n==1 else observed[label+'_evaluator']
        actors=[{k:a[k] for k in ('slot','pid','starttime_ticks')} for a in observed[label+'_actors']]
        require(len(actors)==16 and {x['slot'] for x in actors}==set(range(4096,4112)),'Actual sixteen original actors required')
        require(next(x for x in state['legs'] if x['index']==n)==record and record['state']=='finished' and record['returncode']==0
            and record['pid']==evaluator['pid'] and record['receipt_path']==entry['receipt']['path'],'Finished record snapshot not from actual terminal status')
        require(receipt['valid'] is True and receipt['complete'] is True and receipt['active'] is False
            and receipt['pending']==receipt['abandoned']==0 and audit['leg']==n,'Full-tail original receipt/audit not ready')
        require(str(review['status']).startswith('PASS') and review['leg']==n and review['actual_plan_sha256']==PLAN
            and review['original_evaluator']['pid']==record['pid'],'Actual independent review differs')
        require(tuple(review['original_audit'][k] for k in ('pid','starttime_ticks','invocation_id','exec_code','exit_status','result'))==tuple(
            execution[k] for k in ('original_pid','original_starttime_ticks','original_invocation','original_exec_code','original_exit','original_result'))
            and all(any((x['path'],x['sha256'],x['bytes'])==(entry[k]['path'],entry[k]['sha256'],entry[k]['bytes'])
                for x in review['key_artifacts']) for k in ('audit_receipt','audit_execution')),'Review does not bind this original audit')
        if n==3:
            require(entry['independent_review']['sha256']==R2_INDEX and review['full_source_review']=={
                k:known['R2_full_source_review'][k] for k in ('path','sha256','bytes')},'R2 requires compatible index3bef; full a883 stays separate')
        require(execution['audit_receipt']['sha256']==entry['audit_receipt']['sha256'] and execution['original_exec_code']==1
            and execution['source_pins_held'] is True and execution['original_archived_before_release'] is True,'Original audit execution differs')
        disposition='original_audit_valid' if audit.get('valid') is True else 'root_accepted_narrow_manual_review'
        require((disposition=='original_audit_valid' and execution['original_exit']==0 and execution['original_result']=='success'
            and audit['plan_sha256']==PLAN and audit['receipt_sha256']==entry['receipt']['sha256']) or
            (disposition=='root_accepted_narrow_manual_review' and audit.get('valid') is False
                and execution['original_exit']==2 and execution['original_result']=='exit-code'),'Original audit failure is not root-accepted parser review')
        legs.append(dict(entry,evaluator={k:evaluator[k] for k in ('pid','starttime_ticks')},actors=actors))
        receipt_shas.append(entry['receipt']['sha256']); audit_shas.append(entry['audit_receipt']['sha256'])
        exit_codes.append(execution['original_exit']); review_shas.append(entry['independent_review']['sha256']); dispositions.append(disposition)
    require((acceptance['leg_receipt_sha256'],acceptance['audit_receipt_sha256'],acceptance['audit_original_exit'],
        acceptance['independent_review_sha256'],acceptance['audit_disposition'])==(receipt_shas,audit_shas,exit_codes,review_shas,dispositions),'Root acceptance arrays differ')
    output=Path(late['closure_output_directory']); prep=Path(late['preparation_directory'])
    require(output.parent==prep.parent==RUN and output.name.startswith('rawKL-trial02-quality-terminal-closure-')
        and prep.name.startswith('rawKL-trial02-quality-closure-root-job-') and output!=prep
        and not output.exists() and not prep.exists() and not output.is_symlink() and not prep.is_symlink(),'New direct-run26 paths required')
    return dict(schema='robotron-trial02-quality-owned-closure-job-v1',binding_job=known['binding_job'],timer_invocation_id=timer['InvocationID'],
        terminal_status=late['terminal_status'],terminal_summary=late['terminal_summary'],root_acceptance=late['root_acceptance'],legs=legs,output_directory=str(output)),prep

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute',action='store_true')
    for name in ('known-inputs','known-inputs-sha256','late-bindings','late-bindings-sha256','source-sha256'): parser.add_argument('--'+name)
    args=parser.parse_args(argv)
    if not args.execute: print('PLAN_ONLY: C2/final outcome/root acceptance/parent terminal remain UNBOUND; no reads or writes'); return 0
    source,source_pin=read_file(__file__); require(source_pin['sha256']==args.source_sha256,'Explicit exact source SHA required')
    loaded=[]; input_pins=[]
    for path,expected in [(args.known_inputs,args.known_inputs_sha256),(args.late_bindings,args.late_bindings_sha256)]:
        require(path and expected,'Explicit actual input and SHA required'); raw,pin=read_file(path)
        require(pin['sha256']==expected and pin['identity']['mode']=='0o444' and pin['identity']['nlink']==1,'Readonly exact input required')
        loaded.append(json.loads(raw)); input_pins.append(pin)
    job,prep=prepare(*loaded)  # All metadata validation precedes any output creation.
    prep.mkdir(); job_pin=publish(prep/'root-job.json',job)
    publish(prep/'assembly-receipt.json',dict(status='PREPARED_METADATA_ONLY',source=source_pin,inputs=input_pins,root_job=job_pin,
        parent_terminal=loaded[1]['parent_terminal'],no_acceptance_generated=True,no_runtime_actions=True,qualification_pass=False))
    print(json.dumps(dict(status='PREPARED_METADATA_ONLY',root_job=job_pin)))
    return 0

if __name__=='__main__': raise SystemExit(main())
