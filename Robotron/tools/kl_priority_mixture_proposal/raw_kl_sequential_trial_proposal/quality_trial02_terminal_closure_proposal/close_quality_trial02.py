"""Root-only trial02 quality terminal archive and exact owned release. PLAN default."""
import argparse
import importlib.util
import json
from pathlib import Path

RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
UNIT = 'robotron-quality-448M-vs-rawkl-trial02-first8M-20261017.service'
TIMER = UNIT.removesuffix('.service')+'.timer'
PID, START, INV = 638119, 33529197, '325ea02d8cde47869eb8340b3de73f69'
PLAN_SHA = 'b502625ed8e39f01fa57af1c9f9cc8283794aa14e351e2b9bc9ec1268b267ecf'
BINDING_SHA = '3b16c36da91c63fd4fb218f1fed3c1c5a5fe8caff73534d880aeaeccfe4c81fe'
HEALTH = RUN/'rawKL-trial02-terminal-release-root-preparation-20261017/archive_and_release_trial02.py'
HEALTH_SHA = 'd525f6a0910354023dec54bc6f54b45651912942cdc5a5eb51dc2de814361f65'
LAUNCH = RUN/'rawKL-trial02-quality-durable-launch-20261017'
LAUNCH_PINS = {'original-controller-identity.json':'b75df2f61bc294ddbe5a40c76dbcad7286f27df7855ba038c84f098667f2d204',
    'original-controller-running-show.json':'42c62d4309bfb37ef0dcfd15d0ed776934cab267f1c65628a8770a44a72c770a',
    'original-timer-show-after-carrier-reaped.json':'462ee8ede7dbd5c4b315dea9112fbf7753febb50d9ee6c0398431b2e5f358a07'}

def require(value, message):
    if not value: raise RuntimeError(message)

def load_ops():
    import hashlib
    require(hashlib.sha256(HEALTH.read_bytes()).hexdigest()==HEALTH_SHA,'Unchanged health utility SHA differs')
    spec=importlib.util.spec_from_file_location('_quality_trial02_unchanged_health',HEALTH)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def read_job(path, expected, ops):
    data,pin=ops.read_file(path)
    require(pin['sha256']==expected and pin['identity']['mode']=='0o444' and pin['identity']['nlink']==1,'Exact readonly root job required')
    job=json.loads(data)
    require(set(job)=={'schema','binding_job','timer_invocation_id','terminal_status','terminal_summary','root_acceptance','legs','output_directory'}
        and job['schema']=='robotron-trial02-quality-owned-closure-job-v1','Wrong explicit closure job fields')
    for name in ('binding_job','terminal_status','terminal_summary','root_acceptance'):
        require(isinstance(job[name],dict) and {'path','sha256','bytes','identity'}<=set(job[name]),'Unbound final PIN: '+name)
    require(job['binding_job']['sha256']==BINDING_SHA and isinstance(job['timer_invocation_id'],str)
        and len(job['timer_invocation_id'])==32,'Actual binding/timer identity required')
    require(isinstance(job['legs'],list) and [x.get('index') for x in job['legs']]==[1,2,3,4],'Four actual ordered leg bindings required')
    for leg in job['legs']:
        require(set(leg)=={'index','receipt','finished_record','audit_receipt','audit_execution','independent_review','startup_observation','evaluator','actors'},'Leg proof fields differ')
        for name in ('receipt','finished_record','audit_receipt','audit_execution','independent_review','startup_observation'):
            require(isinstance(leg[name],dict) and {'path','sha256','bytes','identity'}<=set(leg[name]),'Unknown future leg proof')
        require(isinstance(leg['evaluator'],dict) and type(leg['evaluator'].get('pid')) is int and leg['evaluator']['pid']>0
            and type(leg['evaluator'].get('starttime_ticks')) is int and leg['evaluator']['starttime_ticks']>0,'Actual original evaluator PID/start required')
        require(len(leg['actors'])==16 and {x.get('slot') for x in leg['actors']}==set(range(4096,4112))
            and all(type(x.get('pid')) is int and x['pid']>0 and type(x.get('starttime_ticks')) is int and x['starttime_ticks']>0 for x in leg['actors']),
            'Actual original sixteen actor identities required')
    out=Path(job['output_directory'])
    require(out.is_absolute() and out.parent==RUN and out.name.startswith('rawKL-trial02-quality-terminal-closure-')
        and not out.exists() and not out.is_symlink(),'New direct-run26 closure output required')
    return job,pin,out

def original_owner(ops, job):
    saved={}
    for name,digest in LAUNCH_PINS.items():
        data,pin=ops.read_file(LAUNCH/name); require(pin['sha256']==digest,'Original launch evidence changed'); saved[name]=json.loads(data)
    identity=saved['original-controller-identity.json']; running=ops.fields(saved['original-controller-running-show.json']['stdout'])
    require((identity['pid'],identity['starttime_ticks'],identity['invocation_id'],identity['unit'])==(PID,START,INV,UNIT),'Wrong original owner')
    require(running['MainPID']==str(PID) and running['InvocationID']==INV and running['ControlGroup'],'Authentic original cgroup missing')
    timer=ops.fields(saved['original-timer-show-after-carrier-reaped.json']['stdout'])
    require(timer['InvocationID']==job['timer_invocation_id'] and timer['Triggers']==UNIT,'Original timer lineage differs')
    return dict(pid=PID,starttime_ticks=START,invocation_id=INV,unit=UNIT,cgroup=running['ControlGroup'])

def terminal(ops, owner):
    value,raw=ops.show(UNIT); ops.original_terminal(owner,value); return value,raw

def archive_originals(ops, job, owner, out, record):
    service,service_raw=terminal(ops,owner); timer,timer_raw=ops.show(TIMER)
    require(timer.get('LoadState')=='not-found' or timer.get('InvocationID')==job['timer_invocation_id'],'Original timer replaced')
    archives={}
    for label,unit,value,shown,inv in [('service',UNIT,service,service_raw,INV),('timer',TIMER,timer,timer_raw,job['timer_invocation_id'])]:
        archives[label]={}
        for kind,raw in [('show',shown),('cat',ops.command(['systemctl','--user','cat',unit])),
            ('journal',ops.command(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+inv,'--no-pager','-o','short-iso-precise']))]:
            rawpin=record(label+'-'+kind,raw)
            plain=ops.write_bytes(out/(label+'-'+kind+'.txt'),raw['stdout'].encode('utf-8','surrogateescape'),allow_empty=kind=='journal' or value.get('LoadState')=='not-found')
            archives[label][kind]=dict(command=rawpin,plain=plain)
            require(raw['returncode']==0 or kind in ('show','cat') and label=='timer' and value.get('LoadState')=='not-found','Original full archive command failed')
    proof=dict(owner=owner,timer_invocation_id=job['timer_invocation_id'],exec_code=int(service['ExecMainCode']),
        exit_status=int(service['ExecMainStatus']),result=service['Result'],full_original_archives=archives,archived_before_release=True)
    proof['archive_PIN']=ops.publish(out/'original-execution-before-any-release.json',proof); return proof

def final_proofs(ops, job, cfg, record):
    state=ops.pinned(job['terminal_status']); summary=ops.pinned(job['terminal_summary']); acceptance=ops.pinned(job['root_acceptance'])
    require(job['terminal_status']['path']==str(Path(cfg['campaign']['output_directory'])/'status.json')
        and job['terminal_summary']['path']==str(Path(cfg['campaign']['output_directory'])/'summary.json'),'Final original campaign paths differ')
    require(state['state']=='finished' and state['plan_sha256']==summary['plan_sha256']==PLAN_SHA
        and summary['outcome'] in ('qualified_improvement','not_improved'),'Actual valid terminal outcome required')
    require(str(acceptance['status']).startswith('PASS') and acceptance['plan_sha256']==PLAN_SHA
        and acceptance['binding_job_sha256']==BINDING_SHA and acceptance['accepted_leg_indices']==[1,2,3,4]
        and acceptance['campaign_outcome']==summary['outcome'],'Explicit root all-four acceptance required')
    private=[]; receipts=[]; audits=[]; exits=[]; reviews=[]; dispositions=[]; audit_processes=[]
    for leg in job['legs']:
        n=leg['index']; role=('reference' if n in (1,3) else 'candidate'); original=ops.pinned(leg['finished_record'])
        receipt=ops.pinned(leg['receipt']); audit=ops.pinned(leg['audit_receipt']); execution=ops.pinned(leg['audit_execution']); review=ops.pinned(leg['independent_review'])
        observed=ops.pinned(leg['startup_observation']); label=('R1','C1','R2','C2')[n-1]
        parent=observed['quality_owner'] if n==1 else observed['owners'][UNIT]
        unit=observed['quality_unit'] if n==1 else observed['unit_show_all'][UNIT]
        evaluator=observed['evaluator'] if n==1 else observed[label+'_evaluator']
        require((parent['pid'],parent['starttime_ticks'],unit['InvocationID'])==(PID,START,INV)
            and {k:evaluator[k] for k in ('pid','starttime_ticks')}==leg['evaluator']
            and {(x['slot'],x['pid'],x['starttime_ticks']) for x in observed[label+'_actors']}=={
                (x['slot'],x['pid'],x['starttime_ticks']) for x in leg['actors']},'Private original starttimes not joined to authentic saved observations')
        require(next(x for x in state['legs'] if x['index']==n)==original and original['state']=='finished' and original['returncode']==0
            and original['pid']==leg['evaluator']['pid'] and original['role']==role,'Original selected evaluator record differs')
        require(leg['receipt']['path']==original['receipt_path'] and receipt['complete'] is True and receipt['active'] is False
            and receipt['valid'] is True and receipt['pending']==receipt['abandoned']==0,'Original full-tail receipt not valid/complete')
        result=next(x for x in summary['legs'] if x['index']==n)
        require(result['returncode']==0 and result['valid'] is True and result['receipt_sha256']==leg['receipt']['sha256'],'Summary/original receipt differs')
        require(audit['leg']==n and execution['audit_receipt']['sha256']==leg['audit_receipt']['sha256'] and execution['source_pins_held'] is True
            and execution['original_archived_before_release'] is True and execution['original_exec_code']==1,'Actual original audit evidence differs')
        require(str(review['status']).startswith('PASS') and review['leg']==n and review['actual_plan_sha256']==PLAN_SHA,'Pinned independent saved review differs')
        reviewed=review['original_audit']
        require(tuple(reviewed[k] for k in ('pid','starttime_ticks','invocation_id','exec_code','exit_status','result'))==tuple(
            execution[k] for k in ('original_pid','original_starttime_ticks','original_invocation','original_exec_code','original_exit','original_result'))
            and review['original_evaluator']['pid']==original['pid'] and all(any(
                (x['path'],x['sha256'],x['bytes'])==(leg[k]['path'],leg[k]['sha256'],leg[k]['bytes']) for x in review['key_artifacts'])
                for k in ('audit_receipt','audit_execution')),'Independent saved review does not bind this original execution/report')
        if audit.get('valid') is True:
            require(execution['original_exit']==0 and execution['original_result']=='success' and audit['plan_sha256']==PLAN_SHA
                and audit['receipt_sha256']==leg['receipt']['sha256'],'Valid original audit binding differs')
            dispositions.append('original_audit_valid')
        else:
            require(execution['original_exit']==2 and execution['original_result']=='exit-code' and audit.get('valid') is False,'Failed original audit requires root forward review')
            dispositions.append('root_accepted_narrow_manual_review')  # Explicit root acceptance below; no log exemption here.
        require(execution['owned_release'] and {x['unit'] for x in execution['owned_release']}=={
            f'robotron-rawkl-trial02-quality-leg{n:02d}-audit-reviewed1-20261017.'+suffix for suffix in ('service','timer')},'Foreign/missing audit release unit')
        require(all(x.get('final_load_state')=='not-found' for x in execution['owned_release']),'Original audit units not released')
        for release in execution['owned_release']:
            require(ops.show(release['unit'])[0]['LoadState']=='not-found','Audit CPU unit reappeared')
        observed_start=ops.process_start(execution['original_pid'])
        require(observed_start!=execution['original_starttime_ticks'],'Original audit CPU process remains')
        audit_processes.append(dict(pid=execution['original_pid'],expected_start=execution['original_starttime_ticks'],observed_start=observed_start))
        require({(x['slot'],x['pid']) for x in leg['actors']}=={(int(k),v['pid']) for k,v in receipt['socket_wait']['actors'].items()},'Original private actor PID joins differ')
        private.extend([leg['evaluator'],*leg['actors']]); receipts.append(leg['receipt']['sha256']); audits.append(leg['audit_receipt']['sha256'])
        exits.append(execution['original_exit']); reviews.append(leg['independent_review']['sha256']);
    require(acceptance['leg_receipt_sha256']==receipts and acceptance['audit_original_exit']==exits
        and acceptance['audit_receipt_sha256']==audits and acceptance['audit_disposition']==dispositions
        and acceptance['independent_review_sha256']==reviews,'Root acceptance does not bind actual four proofs/dispositions')
    require(len({(x['pid'],x['starttime_ticks']) for x in private})==68,'Duplicate private original identities')
    return dict(outcome=summary['outcome'],audit_original_exit=exits,private=private,
        audit_process_observations=audit_processes,external_root_acceptance=job['root_acceptance'])

def absent(ops, owner, private):
    observations=[]
    for item in [dict(pid=PID,starttime_ticks=START),*private]:
        observed=ops.process_start(item['pid']); observations.append(dict(pid=item['pid'],expected_start=item['starttime_ticks'],observed_start=observed))
        require(observed!=item['starttime_ticks'],'Original quality parent/private evaluator/actor remains')
    ops.cgroup_empty(owner['cgroup'])
    return dict(processes=observations,cgroup=owner['cgroup'],cgroup_empty_or_absent=True)

def release_one(ops, job, owner, unit, record, releases):
    require(unit in (TIMER,UNIT),'Foreign unit release refused'); terminal(ops,owner)
    before,_=ops.show(unit)
    if before['LoadState']=='not-found': releases.append(dict(unit=unit,already_absent=True,released=True,final_load_state='not-found')); return
    require(unit!=TIMER or before['InvocationID']==job['timer_invocation_id'],'Timer replaced before release')
    stopped=ops.command(['systemctl','--user','stop',unit]); record('stop-'+unit,stopped); after,_=ops.show(unit)
    entry=dict(unit=unit,actual_stop_returncode=stopped['returncode'],released=False); releases.append(entry)
    known=[f'Unit {unit} not loaded.',f'Failed to stop {unit}: Unit {unit} not loaded.']
    require(stopped['returncode']==0 or stopped['returncode']==5 and after['LoadState']=='not-found'
        and stopped['stderr'].strip() in known,'Unexpected exact-unit stop error')
    if after['LoadState']!='not-found' and after.get('ActiveState')=='failed':
        reset=ops.command(['systemctl','--user','reset-failed',unit]); record('reset-'+unit,reset); require(reset['returncode']==0,'Exact reset failed')
    final,raw=ops.show(unit); record('released-'+unit,raw); require(final['LoadState']=='not-found','Exact unit still loaded'); entry.update(released=True,final_load_state='not-found')

def close(job, job_pin, out, ops):
    owner=original_owner(ops,job); terminal(ops,owner)  # No files or mutations while original parent is nonterminal/replaced.
    out.mkdir(); counter=0
    def record(name,raw):
        nonlocal counter
        p=ops.publish(out/f'{counter:03d}-{name}-command.json',raw); counter+=1; return p
    proof=archive_originals(ops,job,owner,out,record); releases=[]; result=dict(status='ARCHIVED_NEEDS_ROOT_REVIEW',owned_cleanup_complete=False,
        original_execution=proof,root_job=job_pin,qualification_pass=False,source_freeze_released=False,publication=False,owned_release=releases)
    try:
        require(proof['exec_code']==1 and proof['exit_status']==0 and proof['result']=='success','Original parent failed; retained archive requires root review')
        cfg=ops.pinned(job['binding_job']); bindings=ops.pinned(cfg['evidence']['outer_job']); activation_job=ops.pinned(cfg['evidence']['activation_job'])
        activation=ops.pinned(cfg['evidence']['activation']); ce=ops.pinned(cfg['evidence']['ce_return'])
        require((ce['owner']['pid'],ce['owner']['starttime_ticks'],ce['owner']['invocation_id'])==(620749,33475842,'3e0b59be7ec5484d9cc8d33265e74d77'),'Current CE owner binding differs')
        evidence=final_proofs(ops,job,cfg,record)
        result['bound_final_proofs']=ops.publish(out/'bound-final-proofs.json',evidence)
        result['pre_release_absence']=ops.publish(out/'pre-release-owned-process-and-cgroup-absence.json',absent(ops,owner,evidence['private']))
        before,raw=ops.current_ce_and_resources(bindings,activation_job,activation,ce,record)
        result['pre_release_health']=dict(proof=ops.publish(out/'pre-release-main192-and-resources.json',before),
            raw_API=ops.write_bytes(out/'pre-release-main-API.json',raw))
        for unit in (TIMER,UNIT): absent(ops,owner,evidence['private']); release_one(ops,job,owner,unit,record,releases)
        require(all(ops.show(unit)[0]['LoadState']=='not-found' for unit in (TIMER,UNIT)),'Owned quality units not released')
        result['post_release_absence']=ops.publish(out/'post-release-owned-process-and-cgroup-absence.json',absent(ops,owner,evidence['private']))
        after,raw=ops.current_ce_and_resources(bindings,activation_job,activation,ce,record)
        result['post_release_health']=dict(proof=ops.publish(out/'post-release-main192-and-resources.json',after),
            raw_API=ops.write_bytes(out/'post-release-main-API.json',raw))
        result.update(status='PASS_ORIGINAL_QUALITY_ARCHIVED_OWNED_CLEANUP_COMPLETE',owned_cleanup_complete=True,
            accepted_quality_outcome=evidence['outcome'],all68_owned_private_processes_absent=True,main192_and_resources_healthy=True,root_acceptance=evidence['external_root_acceptance'])
    except Exception as error: result['error']=f'{type(error).__name__}: {error}'
    ops.publish(out/'cleanup-receipt.json',result); return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute',action='store_true'); parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256'); parser.add_argument('--expected-source-sha256'); args=parser.parse_args(argv)
    if not args.execute: print('PLAN_ONLY: no inputs/imports/runtime/actions; actual final root job required'); return 0
    ops=load_ops(); _,source=ops.read_file(__file__); require(source['sha256']==args.expected_source_sha256,'Exact source SHA required')
    require(args.job is not None and args.expected_job_sha256,'Explicit actual final root job required')
    job,pin,out=read_job(args.job,args.expected_job_sha256,ops); result=close(job,pin,out,ops)
    print(json.dumps(dict(status=result['status'],owned_cleanup_complete=result['owned_cleanup_complete'],output=str(out))))
    return 0 if result['owned_cleanup_complete'] else 2

if __name__=='__main__': raise SystemExit(main())
