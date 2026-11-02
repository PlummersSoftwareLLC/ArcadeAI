"""One bounded Root-only negative check of actual closed05 metadata helpers.

Default inert. Never reruns the full positive validator, loads a tensor, probes
runtime, or changes source/Main/canonical/ST/PUBLIC. Only a fresh report is made.
"""
import argparse
import copy
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

VALIDATOR={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/fresh-original05-typed-Adam-cap8-profile-preparation-original05/verify_closed_original05_typed_capture_v1.py', 'sha256': '111eb202f73c3457ccf589576c1c97de01a5adb18d55419108285d5f1ed02507', 'bytes': 26611, 'identity': {'device': 2304, 'inode': 85459427, 'bytes': 26611, 'mtime_ns': 1793333815369822958, 'ctime_ns': 1793334151617301345, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
HELPERS={'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
POSITIVE_REPORT={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/fresh-original05-typed-Adam-cap8-profile-preparation-original05/Root-actual-closed-original05-metadata-verification-original01/Root-actual-closed-original05-metadata-verification-report.json', 'sha256': 'fb3139fd9c3f8dc50036de9d1e34115bf9eaef7f39e6f5c9879dfb08bf2de3f1', 'bytes': 56483, 'identity': {'device': 2304, 'inode': 85459449, 'bytes': 56483, 'mtime_ns': 1793334504238083520, 'ctime_ns': 1793334504238083520, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}


def require(value,reason):
    if not value:raise ValueError(reason)


def load(name,pin):
    path=Path(pin['path']);raw=path.read_bytes()
    require(len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],
            'Exact frozen source bytes required before import')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,
            'Exact selected negative fixture required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and sys.dont_write_bytecode is True,
            'Explicit CPU-only -B invocation required')
    require('torch'not in sys.modules,'Torch must not precede this metadata check')
    output=Path(args.output).absolute()
    require(output==output.resolve()and output.parent==Path(__file__).resolve().parent
            and output.name.startswith('Root-negative-helper-check-')and not output.exists(),
            'One fresh private future05 report directory required')
    class DenyTorch(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname=='torch'or fullname.startswith('torch.'):
                raise RuntimeError('Torch import is prohibited in metadata-only helper checks')
    sys.meta_path.insert(0,DenyTorch())
    reads=set()
    def audit(event,values):
        if event=='open'and isinstance(values[0],(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(values[0])).absolute()
            require(path.suffix not in('.pt','.jsonl')and not path.is_relative_to('/proc')
                    and not path.is_relative_to('/sys'),'Tensor/raw-journal/runtime reads are prohibited')
            mode,flags=values[1],values[2]
            writing=(isinstance(mode,str)and any(k in mode for k in 'wax+'))or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            require(not writing or path==output/'report.json','Only the new private report may be written')
            if not writing:
                if path.is_relative_to('/home/dave/source/repos/ArcadeAI/Robotron'):
                    require(path.stat().st_size<=2<<20,'Held source/metadata read exceeds2MiB')
                reads.add(str(path))
        if event in('subprocess.Popen','os.system','os.exec','os.kill','os.killpg','socket.connect','socket.bind'):
            raise RuntimeError('Runtime/process/network actions are prohibited')
        if event in('os.remove','os.rename','os.rmdir'):
            raise RuntimeError('No deletion or replacement is allowed')
        if event=='os.mkdir':require(Path(values[0]).absolute()==output,'Only the new report directory may be created')
        if event=='os.chmod'and isinstance(values[0],(str,bytes,os.PathLike)):
            require(Path(os.fsdecode(values[0])).absolute()==output/'report.json','Only report permissions may change')
    sys.addaudithook(audit)
    h=load('_closed05_negative_full8_helpers',HELPERS);h.checked(HELPERS)
    validator=load('_closed05_negative_actual_validator',VALIDATOR);h.checked(VALIDATOR)
    positive=validator.read(POSITIVE_REPORT,h)
    require(positive['status']=='PASS'and positive['exit']==0
            and positive['source_sha256']==VALIDATOR['sha256']and positive['helper_sha256']==HELPERS['sha256']
            and positive['torch_imported']is positive['model_body_loaded']is positive['runtime_probe_performed']is False
            and positive['canonical_or_PUBLIC_written']is False,
            'Existing exact actual positive closed-capture report required')
    require(positive['actual_closed_capture']['result']['endpoint']['sha256']==validator.CANDIDATE
            and positive['actual_closed_capture']['all_original_CPU_and_observer_closures_verified']is True
            and positive['actual_closed_capture']['classification_transfer_to_other_endpoint']is False,
            'Positive report must concern only this exact closed original05 endpoint')
    cpu=validator.read(validator.FIXED['CPU'],h);entry=validator.read(validator.FIXED['typed_entry_CPU'],h)
    plan=validator.read(validator.FIXED['plan'],h);anchor=validator.read(validator.FIXED['anchor'],h)
    threshold=validator.read(validator.FIXED['threshold'],h);result=validator.read(validator.FIXED['result'],h)
    owner=validator.read(validator.FIXED['CPU_owner'],h);terminal=validator.read(validator.FIXED['CPU_terminal'],h)
    watcher=validator.load('watcher',h);observer=validator.load('library',h)
    require(validator.FIXED['watcher']['sha256']=='98ffb7eee78101b91ea29e9252b9368b011bed2befa75504fa14c240ded945a5',
            'Exact actual typed-progress helper required')
    baseline=copy.deepcopy((cpu,entry,plan,anchor,threshold,result['added']))
    results=[];started=time.monotonic()
    def rejected(name,call):
        try:call()
        except (ValueError,AssertionError)as error:
            results.append(dict(case=name,status='EXPECTED_REJECTION',exception_type=type(error).__name__,message=str(error)[:1000]))
        except Exception as error:
            results.append(dict(case=name,status='UNEXPECTED_EXCEPTION',exception_type=type(error).__name__,message=str(error)[:1000]))
        else:results.append(dict(case=name,status='UNEXPECTED_ACCEPTANCE'))
    def progress(name,damage):
        values=copy.deepcopy(baseline);damage(*values)
        require(values!=baseline,'Negative case did not actually change its copied inputs: '+name)
        rejected(name,lambda:watcher.endpoint_progress_proof(*values,observer))
    progress('raw_Adam_parameter_count_80',lambda v,e,p,a,t,d:v['Adam_raw_step_proof'].__setitem__('parameters',80))
    progress('raw_Adam_float64_at_same_2p24_value',lambda v,e,p,a,t,d:v['Adam_raw_step_proof'].__setitem__('raw_dtype_counts',{'torch.float64':81}))
    progress('raw_Adam_below_exact_2p24',lambda v,e,p,a,t,d:v['Adam_raw_step_proof'].__setitem__('raw_step_min',16777215.0))
    progress('insufficient_actual_applied_despite_high_integer_clocks',lambda v,e,p,a,t,d:t['host_pipeline']['learning_exposure']['optimizer']['total'].__setitem__('applied',a['host_pipeline']['learning_exposure']['optimizer']['total']['applied']+p['thresholds']['applied_updates']-1))
    progress('insufficient_actual_replay_despite_high_integer_clocks',lambda v,e,p,a,t,d:t['host_pipeline']['learning_exposure']['replay'].__setitem__('accepted_total',a['host_pipeline']['learning_exposure']['replay']['accepted_total']+p['thresholds']['replay_inserts']-1))
    def integer_dose(field,factor):
        def damage(v,e,p,a,t,d):
            amount=t['host_pipeline']['learning_exposure']['optimizer']['total']['applied']-a['host_pipeline']['learning_exposure']['optimizer']['total']['applied']
            v['clocks'][field]=a[field]+factor*amount-1
            t[field]=min(t[field],v['clocks'][field])
        return damage
    progress('insufficient_training_step_integer_dose',integer_dose('training_steps',1))
    progress('insufficient_optimized_sample_integer_dose',integer_dose('optimized_samples',4096))
    progress('foreign_verifier_source',lambda v,e,p,a,t,d:v['verification_source'].__setitem__('path',v['verification_source']['path']+'.foreign'))
    progress('optimizer_epoch_drift',lambda v,e,p,a,t,d:t['host_pipeline']['learning_exposure']['optimizer'].__setitem__('epoch',t['host_pipeline']['learning_exposure']['optimizer']['epoch']+1))
    resources=dict(Type='simple',Restart='no',NRestarts='0',CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='3min')
    rejected('wrong_original_owner_PID',lambda:validator.normal_terminal(copy.deepcopy(terminal),copy.deepcopy(owner['actual_properties']),owner['pid']+1,owner['invocation_id'],resources))
    bad=copy.deepcopy(terminal);bad['ExecMainStatus']='1'
    rejected('nonzero_original_terminal',lambda:validator.normal_terminal(bad,copy.deepcopy(owner['actual_properties']),owner['pid'],owner['invocation_id'],resources))
    badpin=copy.deepcopy(validator.FIXED['CPU']);badpin['sha256']='0'*64
    rejected('held_metadata_SHA_drift',lambda:validator.checked_bytes(badpin,h))
    badpin=copy.deepcopy(validator.FIXED['CPU']);badpin['identity']['inode']+=1
    rejected('held_metadata_full8_inode_drift',lambda:validator.checked_bytes(badpin,h))
    require((cpu,entry,plan,anchor,threshold,result['added'])==baseline,'Actual recorded input dictionaries were mutated')
    require(len(results)==13,'Exact finite negative-case count required')
    require('torch'not in sys.modules,'No Torch import allowed')
    passed=all(row['status']=='EXPECTED_REJECTION'for row in results)
    report=dict(schema='robotron-closed-original05-negative-helper-check-v1',status='PASS'if passed else'FAIL',
        source=h.pin(Path(__file__).resolve()),validator=VALIDATOR,actual_progress_helper=validator.FIXED['watcher'],
        existing_positive_report=POSITIVE_REPORT,positive_full_validator_rerun=False,
        negative_cases=len(results),expected_rejections=sum(r['status']=='EXPECTED_REJECTION'for r in results),cases=results,
        actual_recorded_inputs_unchanged=True,all_negative_changes_in_memory_only=True,
        elapsed_s=time.monotonic()-started,started_unix_s=time.time()-(time.monotonic()-started),
        torch_imported=False,model_body_or_raw_journal_read=False,runtime_probe_performed=False,
        canonical_ST_or_PUBLIC_written=False,only_new_report_written=True,
        full_game_quality_or_improvement_qualified=False,opened_paths=sorted(reads))
    output.mkdir(mode=0o700)
    raw=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
    target=output/'report.json'
    with target.open('xb')as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(output,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(status=report['status'],expected_rejections=report['expected_rejections'],negative_cases=13,report=h.pin(target))),flush=True)
    return 0 if passed else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--output',type=Path);p.add_argument('--source-sha256');args=p.parse_args()
    if not args.execute:print('SOURCE_ONLY_INERT_NO_READS_OR_ACTIONS');return 0
    return execute(args)


if __name__=='__main__':raise SystemExit(main())
