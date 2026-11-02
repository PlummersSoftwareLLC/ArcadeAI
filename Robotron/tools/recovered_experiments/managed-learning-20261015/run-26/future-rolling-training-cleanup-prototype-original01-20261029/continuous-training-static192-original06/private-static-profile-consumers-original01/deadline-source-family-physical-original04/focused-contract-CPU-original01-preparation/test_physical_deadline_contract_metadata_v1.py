"""Six actual private-contract metadata groups; synthetic collaborators, no live qualification.

Actual SHA-bound helper and contract functions are AST-compiled, never imported.
The independent raw reviewer, private parent/source/lease/boot collaborators are
explicitly mocked. No actual raw replay, lease, process, model or science runs.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

CONTRACT = '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-physical-original04/deadline_round_contract_v11.py'
CONTRACT_SHA = '7446897245886f03750bde7334772bac41bf4c96664aa26a14b73bc5575531f4'
HELPER = '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/physical_profile_contract_v3.py'
HELPER_SHA = '16f842452a56d5a2ae9f3c01b6cd4581623d2463c333ed785e8b8ea53a0909e8'


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(s.st_mode&511),uid=s.st_uid,nlink=s.st_nlink)

def pin(path):
    raw=path.read_bytes();return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(path.stat()))

def require(value,message):
    if not value:raise ValueError(message)

def selected(path,digest):
    raw=Path(path).read_bytes();require(hashlib.sha256(raw).hexdigest()==digest,'Exact focused contract source')
    return ast.parse(raw)

class SyntheticMetadata:
    def __init__(self,directory):
        self.root=Path(directory);self.sequence=0;self.checked_mock_paths={};self.verified=False
        ns=dict(json=json,hashlib=hashlib)
        body=[n for n in selected(HELPER,HELPER_SHA).body if isinstance(n,ast.FunctionDef)]
        exec(compile(ast.Module(body=body,type_ignores=[]),HELPER,'exec'),ns)
        self.helper=SimpleNamespace(**ns)
        self.h=SimpleNamespace(checked=self.checked)
        self.source_authority=self.put(dict(SYNTHETIC=True,source='unchanged-main'))
        self.inputs={str(self.root/('held-%03d'%i)):dict(sha256=('%064x'%i),identity=dict(SYNTHETIC=True))for i in range(247)}
        self.parent=self.put(dict(schema='robotron-round-main-health-case-v1',inputs=copy.deepcopy(self.inputs)))
        self.roles={str(i):i<37 for i in range(192)}
        originals={str(i):dict(eval_only=i<37,incarnation=1,original_child=dict(pid=2000+i,birth=9000+i),
            spawn_intent=dict(SYNTHETIC=i),original_child_receipt=dict(SYNTHETIC=i),connection_binding=dict(SYNTHETIC=i))for i in range(192)}
        process=dict(pid=1000,starttime_ticks=8000,parent_pid=1,cgroup='/SYNTHETIC',command=['SYNTHETIC'],
            environment={},affinity=[0],uids=[os.getuid()]*4,executable=dict(path='SYNTHETIC'))
        self.case=dict(schema='robotron-continuous-physical-original192-health-case-v2',inputs=copy.deepcopy(self.inputs),
            slot_eval=self.roles,continuous=dict(epoch='SYNTHETIC-EPOCH',source_authority=self.source_authority,
                original_membership=dict(SYNTHETIC='ORIGINAL192'),original_slots=originals),
            recipe=dict(lr=3.125e-6,epsilon=.02,expert_ratio=0.),actor_environment=dict(SYNTHETIC='ENV'),
            actor_command=['SYNTHETIC-MAME'],actor_executable=dict(path='SYNTHETIC-MAME'),actor_affinity=[0],experiment='SYNTHETIC',
            owners={r:dict(unit='SYNTHETIC-'+r,invocation='1'*32,process=copy.deepcopy(process))for r in('trainer','fleet')},
            exposure={r:dict(process_id=1000,instance_monotonic_ns=100,epoch=1,epoch_reason='SYNTHETIC')for r in('optimizer','replay')})
        self.set_inventory()
        self.sample=dict(schema='robotron-continuous-physical-original192-main-health-snapshot-v2',
            status=dict(schema='robotron-continuous-training-static192-snapshot-v2',mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',
                epoch=self.case['continuous']['epoch'],original_membership=self.case['continuous']['original_membership'],slots={}),
            actors={s:dict(SYNTHETIC=True)for s in self.roles},EVAL_journal_evidence={})
        for slot,r in originals.items():
            raw=json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
            self.sample['status']['slots'][slot]=dict(original_slot_sha256=hashlib.sha256(raw).hexdigest(),
                original_pid=r['original_child']['pid'],original_birth=r['original_child']['birth'],
                eval_only=self.roles[slot],incarnation=1,state='quarantined',natural_result=None)
        self.sample['status']['errors']=['SYNTHETIC old publisher token label; not physical authority']
        tree=selected(CONTRACT,CONTRACT_SHA)
        class BootPath:
            def read_text(self):return 'SYNTHETIC-CURRENT-BOOT'
        def paths(value):return BootPath()if str(value)=='/proc/sys/kernel/random/boot_id'else Path(value)
        base=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
        ns=dict(ast=ast,hashlib=hashlib,json=json,os=os,Path=paths,ROOT=base.parents[2],BASE=base)
        names={'LEGACY_JOB','LEGACY_JOB_SHA','HEALTH_SHAS','PRIVATE_FIELDS'}
        body=[n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id in names for t in n.targets)]
        body += [n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in('require','validate_static','validate_launch')]
        exec(compile(ast.Module(body=body,type_ignores=[]),CONTRACT,'exec'),ns)
        self.contract=SimpleNamespace(**ns);self.contract_ns=ns
        self.legacy={key:dict(SYNTHETIC=key)for key in ns['PRIVATE_FIELDS']}
        lease=dict(path='/SYNTHETIC-PERMANENT-COORDINATOR',bytes=0,sha256='0'*64,identity=dict(mode='0o600'))
        self.legacy['lease']=dict(lease,identity=dict(mode='0o600',inode=1))
        self.job=copy.deepcopy(self.legacy);self.job['lease']=lease
        self.observer={key:dict(path=str(self.root/('synthetic-'+key+'.py')),sha256=digest,bytes=0,identity={})for key,digest in ns['HEALTH_SHAS'].items()}
        self.observer['interpreter']=dict(path='SYNTHETIC-INTERPRETER',sha256='2'*64,bytes=0,identity={})
        self.binding_pin=self.put(self.case)
        self.job.update(main_binding=self.binding_pin,observer_sources=self.observer,runtime=dict(path='SYNTHETIC-RUNTIME',sha256='3'*64))
        self.protocol=dict(schema='robotron-native-continuous-physical-original192-main-health-proof2s-protocol-v2',
            case=self.binding_pin,raw_API_required=True,close_requires_final_sample=True,hot_max_gap_s=2.,initial_samples=100,
            raw_queue_protocol='pending-byte-digest-v2',volatile_live_tmpfs=True,source_bound_retired_API_projection=True,
            source_bound_original192_physical_bootstrap=True,source_bound_physical_original192_partition=True)
        self.recovery=self.put(dict(schema='robotron-post-outage-private-coordinator-restoration-v1',
            status='RESTORED_NEW_BOOT_COORDINATOR',absent_pre_outage_lease=self.legacy['lease'],restored_lease=lease,
            created_exclusively_without_replacing_existing_file=True,exclusive_lock_acquisition_and_release_verified=True,
            current_boot_id='SYNTHETIC-CURRENT-BOOT'))
        self.family=dict(schema='robotron-deadline32-physical192-proof2s-source-family-v2',runtime=self.job['runtime'],
            deadline_components=self.job['components'],main_observer=self.observer,current_main_binding=self.binding_pin,
            reviewer=dict(path='SYNTHETIC-PRIVATE-REVIEWER',sha256='4'*64),
            main_health_finalizer=dict(path='SYNTHETIC-FINALIZER',sha256='64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee'),
            private_parent_job=dict(path=str(ns['LEGACY_JOB']),sha256=ns['LEGACY_JOB_SHA']),lease_recovery_authority=self.recovery,
            round_observer_reviewer=dict(path='SYNTHETIC-REVIEWER',sha256='49517cda74226f60f12297c5a106a758d76a3e0e4682a0a2c9058124c4ad433f'),native_launch_qualified=True)
        self.parent_file=self.put(self.legacy)
        self.checked_mock_paths[str(ns['LEGACY_JOB'])]=Path(self.parent_file['path'])
        ns['source']=lambda path,sha: json.dumps(self.legacy).encode()
        ns['validate_derivation']=lambda *a:dict(SYNTHETIC_SOURCE_DERIVATION_COLLABORATOR=True)
        worker=self.put(dict(case=self.binding_pin));sample=self.put(dict(snapshot=self.sample))
        outcome=self.put(dict(samples=[sample]));self.lifecycle=self.put(dict(worker_job=worker,outcome=outcome))
        self.family['main_domain_hot_review']=self.put(dict(lifecycle=self.lifecycle))
        self.proof=dict(proof_gap_contract='robotron-main-proof-gap-2s-v1',verified_maximum_gap_s=2.,
            accepted_evidence_and_projection_gaps_verified=True,main_health_profile='PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE',
            source_bound_original192_physical_bootstrap_verified=True,TRAIN155_original_physical_and_current_TCP_verified=True,
            EVAL37_original_connection_and_strict_retirement_evidence_verified=True,
            EVAL_closed_slots_have_positive_normal0_reap_and_cleanup_verified=True,original_sources=self.observer)
        def verify(lifecycle,h):
            require(lifecycle==self.lifecycle,'Synthetic verifier lifecycle differs');self.verified=True
            return copy.deepcopy(self.proof)
        ns['load']=lambda name,path:SimpleNamespace(verify=verify)
        def coverage(binding,sample):
            require(self.verified,'Coverage must follow selected verifier callback')
            return self.helper.sample_domain(binding,sample)
        ns['static_profile']=lambda:SimpleNamespace(validate_inventory=self.helper.validate_inventory,
            same_domain=self.helper.same_domain,sample_domain=coverage)
        self.context=dict(family=self.family,main_binding=self.case)
    def put(self,value):
        self.sequence+=1;p=self.root/('%04d.json'%self.sequence)
        with p.open('x')as f:
            json.dump(value,f,separators=(',',':'),allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        return pin(p)
    def checked(self,value):
        # Explicit synthetic source/lease/private-parent collaborator; no real
        # source-family qualification or coordinator lock is being asserted.
        path=value['path']
        if path in self.checked_mock_paths:return self.checked_mock_paths[path]
        if path.startswith('/SYNTHETIC')or path.startswith('SYNTHETIC')or '/synthetic-'in path:return self.root
        p=Path(path);require(pin(p)==value,'Synthetic immutable metadata changed');return p
    def set_inventory(self):
        current=self.case['inputs'];old=self.inputs
        self.case['input_inventory_authority']=self.put(dict(schema='robotron-root-continuous-static192-input-inventory-v1',
            status='ROOT_SELECTED_EXACT_HELD_INPUTS',mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',source_authority=self.source_authority,
            inputs=current,input_count=len(current),parent_case=self.parent,
            replacements={p:dict(before=old[p],after=current[p])for p in old if p in current and old[p]!=current[p]},
            added_inputs={p:current[p]for p in set(current)-set(old)}))

class Tests(unittest.TestCase):
    def test_actual_new_protocol_and_exact_eight_source_static_contract(self):
        with tempfile.TemporaryDirectory()as root:
            h=SyntheticMetadata(root)
            self.assertTrue(h.contract.validate_static(h.job,h.protocol,h.family,h.h)['SYNTHETIC_SOURCE_DERIVATION_COLLABORATOR'])
    def test_actual_static_contract_rejects_old_schema_flags_sources_and_bounds(self):
        with tempfile.TemporaryDirectory()as root:
            h=SyntheticMetadata(root)
            for damage in('schema','physical_bootstrap','partition','gap','initial','source','reviewer','family'):
                p,f,j=copy.deepcopy(h.protocol),copy.deepcopy(h.family),copy.deepcopy(h.job)
                if damage=='schema':p['schema']='robotron-native-continuous-static192-main-health-proof2s-protocol-v1'
                elif damage=='physical_bootstrap':p['source_bound_original192_physical_bootstrap']=False
                elif damage=='partition':p['source_bound_physical_original192_partition']=False
                elif damage=='gap':p['hot_max_gap_s']=2.001
                elif damage=='initial':p['initial_samples']=99
                elif damage=='source':f['main_observer']['worker']['sha256']='0'*64;j['observer_sources']=f['main_observer']
                elif damage=='reviewer':f['round_observer_reviewer']['sha256']='0'*64
                else:f['schema']='robotron-deadline32-static192-proof2s-source-family-v1'
                with self.subTest(damage=damage),self.assertRaises(ValueError):h.contract.validate_static(j,p,f,h.h)
    def test_actual_launch_new_flags_and_environment_precede_coverage(self):
        with tempfile.TemporaryDirectory()as root:
            h=SyntheticMetadata(root)
            with patch.dict(os.environ,dict(ROBOTRON_CONTINUOUS_TRAINING_MODE='0',ROBOTRON_ROLLING_TRAINING_CLEANUP='0',ROBOTRON_CONTINUOUS_STARTUP_HOLD='0')):
                self.assertEqual(h.contract.validate_launch(h.job,h.context,h.h),h.proof)
                for key in('source_bound_original192_physical_bootstrap_verified','TRAIN155_original_physical_and_current_TCP_verified',
                    'EVAL37_original_connection_and_strict_retirement_evidence_verified','EVAL_closed_slots_have_positive_normal0_reap_and_cleanup_verified'):
                    h.proof[key]=False
                    with self.subTest(flag=key),self.assertRaises(ValueError):h.contract.validate_launch(h.job,h.context,h.h)
                    h.proof[key]=True
                for key in('ROBOTRON_CONTINUOUS_TRAINING_MODE','ROBOTRON_ROLLING_TRAINING_CLEANUP','ROBOTRON_CONTINUOUS_STARTUP_HOLD'):
                    with patch.dict(os.environ,{key:'1'}),self.subTest(mode=key),self.assertRaises(ValueError):h.contract.validate_launch(h.job,h.context,h.h)
    def test_actual_inventory_retains_247_and_exact_delta_count_and_schema(self):
        with tempfile.TemporaryDirectory()as root:
            h=SyntheticMetadata(root);h.helper.validate_inventory(h.case,h.h)
            h.case['inputs'][str(h.root/'added')]=dict(sha256='a'*64,identity=dict(SYNTHETIC=True));h.set_inventory()
            self.assertEqual(h.helper.validate_inventory(h.case,h.h)['input_count'],248)
            for damage in('schema','drop','count','delta','self'):
                c=copy.deepcopy(h.case);a=json.loads(Path(c['input_inventory_authority']['path']).read_bytes())
                if damage=='schema':c['schema']='robotron-continuous-static192-health-case-v1'
                elif damage=='drop':c['inputs'].pop(next(iter(h.inputs)));a['inputs']=c['inputs'];a['input_count']=len(c['inputs'])
                elif damage=='count':a['input_count']+=1
                elif damage=='delta':a['added_inputs']={}
                else:c['inputs'][c['input_inventory_authority']['path']]={};a['inputs']=c['inputs'];a['input_count']=len(c['inputs'])
                c['input_inventory_authority']=h.put(a)
                with self.subTest(damage=damage),self.assertRaises(ValueError):h.helper.validate_inventory(c,h.h)
    def test_actual_same_domain_rejects_recipe_owner_epoch_and_source_drift(self):
        with tempfile.TemporaryDirectory()as root:
            h=SyntheticMetadata(root);h.helper.same_domain(h.case,copy.deepcopy(h.case))
            for damage in('recipe','owner','epoch','source','role'):
                c=copy.deepcopy(h.case)
                if damage=='recipe':c['recipe']['lr']*=2
                elif damage=='owner':c['owners']['trainer']['process']['starttime_ticks']+=1
                elif damage=='epoch':c['exposure']['optimizer']['epoch']+=1
                elif damage=='source':c['continuous']['source_authority']['sha256']='0'*64
                else:c['slot_eval']['40']=True
                with self.subTest(damage=damage),self.assertRaises(ValueError):h.helper.same_domain(h.case,c)
    def test_actual_post_replay_domain_uses_physical_membership_and_independent_EVAL(self):
        with tempfile.TemporaryDirectory()as root:
            h=SyntheticMetadata(root);h.helper.sample_domain(h.case,h.sample)
            s=copy.deepcopy(h.sample);s['actors'].pop('0');s['EVAL_journal_evidence']['0']=dict(SYNTHETIC_ALREADY_VALIDATED=True)
            h.helper.sample_domain(h.case,s)  # no closed/normal0 claim, no publisher-natural dependency
            for damage in('TRAIN','EVAL','digest','pid','schema','epoch'):
                bad=copy.deepcopy(s)
                if damage=='TRAIN':bad['actors'].pop('40')
                elif damage=='EVAL':bad['EVAL_journal_evidence']={}
                elif damage=='digest':bad['status']['slots']['40']['original_slot_sha256']='0'*64
                elif damage=='pid':bad['status']['slots']['40']['original_pid']+=1
                elif damage=='schema':bad['schema']='robotron-continuous-static192-main-health-snapshot-v1'
                else:bad['status']['epoch']='foreign'
                with self.subTest(damage=damage),self.assertRaises(ValueError):h.helper.sample_domain(h.case,bad)

if __name__=='__main__':unittest.main()
