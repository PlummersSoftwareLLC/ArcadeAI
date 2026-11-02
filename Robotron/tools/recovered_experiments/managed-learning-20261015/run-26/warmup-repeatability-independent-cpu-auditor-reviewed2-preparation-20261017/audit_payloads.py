"""Independent CPU-only audit of one fixed archived warmup diagnostic.

SOURCE ONLY / UNEXECUTED. Default is a literal PLAN with no input/framework read.
No captured checkpoint, model state, replay or sampler file is loaded.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys

PLAN = "PLAN ONLY: no inputs read or frameworks imported. A separately authorized --execute --job warmup-repeatability-reviewed1-20261017 --source-sha256 SHA --pins-sha256 SHA --output NEW_ABSOLUTE_DIR audits only12 archived warmup payloads+2 masks on CPU; no GPU, checkpoint/replay load, ON/full-step or learning claim."
JOB = 'warmup-repeatability-reviewed1-20261017'
ROLES = ('base_a', 'base_repeat', 'off')
CASES = tuple(dict(index=i+1,diagnostics=d,empty=e) for i,(d,e) in enumerate(
    ((False,False),(False,True),(True,False),(True,True))))
TOLS = dict(ce=dict(rtol=.0002,atol=.00002),gradient=dict(rtol=.002,atol=.000002),
            scalars=dict(rtol=.002,atol=.000002))
ZERO_CALLS = dict(optimizer_step=0,scaler_step=0,scaler_update=0)
PRIOR_SHA = 'f0c8789f7976097a2c257ada4b23d3af644ebf0c48f7d7393c02e92d264f823d'
ARCHIVE_SHA = 'b6383ddf1a31db763a42f287355a41ea646d6d656d8f29306ca18d4f6895e4c1'
LOCK_SHA = '20057c290b1a9f121a03dfb5e81d33c67170a2d51807c0c149e295f393fa359e'
WORKER_SHA = '59b3e81dead476bae25637b848b8c880043ca1b7f9b817e1d1b7c83846e4320c'
MAX_JSON = 8*1024**2
MAX_PAYLOAD = 80*1024**2
RUN_ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha_file(path):
    path=Path(path)
    require(not path.is_symlink(), 'Symlink file: '+str(path))
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'Nonregular input')
        while chunk:=stream.read(1024**2):digest.update(chunk)
        after=os.fstat(stream.fileno())
    require(identity(before)==identity(after)==identity(path.stat()),'File changed during hash: '+str(path))
    return digest.hexdigest()


def identity(value):
    return value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns


def read_json(path, expected=None):
    require(Path(path).stat().st_size<=MAX_JSON,'Oversized JSON')
    if expected is not None:require(sha_file(path)==expected,'JSON SHA mismatch: '+str(path))
    def reject(value):raise ValueError('Nonfinite JSON: '+value)
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate JSON key');result[key]=value
        return result
    data=json.loads(Path(path).read_bytes(),parse_constant=reject,object_pairs_hook=unique)
    if expected is not None:require(sha_file(path)==expected,'JSON changed during parse')
    return data


def save_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
        stream.flush();os.fsync(stream.fileno())


def label(case):
    return 'case-%02d-diagnostic%d-empty%d'%(case['index'],case['diagnostics'],case['empty'])


def expected_payloads():
    run=RUN_ROOT/JOB
    return {run/role/(label(case)+'.actual.pt') for role in ROLES for case in CASES} | {
        run/'base_repeat'/(label(case)+'.violations.pt') for case in CASES[:2]}


def tensor_bytes(torch,value):
    return value.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()


def tree_digest(torch,value):
    """Independent implementation of the frozen helper's documented encoding.

    No helper is imported. Array-valued RNG was tensorized in the archive.
    """
    result=hashlib.sha256()
    def walk(item):
        if isinstance(item,torch.Tensor):
            require(item.device.type=='cpu','Non-CPU loaded tensor')
            result.update(str((str(item.dtype),list(item.shape))).encode())
            result.update(tensor_bytes(torch,item))
        elif isinstance(item,dict):
            for key in sorted(item,key=lambda key:(type(key).__name__,str(key))):
                result.update(repr(key).encode());walk(item[key])
        elif isinstance(item,(list,tuple)):
            result.update(type(item).__name__.encode())
            for part in item:walk(part)
        else:
            require(item is None or type(item) in (bool,int,float,str),'Unexpected payload object')
            result.update(repr(item).encode())
    walk(value)
    return result.hexdigest()


def finite_cpu(torch,value):
    if isinstance(value,torch.Tensor):
        return value.device.type=='cpu' and bool(torch.isfinite(value).all())
    if isinstance(value,dict):return all(finite_cpu(torch,v) for v in value.values())
    if isinstance(value,(list,tuple)):return all(finite_cpu(torch,v) for v in value)
    return type(value) is not float or math.isfinite(value)


def load_payload(torch, path, record, allowed):
    """Only the exact fixed14 case/mask paths can reach torch.load."""
    path=Path(path)
    require(path in allowed and str(path)==record['path'],'Payload outside exact whitelist')
    require(not path.is_symlink() and path.stat().st_size==record['bytes']<=MAX_PAYLOAD,'Payload size/type')
    require(sha_file(path)==record['sha256'],'Payload changed BEFORE load')
    before=identity(path.stat())
    with path.open('rb') as stream:
        require(identity(os.fstat(stream.fileno()))==before,'Payload identity changed at open')
        value=torch.load(stream,map_location='cpu',weights_only=True)
        require(identity(os.fstat(stream.fileno()))==before,'Payload mutated during load')
    require(identity(path.stat())==before and sha_file(path)==record['sha256'],'Payload changed AFTER load')
    require(finite_cpu(torch,value),'Nonfinite/nonCPU payload')
    return value


def tolerance(path, floating=True):
    if not floating:return dict(rtol=0.,atol=0.)
    return TOLS['ce' if path.endswith('/ce') else 'scalars' if path.endswith(('/loss','/bc_loss')) else 'gradient']


def recompute(torch,actual,expected,root):
    """Direct native isclose, independent of the producer's comparator."""
    records=[];masks={};none_paths=[]
    def visit(a,b,path):
        if isinstance(b,torch.Tensor):
            require(isinstance(a,torch.Tensor) and a.shape==b.shape and a.dtype==b.dtype,'Tensor structure: '+path)
            require(finite_cpu(torch,a) and finite_cpu(torch,b),'Nonfinite tensor: '+path)
            tol=tolerance(path,a.is_floating_point())
            bad=~torch.isclose(a,b,**tol,equal_nan=False)
            error=(a.double()-b.double()).abs();bound=tol['atol']+tol['rtol']*b.double().abs()
            row=dict(path=path,shape=list(a.shape),dtype=str(a.dtype),tolerance=tol,
                actual_sha256=hashlib.sha256(tensor_bytes(torch,a)).hexdigest(),
                expected_sha256=hashlib.sha256(tensor_bytes(torch,b)).hexdigest(),
                max_abs=float(error.max()) if error.numel() else 0.,
                l2_error=float(torch.linalg.vector_norm((a.double()-b.double()).reshape(-1))),
                reference_l2=float(torch.linalg.vector_norm(b.double().reshape(-1))),
                passed=not bool(bad.any()),violations=int(bad.sum()),coordinate_examples=[])
            def coordinate(index):
                key=tuple(index)
                return dict(index=index,actual=float(a[key]),expected=float(b[key]),
                    signed_difference=float(a[key].double()-b[key].double()),
                    absolute_error=float(error[key]),allowed_bound=float(bound[key]))
            if row['violations']:
                positions=torch.nonzero(bad,as_tuple=False)
                row['coordinate_examples']=[coordinate(index) for index in positions[:16].tolist()]
                worst=torch.nonzero(bad & (error==error[bad].max()),as_tuple=False)[0].tolist()
                row['max_violation']=coordinate(worst)
                masks[path]=bad
            records.append(row)
        elif isinstance(b,dict):
            require(isinstance(a,dict) and set(a)==set(b),'Mapping structure: '+path)
            for key in b:visit(a[key],b[key],path+'/'+str(key))
        elif isinstance(b,(list,tuple)):
            require(type(a) is type(b) and len(a)==len(b),'Sequence structure: '+path)
            for i,(left,right) in enumerate(zip(a,b)):visit(left,right,path+'/'+str(i))
        elif type(b) is float:
            require(type(a) in (int,float) and math.isfinite(a) and math.isfinite(b),'Nonfinite/malformed scalar')
            tol=tolerance(path)
            records.append(dict(path=path,actual=a,expected=b,tolerance=tol,
                passed=math.isclose(a,b,rel_tol=tol['rtol'],abs_tol=tol['atol']),
                predicate='original math.isclose',absolute_error=abs(a-b),
                allowed_bound=max(tol['atol'],tol['rtol']*max(abs(a),abs(b)))))
        else:
            require(type(a) is type(b) and a==b,'None/boolean/control differs: '+path)
            if b is None:none_paths.append(path)
    visit(actual,expected,root)
    return records,masks,none_paths


def equal_record(computed,saved):
    """Exact hashes/predicates/counts/coordinates; disclosed double L2 check.

    L2 uses a CPU double reduction. The1e-12/1e-15 check below concerns that
    descriptive statistic only and never changes a learner tolerance/mask.
    """
    for key,value in computed.items():
        require(key in saved,'Missing producer statistic: '+key)
        if key in ('l2_error','reference_l2'):
            require(math.isclose(value,saved[key],rel_tol=1e-12,abs_tol=1e-15),'L2 statistic mismatch: '+computed['path'])
        else:require(value==saved[key],'Statistic mismatch '+computed['path']+'/'+key)


def parameter_names(phase):
    names=phase['before']['steps']
    require(isinstance(names,dict) and len(names)==99 and all(type(name) is str for name in names),
            'Expected exactly99 captured named parameter steps')
    return set(names)


def validate_payload(torch,payload,row,role,case,input_sha,state_sha,rng_sha,expected_gradient_names):
    require(set(payload)=={'variant','case','numerical','pre_rng','post_rng','pre_state_sha256',
                          'post_state_sha256','input_manifest_sha256','update_calls'},'Payload field set')
    require(payload['variant']==role and payload['case']==case and payload['input_manifest_sha256']==input_sha,'Payload case/input identity')
    require(payload['update_calls']==row['update_calls']==ZERO_CALLS,'Captured update call nonzero')
    require(payload['pre_state_sha256']==payload['post_state_sha256']==row['pre_state_sha256']==row['post_state_sha256']==state_sha,
            'Captured scientific state fingerprint differs')
    for when in ('pre','post'):
        value=payload[when+'_rng']
        require(set(value)=={'python','numpy','cpu','cuda'},'RNG components')
        observed={key:tree_digest(torch,part) for key,part in value.items()}
        require(observed==row[when+'_rng_sha256']==rng_sha,'RNG digest differs')
    values=payload['numerical']
    require(set(values)=={'ce','loss','bc_loss','diagnostic_output','gradient','diagnostics','empty'},'Numerical payload fields')
    require(values['diagnostics']==case['diagnostics'] and values['empty']==case['empty'],'Numerical case controls')
    require(values['ce'].shape==(4096,) and values['ce'].dtype==torch.float32 and
            values['diagnostic_output'].shape==(12,) and values['diagnostic_output'].dtype==torch.float32,'Fixed numerical output geometry')
    require(type(values['loss']) is float and type(values['bc_loss']) is float and isinstance(values['gradient'],dict),'Loss/gradient structure')
    require(set(values['gradient'])==expected_gradient_names,'Gradient name coverage differs from captured parameter steps')
    require(all(value is None or isinstance(value,torch.Tensor) and value.dtype==torch.float32
                for value in values['gradient'].values()),'Native gradient types')
    return values


def prepare(pins):
    run=RUN_ROOT/JOB
    require(pins['job']==JOB and pins['run']==str(run),'Fixed job mismatch')
    prior=RUN_ROOT/'warmup-repeatability-reviewed1-independent-json-scientific-review-20261017/review-receipt.json'
    archive=RUN_ROOT/'warmup-repeatability-reviewed1-terminal-root-archive-20261017/archive-manifest.json'
    require(sha_file(prior)==PRIOR_SHA and sha_file(archive)==ARCHIVE_SHA,'Prior/terminal archive changed')
    provenance=read_json(prior,PRIOR_SHA)
    terminal=read_json(archive,ARCHIVE_SHA)
    require(provenance['status']=='PASS_WITH_REPORTED_AA_REPEATABILITY_MISMATCH' and provenance['qualification_pass'] is False,'Prior audit status')
    require(pins['sources']=={name:dict(sha256=record['sha256'],bytes=record['bytes'])
                            for name,record in terminal['sources'].items()},'Source archive map differs')
    original={record['path']:dict(path=record['path'],sha256=record['sha256'],bytes=record['bytes'])
              for record in provenance['artifacts']}
    require(all(record==original[path] for path,record in pins['payloads'].items()),'Payload pins differ from original audit')
    require(pins['json_inputs']=={path:record for path,record in original.items()
                                 if path.startswith(str(run)+'/') and path.endswith('.json')},'JSON inventory differs from original audit')
    for name,record in pins['sources'].items():
        path=RUN_ROOT/'warmup-repeatability-reviewed1-terminal-root-archive-20261017/bound-sources'/name
        require(sha_file(path)==record['sha256'],'Archived source changed: '+name)
    require(pins['sources']['source-lock.json']['sha256']==LOCK_SHA and pins['sources']['cuda_trace_worker.py']['sha256']==WORKER_SHA,'Numerical source boundary')
    lock=read_json(RUN_ROOT/'warmup-repeatability-reviewed1-terminal-root-archive-20261017/bound-sources/source-lock.json',LOCK_SHA)
    require(all(lock['tolerances'][key]==value for key,value in TOLS.items()),'Original tolerance changed')
    require(lock['variants']==list(ROLES) and lock['attempts']==0 and lock['warmup_cases']==list(CASES),'Original protocol changed')
    expected=set(pins['payloads'])
    require(expected=={str(path) for path in expected_payloads()},'Pinned load whitelist differs from fixed14 paths')
    actual={str(path) for path in run.glob('*/case-*.pt')}
    require(actual==expected and len(expected)==14,'Payload inventory not exactly12 actual+2 masks')
    require(not (run/'on').exists(),'Unexpected ON role')
    for role in ROLES:
        needed={label(case)+suffix for case in CASES for suffix in
                ('.actual.pt','.entered.json','.payload-retained.json','.json')}
        if role!='base_a':needed|={label(case)+'.comparison.json' for case in CASES}
        if role=='base_repeat':needed|={label(case)+'.violations.pt' for case in CASES[:2]}
        require({path.name for path in (run/role).glob('case-*')}==needed,'Extra/missing original case evidence: '+role)
    for path,record in pins['json_inputs'].items():require(sha_file(path)==record['sha256'],'Bound JSON changed')
    return run,provenance


def audit(torch,pins,output):
    run,prior=prepare(pins)
    allowed={Path(path) for path in pins['payloads']}
    phases={role:read_json(run/role/'phase-result.json',pins['json_inputs'][str(run/role/'phase-result.json')]['sha256']) for role in ROLES}
    gradient_names={role:parameter_names(phase) for role,phase in phases.items()}
    input_sha=sha_file(run/'inputs/inputs.json')
    state_sha=prior['scientific_control_summary']['persistent_scientific_state_sha256']
    rng_sha=prior['scientific_control_summary']['rng_sha256']
    for role,phase in phases.items():
        require(phase['status']=='OBSERVATIONS_COMPLETE' and phase['variant']==role and phase['qualification_pass'] is False
                and phase['source_lock_sha256']==LOCK_SHA and phase['input_manifest_sha256']==input_sha,'Phase identity')
        require([row['case'] for row in phase['cases']]==list(CASES),'Four fixed cases')
        require(phase['before']==phase['after'] and phase['update_calls']==ZERO_CALLS,'Captured before/after control differs')
        exposure=phase['before']['exposure']
        require(all(v==0 for v in exposure['total'].values()) and exposure['unclassified_started_total']==0,'Captured optimizer exposure nonzero')
        require(phase['before']['persistent_finite'] and phase['before']['modes']==[True,False,False],'Captured state/modes invalid')
    results=[]
    for case in CASES:
        idx=case['index']-1;name=label(case)
        baseline_row=phases['base_a']['cases'][idx]
        path=Path(baseline_row['actual']['path'])
        require(baseline_row['actual']==pins['payloads'][str(path)],'BASE payload receipt differs')
        base=load_payload(torch,path,pins['payloads'][str(path)],allowed)
        expected=validate_payload(torch,base,baseline_row,'base_a',case,input_sha,state_sha,rng_sha,gradient_names['base_a'])
        results.append(dict(role='base_a',case=case,payload_sha256=baseline_row['actual']['sha256'],reference_only=True,
                            gradient_tensors=sum(isinstance(v,torch.Tensor) for v in expected['gradient'].values()),
                            gradient_none=sum(v is None for v in expected['gradient'].values())))
        for role in ROLES[1:]:
            row=phases[role]['cases'][idx];path=Path(row['actual']['path'])
            require(row['actual']==pins['payloads'][str(path)],'Compared payload receipt differs')
            payload=load_payload(torch,path,pins['payloads'][str(path)],allowed)
            actual=validate_payload(torch,payload,row,role,case,input_sha,state_sha,rng_sha,gradient_names[role])
            records,masks,none_paths=recompute(torch,actual,expected,name)
            saved=row['comparisons']
            require([r['path'] for r in records]==[r['path'] for r in saved],'Comparison record coverage/order differs')
            for computed,original in zip(records,saved):equal_record(computed,original)
            passed=all(record['passed'] for record in records)
            require(passed==row['comparison_pass'],'Case pass differs')
            if masks:
                mask_record=row['all_failed_coordinate_masks'];mask_path=Path(mask_record['path'])
                require(mask_record==pins['payloads'][str(mask_path)],'Mask record identity')
                archived=load_payload(torch,mask_path,mask_record,allowed)
                require(set(archived)==set(masks),'Mask path coverage')
                for key,value in masks.items():require(archived[key].dtype==torch.bool and torch.equal(value,archived[key]),'Full mask differs: '+key)
                del archived
            else:require('all_failed_coordinate_masks' not in row,'Spurious saved masks')
            result=dict(role=role,case=case,recomputed_matches_original=True,comparison_pass=passed,
                records=records,none_paths=none_paths,failed_tensor_masks=len(masks),
                failed_coordinates=sum(record.get('violations',0) for record in records),
                payload_sha256=row['actual']['sha256'])
            save_json(output/(role+'-'+name+'.json'),result);results.append(result)
            del payload,actual,records,masks;gc.collect()
        del base,expected;gc.collect()
    for role in ROLES[1:]:
        require(all(result['comparison_pass'] for result in results if result['role']==role)==phases[role]['comparison_pass'],'Role pass differs')
    aggregate=read_json(run/'result.json',pins['json_inputs'][str(run/'result.json')]['sha256'])
    require(aggregate['status']=='OBSERVATIONS_COMPLETE' and aggregate['qualification_pass'] is False and
            aggregate['comparison_pass']==all(phase['comparison_pass'] for phase in phases.values()),'Original aggregate outcome differs')
    # Whole captured JSON inventory and source pins are checked again at end.
    prepare(pins)
    return dict(schema='robotron-archived-warmup-independent-cpu-numerical-audit-v1',status='PASS',job=JOB,
        archive_numeric_records_verified=True,rows=results,qualification_pass=False,
        audit_does_not_change_original_comparison_outcome=True,
        scope=['Archived warmup output/gradient/RNG/mask tensor recomputation only; no new backward or optimizer operation',
            'No captured checkpoint/model/Adam/scaler/replay contents loaded; scientific persistent-state hashes/zero-update counters are checked as captured metadata only',
            'A/A mismatches remain real at the original threshold; OFF passing these cases does not establish general parity',
            'No ON observer, full train_step, live acquisition, operator cause, game quality or learning benefit established'],
        descriptive_l2_verification_tolerance=dict(rtol=1e-12,atol=1e-15),learner_tolerances=TOLS)


def execute(args):
    require(args.job==JOB,'Only the exact archived job is authorized')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CUDA must be hidden before importing Torch')
    require(sha_file(__file__)==args.source_sha256,'Auditor source SHA mismatch')
    pin_path=Path(__file__).parent/'input-pins.json'
    pins=read_json(pin_path,args.pins_sha256)
    output=Path(args.output)
    require(output.is_absolute() and not output.exists() and output.parent.is_dir()
            and not output.resolve().is_relative_to((RUN_ROOT/JOB).resolve()),'New output outside original run required')
    output.mkdir()
    try:
        save_json(output/'execution.json',dict(job=JOB,source_sha256=args.source_sha256,pins_sha256=args.pins_sha256,
                                            CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES']))
        prepare(pins)
        import torch # explicit authorized CPU execution only
        torch.set_num_threads(2);torch.set_num_interop_threads(2)
        require(str(torch.__version__)=='2.13.0+cu130' and not torch.cuda.is_initialized(),'Wrong CPU framework/context state')
        report=audit(torch,pins,output)
        require(not torch.cuda.is_initialized(),'Unexpected CUDA initialization')
        require(sha_file(__file__)==args.source_sha256 and sha_file(pin_path)==args.pins_sha256,'Auditor changed')
        save_json(output/'review-receipt.json',report)
        save_json(output/'completion.json',dict(status='PASS',receipt_sha256=sha_file(output/'review-receipt.json'),
                                               artifacts_sha256={p.name:sha_file(p) for p in output.iterdir()}))
        return 0
    except BaseException as error:
        try:save_json(output/'failure.json',dict(status='INVALID_OR_INCOMPLETE_AUDIT',error=type(error).__name__,message=str(error)[:2000]))
        except Exception:pass
        return 1


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if '--execute' not in argv:print(PLAN);return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    for flag in ('job','source-sha256','pins-sha256','output'):parser.add_argument('--'+flag,required=True)
    return execute(parser.parse_args(argv))


if __name__=='__main__':
    raise SystemExit(main())
