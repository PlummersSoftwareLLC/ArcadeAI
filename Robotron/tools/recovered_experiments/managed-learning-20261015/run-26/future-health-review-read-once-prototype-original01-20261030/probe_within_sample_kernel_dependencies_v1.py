"""UNSELECTED component probe: share kernel-exit metadata within ONE sample.

This does not replace the full accepted/rejected health replay or h.checked.
Root alone may benchmark a bounded, independently qualified, closed C1 subset.
"""
import argparse
import ast
import copy
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
HERE = B/'future-health-review-read-once-prototype-original01-20261030'
ORIGINAL_REGISTRY = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/continuous_physical192_registry_v5.py', 'sha256': '8cc5340708a73ffb97b16be4b96e72b3d5560ee0b371b7ffd8d67c4074cf76b4', 'bytes': 49518, 'identity': {'device': 2304, 'inode': 85353797, 'bytes': 49518, 'mtime_ns': 1793309467460439411, 'ctime_ns': 1793309543185873072, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
SLOTS = frozenset(map(str,range(192)))


def require(value, reason):
    if not value:
        raise ValueError(reason)


def _kernel_eval_exit_with_shared(case, sample, slot, *, read_pin, shared):
    selected=case['continuous'].get('eval_exit_witness')
    pin=sample.get('EVAL_kernel_exit_receipts',{}).get(slot)
    require(selected is not None and pin is not None, 'No original positive EVAL exit/reap witness')
    publication=sample['EVAL_exit_witness_capture']['publication']['value']
    require(publication['exit_receipts'].get(slot)==pin,
            'Kernel exit file was not published after its producer fsync returned')
    anchors,selection=_read_shared_anchors(selected,read_pin,shared)
    value=read_pin(pin)
    require(anchors['schema']=='robotron-original37-EVAL-pidfd-held-anchors-v1'
            and anchors['selection']==selected['selection'] and anchors['source']==selected['source']
            and anchors['holder']==selected['holder'] and anchors['all37_acquired_while_originals_live'] is True
            and value['schema']=='robotron-original-EVAL-retained-pidfd-exit-v1'
            and value['anchors']==selected['anchors'] and value['selection']==selected['selection']
            and value['source']==selected['source'] and value['holder']==selected['holder']
            and value['nonce']==anchors['nonce']==selection['nonce']
            and value['slot']==int(slot) and value['anchor']==anchors['originals'][slot]
            and value['original']==selection['originals'][slot]
            and value['descriptor']==value['anchor']['descriptor']
            and value['request_ioctl']==0xc050ff0b and value['request_mask']==0x28
            and value['original_Popen_wait_called_claimed'] is False
            and value['actor_signals_or_wait_or_reap_performed'] is False,
            'Source-bound held-before-exit kernel EVAL authority differs')
    old=case['continuous']['original_slots'][slot]; child=old['original_child']; original=value['original']
    require(original['pid']==child['pid'] and original['birth']==child['birth']
            and original['parent']==child['parent'] and original['uid']==os.getuid()
            and original['initial_connection_binding']==old['connection_binding']
            and Path(pin['path'])==Path(selected['output'])/('exit-slot-%03d.json'%int(slot)),
            'Kernel receipt is not the original selected EVAL birth/connection/path')
    raw=bytes.fromhex(value['returned_raw80_hex']); initial=bytes.fromhex(value['anchor']['initial_info']['raw80_hex'])
    require(len(raw)==len(initial)==80 and value['returned_info']['raw80_hex']==value['returned_raw80_hex'],
            'Exact80-byte retained kernel buffers required')
    returned=struct.unpack_from('=Q',raw,0)[0]; supported=struct.unpack_from('=Q',raw,72)[0]
    status=struct.unpack_from('=i',raw,60)[0]
    require(returned & 8 and returned & 32 and supported & 8
            and not struct.unpack_from('=Q',initial,0)[0] & 8
            and struct.unpack_from('=Q',initial,0)[0] & 3 == 3
            and struct.unpack_from('=I',initial,16)[0]==child['pid']
            and struct.unpack_from('=I',initial,20)[0]==child['pid']
            and struct.unpack_from('=I',initial,24)[0]==child['parent']
            and struct.unpack_from('=I',initial,28)[0]==os.getuid()
            and struct.unpack_from('=I',initial,36)[0]==os.getuid()
            and value['returned_info']['returned_mask']==returned
            and value['returned_info']['supported_mask']==supported
            and value['returned_info']['exit_code_raw']==value['raw_wait_status']==status
            and os.WIFEXITED(status) and os.WEXITSTATUS(status)==0
            and value['normal_exit_zero'] is value['normal_exit'] is True
            and value['normal_exit_status']==0 and value['signal_termination'] is False
            and value['original_birth_absent'] is True and value['status']=='KERNEL_REAPED_NORMAL0'
            and value['anchor']['capture_end_monotonic_ns'] <= value['capture_begin_monotonic_ns']
            <= value['capture_end_monotonic_ns'] <= value['observed_monotonic_ns']
            <= sample['monotonic_s']*1e9,
            'No positive retained normal0 waitstatus/reap truth for original EVAL')
    return value


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


def verify_sample_kernel_exits(case, sample, read_pin):
    """Keep all state local; callback authenticates each unique pin THIS sample.

    No h.checked replacement or global/path cache exists. The selected original
    registry.read_pin callback retains its full SHA/full8 and immutable checks.
    Only anchors/selection are shared, privately, across this sample's receipts.
    """
    slots=list(sample.get('EVAL_kernel_exit_receipts',{}))
    shared={}
    result={}
    for slot in slots:
        require(slot in SLOTS and case['slot_eval'][slot] is True, 'Unknown kernel EVAL exit slot')
        result[slot]=_kernel_eval_exit_with_shared(case,sample,slot,read_pin=read_pin,shared=shared)
    return result


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


def selected_original_functions():
    """Compile ONLY four exact original stdlib functions; no module monkeypatch."""
    raw=checked_bytes(ORIGINAL_REGISTRY,2_000_000)
    nodes={n.name:n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}
    wanted=('require','identity','read_pin','kernel_eval_exit')
    require(all(name in nodes for name in wanted),'Exact original kernel collaborators missing')
    namespace=dict(os=os,Path=Path,stat=stat,hashlib=hashlib,json=json,struct=struct)
    for name in wanted:
        module=ast.Module(body=[nodes[name]],type_ignores=[])
        exec(compile(ast.fix_missing_locations(module),ORIGINAL_REGISTRY['path'],'exec'),namespace)
    return namespace['kernel_eval_exit'],namespace['read_pin']


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


def deny_unsafe(event,args):
    if event in ('os.system','subprocess.Popen','socket.connect','socket.bind'):
        raise ValueError('No process/network action in this component probe')
    if event=='open':
        path=args[0]
        if isinstance(path,(str,bytes,os.PathLike)):
            path=os.fsdecode(path)
            require(not path.startswith(('/proc/','/sys/','/dev/'))
                and not path.endswith(('.pt','.pth','.jsonl','.npy','.npz'))
                and '/models_dqn/'not in path,'No process/model/replay/raw-journal body reads')
    if event=='import':
        require(not str(args[0]).split('.')[0]in ('torch','numpy','socket','subprocess'), 'No GPU/model/network import')


def execute(selection_pin, own_pin):
    require(not any(name.split('.')[0]in ('torch','numpy') for name in sys.modules), 'No Torch/NumPy in metadata probe')
    resource.setrlimit(resource.RLIMIT_CPU,(30,30))
    resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30))
    sys.addaudithook(deny_unsafe)
    metadata_inputs=[]
    selected=read_metadata(selection_pin,262144,metadata_inputs)
    require(selected['schema']=='robotron-root-closed-C1-kernel-dependency-probe-v1'
        and selected['prototype']==own_pin and selected['original_registry']==ORIGINAL_REGISTRY,
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
    pins=selected['samples']
    require(type(pins)is list and 1<=len(pins)<=3 and len({p['path']for p in pins})==len(pins),
        'Select one to three distinct saved accepted C1 samples only')
    indices=[]
    for value in pins:
        matches=[index for index,entry in enumerate(outcome['samples'])if entry==value]
        require(len(matches)==1,'Sample is not an exact accepted outcome fullpin')
        indices.append(matches[0])
    require(indices==sorted(indices) and len(set(indices))==len(indices), 'Ordered distinct accepted subset required')
    baseline,original_read_pin=selected_original_functions()
    owner=read_metadata(outcome['owner'],2_000_000,metadata_inputs)
    results=[]
    for ordinal,(value,index)in enumerate(zip(pins,indices)):
        row=read_metadata(value,8<<20,metadata_inputs)
        require(row['index']==index and row['job']==life['worker_job']
            and row['nonce']==worker['nonce'] and row['owner']==owner,'Actual saved sample binding differs')
        sample=row['snapshot'];before=canonical(dict(case=case,sample=sample))
        old_read,old_calls=recorder(original_read_pin)
        new_read,new_calls=recorder(original_read_pin)
        original_kernel=type(baseline)(baseline.__code__,dict(baseline.__globals__,read_pin=old_read))
        def original():
            result={}
            for slot in sample.get('EVAL_kernel_exit_receipts',{}):
                require(slot in SLOTS and case['slot_eval'][slot]is True,'Unknown kernel EVAL exit slot')
                result[slot]=original_kernel(case,sample,slot)
            return result
        def prototype():
            return verify_sample_kernel_exits(case,sample,new_read)
        # Alternate order to disclose/reduce simple warm-cache order bias.
        order=('original','prototype')if ordinal%2==0 else('prototype','original')
        measured={}
        for name in order:
            measured[name]=measure(original if name=='original'else prototype)
            require(canonical(dict(case=case,sample=sample))==before,'Component mutated original case/sample')
        require(measured['original'][0]==measured['prototype'][0], 'Per-slot kernel validation outputs differ')
        require(dependency_set(old_calls)==dependency_set(new_calls),'Unique fullpin/as_json/immutable dependencies differ')
        slot_count=len(measured['original'][0])
        require(len(old_calls)==3*slot_count and len(new_calls)==(slot_count+2 if slot_count else 0),
                'Unexpected original or shared callback coverage')
        counts={}
        for name,calls in (('original',old_calls),('prototype',new_calls)):
            counts[name]=dict(callback_calls=len(calls),callback_bytes=sum(x['pin']['bytes']for x in calls),
                unique_dependencies=len(dependency_set(calls)))
        results.append(dict(sample=value,index=index,order=list(order),kernel_slots=len(measured['original'][0]),
            outputs_equal=True,unique_dependencies_equal=True,inputs_unchanged=True,
            original_outputs_sha256=hashlib.sha256(canonical(measured['original'][0])).hexdigest(),
            prototype_outputs_sha256=hashlib.sha256(canonical(measured['prototype'][0])).hexdigest(),
            original=measured['original'][1],prototype=measured['prototype'][1],counts=counts,
            original_dependency_set=[json.loads(x)for x in dependency_set(old_calls)],
            prototype_dependency_set=[json.loads(x)for x in dependency_set(new_calls)]))
    require(not any(name.split('.')[0]in ('torch','numpy')for name in sys.modules),'Unexpected model import')
    output=Path(selected['output'])
    require(output.parent==HERE and output.name.startswith('Root-') and output.resolve(strict=False)==output
        and not output.exists(),'Fresh direct-child Root-only probe output required')
    output.mkdir(mode=0o700)
    value=dict(schema='robotron-closed-C1-kernel-dependency-component-probe-result-v1',status='PASS',
        source=own_pin,selection=selection_pin,original_registry=ORIGINAL_REGISTRY,
        closed_C1_qualification=selected['closed_C1_qualification'],metadata_inputs=metadata_inputs,
        samples=results,resource_limits=dict(CPU_seconds=30,address_space_bytes=1<<30,external_wall_s=45),
        max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        component_only=True,full_health_replay_replaced=False,accepted_or_rejected_proof_requalified=False,
        dependency_set_scope='Original registry.read_pin callbacks only; outer helper hooks remain untouched',
        h_checked_replaced_or_monkeypatched=False,cross_sample_cache=False,
        current_or_future_study_source_selected=False,throughput_or_quality_credit=False,
        no_model_Torch_proc_API_or_raw_journal_reads=True)
    raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    with(output/'report.json').open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status='PASS',output=str(output/'report.json'),sha256=hashlib.sha256(raw).hexdigest(),
        samples=len(results),component_only=True)),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--selection-sha256')
    parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('SOURCE_ONLY_UNSELECTED_COMPONENT_PROBE')
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
