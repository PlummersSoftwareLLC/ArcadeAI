"""UNSELECTED offline full per-sample health comparison: local kernel sharing.

This does not replace the full accepted/rejected health replay or h.checked.
Root alone may benchmark a bounded, independently qualified, closed C1 subset.
"""
import argparse
import ast
import copy
import importlib.util
import math
import mmap
import socket
import subprocess
import urllib.request
from types import SimpleNamespace
import hashlib
import json
import os
from pathlib import Path
import resource
import stat
import struct
import sys
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = ROOT/'logs/managed-learning-20261015/run-26'
HERE = B/'future-health-review-read-once-prototype-original01-20261030/full-health-integration-original02'
ORIGINAL_REGISTRY = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/continuous_physical192_registry_v5.py', 'sha256': '8cc5340708a73ffb97b16be4b96e72b3d5560ee0b371b7ffd8d67c4074cf76b4', 'bytes': 49518, 'identity': {'device': 2304, 'inode': 85353797, 'bytes': 49518, 'mtime_ns': 1793309467460439411, 'ctime_ns': 1793309543185873072, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
ORIGINAL_BASE = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/continuous_physical192_health_main_journal128_v1.py', 'sha256': '95502ef826a20a6a62a014236ea79956ee3af5c05dda23b07c8ebef459c7ef7a', 'bytes': 37464, 'identity': {'device': 2304, 'inode': 85380114, 'bytes': 37464, 'mtime_ns': 1793325874164729893, 'ctime_ns': 1793325874164729893, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
ORIGINAL_TRANSPORT = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/continuous_physical192_transport_main_journal128_v1.py', 'sha256': '3108ccc41b55285ca3381072be81fcd75ad1fcc68cf11711ba01025ef8cc55f6', 'bytes': 17116, 'identity': {'device': 2304, 'inode': 85380124, 'bytes': 17116, 'mtime_ns': 1793325874181550458, 'ctime_ns': 1793325874181550458, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
SLOTS = frozenset(map(str,range(192)))


def require(value, reason):
    if not value:
        raise ValueError(reason)



def _read_shared_anchors(selected, read_pin, shared):
    pins={key:selected[key] for key in ('anchors','selection')}
    if not shared:
        saved=copy.deepcopy(pins)
        values=(read_pin(saved['anchors']),read_pin(saved['selection']))
        require(pins==saved,'Original fullpins changed during shared authentication')
        shared.update(pins=saved,values=values)
    require(set(shared)=={'pins','values'} and pins==shared['pins'],
            'Exact within-sample anchor/selection fullpins changed')
    return shared['values']



def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def checked_bytes(value, maximum):
    """Benchmark metadata only: one bounded buffer, full SHA/full8 pre/post.

    This is NOT substituted for any production helper or recording callback.
    """
    require(type(value)is dict and set(value)=={'path','sha256','bytes','identity'},'Exact metadata fullpin required')
    path=Path(value['path'])
    require(path.is_absolute() and path.resolve(strict=True)==path and not path.is_symlink(), 'Canonical metadata path required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and identity(before)==value['identity']
            and before.st_uid==os.getuid() and before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o444
            and 0<=before.st_size==value['bytes']<=maximum,'Sealed bounded metadata identity differs')
        with os.fdopen(os.dup(fd),'rb')as stream:
            raw=stream.read(maximum+1)
        require(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']
            and identity(os.fstat(fd))==value['identity']==identity(path.lstat()),'Metadata bytes or full8 changed')
        return raw
    finally:
        os.close(fd)


def read_metadata(value, maximum, metadata_inputs):
    raw=checked_bytes(value,maximum)
    metadata_inputs.append(copy.deepcopy(value))
    return json.loads(raw)


def _compile_namespace(raw, path, injected, replacements=None, omitted=()):
    """Bind private offline collaborators before compilation; never patch modules."""
    nodes=[]
    replacements={}if replacements is None else replacements
    for node in ast.parse(raw).body:
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.If)):
            continue
        if isinstance(node,ast.FunctionDef)and node.name in omitted:
            continue
        if isinstance(node,ast.FunctionDef)and node.name in replacements:
            node=copy.deepcopy(replacements[node.name])
        nodes.append(node)
    namespace=dict(__name__='_offline_full_health_validation',__file__=path,
        hashlib=hashlib,json=json,math=math,os=os,Path=Path,stat=stat,struct=struct,
        copy=copy,importlib=importlib,mmap=mmap,subprocess=subprocess,time=time,
        urllib=urllib,socket=socket,sys=sys)
    namespace.update(injected)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),path,'exec'),namespace)
    return SimpleNamespace(**namespace)


def _factory_without_module_cache(node, selected_name):
    node=copy.deepcopy(node)
    require(isinstance(node.body[0],ast.Expr)and isinstance(node.body[0].value,ast.Call)
        and isinstance(node.body[0].value.func,ast.Name)and node.body[0].value.func.id=='require',
        'Original factory source-SHA guard must remain first')
    node.body=[node.body[0],ast.Return(value=ast.Name(id=selected_name,ctx=ast.Load()))]
    return node


def selected_registry_reader(raw):
    nodes={n.name:n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}
    namespace=dict(os=os,Path=Path,stat=stat,hashlib=hashlib,json=json)
    for name in ('require','identity','read_pin'):
        exec(compile(ast.fix_missing_locations(ast.Module(body=[nodes[name]],type_ignores=[])),
            ORIGINAL_REGISTRY['path'],'exec'),namespace)
    return namespace['read_pin']


def assemble_full_health(source_bytes, read_pin_callback, optimized):
    """Complete saved-snapshot validation; original outer review stays required."""
    registry_nodes={n.name:n for n in ast.parse(source_bytes['registry']).body if isinstance(n,ast.FunctionDef)}
    replacements={}
    injected=dict(read_pin=read_pin_callback)
    if optimized:
        kernel=copy.deepcopy(registry_nodes['kernel_eval_exit'])
        replacement=ast.parse("anchors,selection=_read_shared_anchors(selected,read_pin,_kernel_shared)\nvalue=read_pin(pin)").body
        old_reads=ast.parse("anchors=read_pin(selected['anchors']); selection=read_pin(selected['selection']); value=read_pin(pin)").body
        found=False
        for index in range(len(kernel.body)-2):
            if [ast.dump(x,include_attributes=False)for x in kernel.body[index:index+3]]==[ast.dump(x,include_attributes=False)for x in old_reads]:
                kernel.body[index:index+3]=replacement;found=True;break
        require(found,'Exact original kernel three-read assignment required')
        kernel.args.kwonlyargs.append(ast.arg(arg='_kernel_shared'))
        kernel.args.kw_defaults.append(None)
        replacements['kernel_eval_exit']=kernel
        snapshot=copy.deepcopy(registry_nodes['validate_snapshot'])
        snapshot.body.insert(1,ast.parse('_kernel_shared={}').body[0])
        changed=0
        for node in ast.walk(snapshot):
            if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='kernel_eval_exit':
                node.keywords.append(ast.keyword(arg='_kernel_shared',value=ast.Name(id='_kernel_shared',ctx=ast.Load())))
                changed+=1
        require(changed==1,'Exactly one original snapshot kernel-exit call required')
        replacements['validate_snapshot']=snapshot
        injected['_read_shared_anchors']=_read_shared_anchors
    registry=_compile_namespace(source_bytes['registry'],ORIGINAL_REGISTRY['path'],injected,replacements,omitted=('read_pin',))
    base_nodes={n.name:n for n in ast.parse(source_bytes['base']).body if isinstance(n,ast.FunctionDef)}
    base=_compile_namespace(source_bytes['base'],ORIGINAL_BASE['path'],dict(_selected_registry=registry),
        dict(registry=_factory_without_module_cache(base_nodes['registry'],'_selected_registry')))
    transport_nodes={n.name:n for n in ast.parse(source_bytes['transport']).body if isinstance(n,ast.FunctionDef)}
    return _compile_namespace(source_bytes['transport'],ORIGINAL_TRANSPORT['path'],dict(_selected_base=base),
        dict(base=_factory_without_module_cache(transport_nodes['base'],'_selected_base')))


def checked_snapshot(row, index, worker_pin, worker, owner):
    require(row['index']==index and row['job']==worker_pin and row['nonce']==worker['nonce']
        and row['owner']==owner,'Actual saved accepted row binding differs')
    return row['snapshot']


def copied_negative_inputs(case,sample,previous):
    """Eight bounded faults; every change stays in freshly copied input data."""
    cases=[]
    def add(name,mutate):
        value=copy.deepcopy(dict(case=case,sample=sample,previous=previous))
        before=canonical(value);mutate(value)
        require(canonical(value)!=before,'Negative mutation did not change input')
        cases.append((name,value))
    def bad_api(x):x['sample']['api_wire_sha256']='0'*64
    add('raw_API_SHA_drift',bad_api)
    def epoch(x):
        s=x['sample'];s['api']['host_pipeline']['learning_exposure']['optimizer']['epoch']+=1
        s['raw_API_wire']=canonical(s['api']).decode();s['api_wire_sha256']=hashlib.sha256(s['raw_API_wire'].encode()).hexdigest()
    add('optimizer_epoch_drift_with_coherent_wire',epoch)
    def actor(x):
        slot=next(slot for slot in x['sample']['actors']if x['case']['slot_eval'][slot]is False)
        x['sample']['actors'][slot]['starttime_ticks']+=1
    add('original_TRAIN_birth_drift',actor)
    def tcp(x):
        for name in ('tcp','tcp6'):x['sample']['transport']['raw_tables'][name]=''
    add('missing_current_owned_TCP',tcp)
    def capture(x):x['sample']['capture_started_monotonic_s']=x['sample']['monotonic_s']-5.001
    add('capture_bracket_exceeds5s',capture)
    def gap(x):
        if x['previous']is None:x['previous']=copy.deepcopy(x['sample'])
        x['previous']['monotonic_s']=x['sample']['monotonic_s']-2.001
    add('previous_accepted_gap_exceeds2s',gap)
    def anchor(x):x['case']['continuous']['eval_exit_witness']['anchors']['identity']['inode']+=1
    add('held_anchor_full8_inode_drift',anchor)
    def cleanup(x):
        slot=next(iter(x['sample']['EVAL_cleanup_captures']))
        c=x['sample']['EVAL_cleanup_captures'][slot];c['value']['cleanup_error']='UNRECOGNIZED_RECORDED_ERROR'
        c['raw_wire']=canonical(c['value']).decode();c['sha256']=hashlib.sha256(c['raw_wire'].encode()).hexdigest()
    add('unknown_cleanup_error_with_coherent_wire',cleanup)
    return cases


def outcome_of_validation(health,case,sample,previous):
    try:
        value=health.validate(case,sample,previous=previous)
    except(ValueError,AssertionError)as error:
        return dict(accepted=False,error_type=type(error).__name__,error=str(error))
    return dict(accepted=True,value=value)


def recorder(original_read_pin):
    """Explicit callback; invoke actual original verifier before recording success."""
    calls=[]
    def read_pin(value, *, as_json=True, immutable=True):
        result=original_read_pin(value,as_json=as_json,immutable=immutable)
        calls.append(dict(pin=copy.deepcopy(value),as_json=as_json,immutable=immutable))
        return result
    return read_pin,calls


def dependency_set(calls):
    return sorted({canonical(row).decode() for row in calls})


def measure(function):
    wall=time.perf_counter();cpu=time.process_time()
    value=function()
    return value,dict(wall_s=time.perf_counter()-wall,CPU_s=time.process_time()-cpu)


def deny_unsafe(event,args,archive_policy):
    if event in ('os.system','subprocess.Popen','socket.connect','socket.bind'):
        raise ValueError('No process/network action in this component probe')
    if event=='open':
        path=args[0]
        if isinstance(path,(str,bytes,os.PathLike)):
            path=os.fsdecode(path)
            require(not path.startswith(('/proc/','/sys/','/dev/'))
                and not path.endswith(('.pt','.pth','.npy','.npz'))
                and (not path.endswith('.jsonl')or path==archive_policy['archive'])
                and '/models_dqn/'not in path,'No process/model/replay/raw-journal body reads')
    if event=='import':
        require(not str(args[0]).split('.')[0]in ('torch','numpy','socket','subprocess'), 'No GPU/model/network import')


def execute(selection_pin, own_pin):
    require(not any(name.split('.')[0]in ('torch','numpy') for name in sys.modules), 'No Torch/NumPy in metadata probe')
    resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30))
    archive_policy=dict(archive=None)
    sys.addaudithook(lambda event,args:deny_unsafe(event,args,archive_policy))
    metadata_inputs=[]
    selected=read_metadata(selection_pin,262144,metadata_inputs)
    require(selected['schema']=='robotron-root-closed-C1-full-health-integration-probe-v2'
        and selected['prototype']==own_pin and selected['original_registry']==ORIGINAL_REGISTRY
        and selected['original_base']==ORIGINAL_BASE and selected['original_transport']==ORIGINAL_TRANSPORT,
        'Exact unselected component sources required')
    checked_bytes(own_pin,262144)
    q=read_metadata(selected['closed_C1_qualification'],2_000_000,metadata_inputs)
    require(q['schema']=='robotron-root-deadline32-leg-qualification-v1'
        and q['status']=='INDEPENDENT_DEADLINE32_QUALIFIED' and q['leg']=='C1'
        and type(q['actual_review_tool_terminal_exit'])is int and q['actual_review_tool_terminal_exit']==0
        and q['all_six_descriptors_resources_argv_birth_units_cgroup_release_verified']is True,
        'Actual independently closed C1 qualification required')
    report=read_metadata(q['independent_report'],64<<20,metadata_inputs)
    require(report['schema']=='robotron-deadline32-original-leg-independent-review-v1'
        and report['status']=='PASS' and report['leg']=='C1' and report['actual_native_exit']==0
        and report['deadline_metric_independently_qualified']is True
        and report['positive_owned_native_observer_children_threads_and_lease_closure']is True,
        'Actual closed original independent review required')
    life_pin=report['main_health']['lifecycle']
    life=read_metadata(life_pin,2_000_000,metadata_inputs)
    require(life['schema']=='robotron-round-observer-native-lifecycle-v1' and life['success']is True
        and life['all_original_processes_reaped']is True and life['original_scope_released']is True,
        'Original closed observer lifecycle required')
    native=read_metadata(life['native_job'],4<<20,metadata_inputs)
    require(native['leg']=='C1' and report['original_job']==life['native_job'], 'Only this qualified closed C1 native scope')
    worker=read_metadata(life['worker_job'],4<<20,metadata_inputs)
    require(worker['native_job']==life['native_job'] and report['main_health']['original_job']==life['worker_job'],
        'Closed native/worker/report binding differs')
    outcome=read_metadata(life['outcome'],64<<20,metadata_inputs)
    require(outcome['job']==life['worker_job'] and outcome['success']is True and outcome['error']is None
        and outcome['all_writer_threads_stopped']is True and outcome['uncommitted_raw']==[],
        'Actual fully sealed successful outcome required')
    case=read_metadata(worker['case'],4<<20,metadata_inputs)
    prior_prefix=read_metadata(case['continuous']['completed_clients_prefix'],2_000_000,metadata_inputs)
    archive=prior_prefix['archive']
    require(prior_prefix['schema']=='robotron-prior-cohort-EVAL-completed-prefix-v1'
        and prior_prefix['canonical_path']==str(Path(case['continuous']['eval_journal_directory'])/'completed_clients.jsonl')
        and archive['path']not in (prior_prefix['canonical_path'],str(Path(case['continuous']['eval_journal_directory'])/'games.jsonl'))
        and type(archive['bytes'])is int and 0<=archive['bytes']==prior_prefix['prefix_bytes']<=262144
        and archive['sha256']==prior_prefix['prefix_sha256']
        and archive['identity']['mode']=='0o444' and archive['identity']['uid']==os.getuid()
        and archive['identity']['nlink']==1
        and case['inputs'].get(archive['path'])==dict(sha256=archive['sha256'],identity=archive['identity']),
        'Only the exact case-held immutable historical prefix archive may bypass the raw-extension deny')
    archive_policy['archive']=archive['path']
    pins=selected['samples']
    require(type(pins)is list and 1<=len(pins)<=3 and len({p['path']for p in pins})==len(pins),
        'Select one to three distinct saved accepted C1 samples only')
    indices=[]
    for value in pins:
        matches=[index for index,entry in enumerate(outcome['samples'])if entry==value]
        require(len(matches)==1,'Sample is not an exact accepted outcome fullpin')
        indices.append(matches[0])
    require(indices==sorted(indices) and len(set(indices))==len(indices), 'Ordered distinct accepted subset required')
    source_bytes={key:checked_bytes(pin,2_000_000)for key,pin in
        (('registry',ORIGINAL_REGISTRY),('base',ORIGINAL_BASE),('transport',ORIGINAL_TRANSPORT))}
    original_read_pin=selected_registry_reader(source_bytes['registry'])
    owner=read_metadata(outcome['owner'],2_000_000,metadata_inputs)
    results=[];negative_results=[];negative_seed=None
    for ordinal,(value,index)in enumerate(zip(pins,indices)):
        row=read_metadata(value,8<<20,metadata_inputs)
        sample=checked_snapshot(row,index,life['worker_job'],worker,owner)
        if index==0:
            previous=None;previous_pin=None
        else:
            previous_pin=outcome['samples'][index-1]
            prior=read_metadata(previous_pin,8<<20,metadata_inputs)
            previous=checked_snapshot(prior,index-1,life['worker_job'],worker,owner)
        before=canonical(dict(case=case,sample=sample,previous=previous))
        old_read,old_calls=recorder(original_read_pin);new_read,new_calls=recorder(original_read_pin)
        original=assemble_full_health(source_bytes,old_read,False)
        prototype=assemble_full_health(source_bytes,new_read,True)
        order=('original','prototype')if ordinal%2==0 else('prototype','original');measured={}
        for name in order:
            health=original if name=='original'else prototype
            measured[name]=measure(lambda:health.validate(case,sample,previous=previous))
            require(canonical(dict(case=case,sample=sample,previous=previous))==before,'Validation mutated original input')
        require(measured['original'][0]==measured['prototype'][0],'Full per-sample health outputs differ')
        require(dependency_set(old_calls)==dependency_set(new_calls),'Unique full-health callback dependencies differ')
        first_new_calls=list(new_calls)
        repeated=prototype.validate(case,sample,previous=previous)
        repeat_calls=new_calls[len(first_new_calls):]
        require(repeated==measured['prototype'][0] and len(repeat_calls)==len(first_new_calls)
            and dependency_set(repeat_calls)==dependency_set(first_new_calls),
            'Same validator instance failed to reset authentication for the next validate call')
        require(canonical(dict(case=case,sample=sample,previous=previous))==before,'Repeated validation mutated original input')
        k=len(sample.get('EVAL_kernel_exit_receipts',{}))
        require(len(old_calls)-len(first_new_calls)==2*max(0,k-1),'Unexpected sharing callback delta')
        counts={name:dict(callback_calls=len(calls),callback_bytes=sum(x['pin']['bytes']for x in calls),
            unique_dependencies=len(dependency_set(calls)))for name,calls in (('original',old_calls),('prototype',first_new_calls))}
        results.append(dict(sample=value,index=index,actual_previous_accepted_sample=previous_pin,order=list(order),
            kernel_slots=k,outputs_equal=True,unique_dependencies_equal=True,inputs_unchanged=True,
            same_instance_second_validate_reauthenticates=True,second_validate_callback_calls=len(repeat_calls),
            original_outputs_sha256=hashlib.sha256(canonical(measured['original'][0])).hexdigest(),
            prototype_outputs_sha256=hashlib.sha256(canonical(measured['prototype'][0])).hexdigest(),
            original=measured['original'][1],prototype=measured['prototype'][1],counts=counts,
            original_dependency_set=[json.loads(x)for x in dependency_set(old_calls)],
            prototype_dependency_set=[json.loads(x)for x in dependency_set(first_new_calls)]))
        if negative_seed is None and sample.get('EVAL_cleanup_captures'):
            negative_seed=(sample,previous)
    require(negative_seed is not None,'Select a closed accepted sample with cleanup evidence for bounded negative checks')
    sample,previous=negative_seed;seed_before=canonical(dict(case=case,sample=sample,previous=previous))
    for label,value in copied_negative_inputs(case,sample,previous):
        old_read,old_calls=recorder(original_read_pin);new_read,new_calls=recorder(original_read_pin)
        original=assemble_full_health(source_bytes,old_read,False);prototype=assemble_full_health(source_bytes,new_read,True)
        before=canonical(value)
        old=outcome_of_validation(original,value['case'],value['sample'],value['previous'])
        require(canonical(value)==before,'Original validator mutated negative copied data')
        new=outcome_of_validation(prototype,value['case'],value['sample'],value['previous'])
        require(canonical(value)==before,'Prototype mutated negative copied data')
        require(old['accepted']is False and new==old,'Expected identical bounded negative rejection')
        require(dependency_set(old_calls)==dependency_set(new_calls),'Negative unique dependencies differ')
        negative_results.append(dict(label=label,expected_rejection=True,error_type=old['error_type'],error=old['error'],
            unique_dependencies_equal=True,inputs_unchanged=True))
    require(len(negative_results)==8 and canonical(dict(case=case,sample=sample,previous=previous))==seed_before,
        'Bounded negative coverage or original input immutability differs')
    require(not any(name.split('.')[0]in ('torch','numpy')for name in sys.modules),'Unexpected model import')
    output=Path(selected['output'])
    require(output.parent==HERE and output.name.startswith('Root-') and output.resolve(strict=False)==output
        and not output.exists(),'Fresh direct-child Root-only probe output required')
    output.mkdir(mode=0o700)
    value=dict(schema='robotron-closed-C1-full-per-sample-health-integration-probe-result-v2',status='PASS',
        source=own_pin,selection=selection_pin,original_registry=ORIGINAL_REGISTRY,original_base=ORIGINAL_BASE,
        original_transport=ORIGINAL_TRANSPORT,closed_C1_qualification=selected['closed_C1_qualification'],metadata_inputs=metadata_inputs,
        samples=results,negative_checks=negative_results,resource_limits=dict(CPU_seconds=60,address_space_bytes=1<<30,external_wall_s=90),
        max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        timing_scope='transport.validate including original factory/dependency checks; excludes source assembly, sealed row hash/JSON parse, outer durability and full-corpus review',
        full_per_sample_health_outputs_equal=True,full_closed_review_replaced=False,accepted_or_rejected_evidence_requalified=False,
        outer_fe911_durability_rejection_coverage_source_unchanged=True,
        dependency_set_scope='Exact original registry.read_pin successful callbacks; h.checked and all outer helper hooks unchanged',
        imported_production_modules_monkeypatched=False,cross_sample_evidence_cache=False,
        current_or_future_study_source_selected=False,throughput_or_quality_credit=False,
        explicit_immutable_prior_cohort_archive=archive,
        no_model_Torch_proc_API_or_live_raw_journal_reads=True)
    raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    with(output/'report.json').open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status='PASS',output=str(output/'report.json'),sha256=hashlib.sha256(raw).hexdigest(),
        samples=len(results),negative_checks=len(negative_results),full_review_replaced=False)),flush=True)



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--selection-sha256')
    parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('SOURCE_ONLY_UNSELECTED_FULL_PER_SAMPLE_HEALTH_PROBE')
        return 0
    own=Path(__file__).resolve(strict=True)
    own_raw=own.read_bytes();info=own.lstat()
    require(hashlib.sha256(own_raw).hexdigest()==args.source_sha256,'Exact prototype source bytes required')
    own_pin=dict(path=str(own),sha256=args.source_sha256,bytes=len(own_raw),identity=identity(info))
    require(own.parent==HERE and identity(info)['mode']=='0o444','Frozen isolated prototype source required')
    require(args.selection is not None and args.selection_sha256 is not None,'Explicit immutable Root selection required')
    info=args.selection.lstat()
    selection_pin=dict(path=str(args.selection),sha256=args.selection_sha256,bytes=info.st_size,identity=identity(info))
    execute(selection_pin,own_pin)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
