"""Six source-only fullgame/static8 groups for a future Root-owned CPU scope.

No candidate module is imported. Selected SHA-bound functions are compiled from
their actual AST only when Root executes this fixture. Context helpers, policy
receipts, boot ID, health replay and all physical owners are synthetic. These
groups cannot establish actual engineering, serialized-job or quality readiness.
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

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE=ROOT/'logs/managed-learning-20261015/run-26'
D=BASE/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06'
S=D/'private-static-profile-consumers-original01'
F=S/'fullgame-source-family-original02'
H=D/'health-consumer-original01'
OLD=BASE/'post-recovery-evaluation-isolation-original01-20261027/future-proof2s-fullgame-confirmation-original01-preparation/source-family-original01'
SELECTED={
    'fullgame_round_contract_v7.py':'2bbc7296e8c0814d8f59d022ae39280d12e214cf514a49e5b7d38922a9eb8616',
    'fullgame_round_observer_v6.py':'15479a570a2550b80e223d536149682440dca5e8a59cc0e3327dd6b0df70eae3',
    'fullgame_round_observer_client_v8.py':'7deabce1af2b6d2fdc65d715e7acb8a38f1318f2a9d6a1c024e78ef81012f685',
    'review_fullgame_round_observer_v7.py':'168cb0ff523c9ab48c8357a6f35ea2b85c2ead8d7c5bed78e270fe082b3e44df',
    'check_fullgame_four_cpu_v7.py':'dd1a75a3d5dc16fc92a28cf854fb5aa2549fbdc36f9708da566d3922421b8015',
}
SHARED_SHA='5260662e651c6f26cde42bb04cde913dd51015658d071499b6966e661e6a451b'


def selected(path, digest):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('Exact fixture source changed: '+str(path))
    return raw


def functions(path,digest,names,extra=None):
    """Actual top-level functions only; no candidate imports/module execution."""
    tree=ast.parse(selected(path,digest))
    found=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in found}!=set(names):
        raise ValueError('Actual requested functions missing')
    ns=dict(__file__=str(path),__name__='_synthetic_static_fullgame_AST',ast=ast,
        hashlib=hashlib,json=json,os=os,Path=Path,sys=SimpleNamespace(modules={}))
    if extra:ns.update(extra)
    exec(compile(ast.fix_missing_locations(ast.Module(body=found,type_ignores=[])),str(path),'exec'),ns)
    return ns


def synthetic_pin(path):
    """Descriptor-shaped synthetic value; never asserts source/physical identity."""
    text=str(path)
    return dict(path=text,sha256=hashlib.sha256(text.encode()).hexdigest(),bytes=0,
        identity=dict(mode='0o444'))


class TempEvidence:
    """Real exclusive immutable temporary JSON with exact hash/stat readback."""
    def __init__(self,root):self.root=Path(root);self.serial=0
    def pin(self,path):
        path=Path(path);s=path.stat();raw=path.read_bytes()
        return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
            identity=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,
                mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),
                uid=s.st_uid,nlink=s.st_nlink))
    def checked(self,value):
        if self.pin(value['path'])!=value:raise ValueError('Temporary evidence changed')
        return Path(value['path'])
    def put(self,value):
        self.serial+=1;path=self.root/('synthetic-'+str(self.serial)+'.json')
        with path.open('x')as out:
            out.write(json.dumps(value,sort_keys=True,allow_nan=False)+'\n')
            out.flush();os.fchmod(out.fileno(),0o444);os.fsync(out.fileno())
        return self.pin(path)


class Tests(unittest.TestCase):
    def shared(self):
        return functions(S/'static_profile_contract_v2.py',SHARED_SHA,
            ('require','read','validate_inventory','same_domain','sample_domain'))

    def contract(self,*names):
        return functions(F/'fullgame_round_contract_v7.py',SELECTED['fullgame_round_contract_v7.py'],
            ('require',*names),dict(HERE=F,STATIC_PROFILE=S/'static_profile_contract_v2.py',ROOT=ROOT,
            TEMPLATE=Path('/SYNTHETIC-original-private-template'),PRIVATE_FIELDS=('schema','actor_slots'),
            ORDER=('R1','C1','R2','C2')))

    def test_original_private_predicates_and_four_exact_job_guard_preserved(self):
        # Original full four-job guard is retained, not rerun with invented jobs.
        self.assertEqual(selected(F/'check_fullgame_four_cpu_v7.py',SELECTED['check_fullgame_four_cpu_v7.py']),
            (OLD/'check_fullgame_four_cpu_v7.py').read_bytes())
        ns=self.contract('validate_derivation')
        original=BASE/'future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01'
        ns.update(NATIVE=original/'run_quality32_quota64_selected_original01_v2.py',
            NATIVE_SHA='9ecf99ba66b76b8bd31de06e894124e495d3fedba86ba5a1c36db628ccb95f83',
            REVIEW=original/'read_quality32_quota64_selected_original01_v2.py',
            REVIEW_SHA='e2231b41f69671ebb0d80bf52a3aeb20e273486fc58934c33ecef61eec185d2c')
        proof=ns['validate_derivation'](F/'run_fullgame_rounds_v7.py',F/'review_fullgame_rounds_v7.py')
        self.assertTrue(proof['private_count_life_game_tail_score_cleanup_and_timeout_predicates_preserved'])
        self.assertFalse(proof['scientific_launch_qualified'])

    def test_fullgame_bounds_and_worker_exact_static8_prefix(self):
        worker=F/'fullgame_round_observer_v6.py'
        tree=ast.parse(selected(worker,SELECTED[worker.name]));run=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='run')
        prefix=copy.deepcopy(run);prefix.name='prefix';prefix.body=prefix.body[:3]
        self.assertTrue(all(isinstance(n,ast.Expr)and isinstance(n.value,ast.Call)and isinstance(n.value.func,ast.Name)and n.value.func.id=='require'for n in prefix.body))
        ns=self.contract();ns.update(SCHEMA='robotron-fullgame-continuous-static192-observer-proof2s-job-v1',pin=synthetic_pin)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[prefix],type_ignores=[])),str(worker),'exec'),ns)
        job=dict(schema=ns['SCHEMA'],attempt=1,no_retry=True,interval_s=.2,initial_samples=100,maximum_gap_s=2.0,
            work_s=22200,runtime_s=22260,source_bound_retired_API_projection=True,
            source_bound_completed_original192_bootstrap=True,source_bound_static_original192_partition=True,
            sources={k:synthetic_pin(p)for k,p in dict(client=F/'fullgame_round_observer_client_v8.py',worker=worker,
                health=H/'continuous_static192_transport_v1.py',health_base=H/'continuous_static192_health_v1.py',
                registry=H/'continuous_static192_registry_v1.py',durability=ROOT/'tools/post_recovery_evaluation/buffered_raw_writer_v2.py',
                control=ROOT/'tools/post_recovery_evaluation/volatile_live_control_v1.py',interpreter=Path('/usr/bin/python3.12')).items()})
        ns['prefix'](job,{})
        for fault in ('old_deadline_schema','work','runtime','gap','initial','interval','extra_launcher','missing_registry','wrong_registry','opt_in'):
            value=copy.deepcopy(job)
            if fault=='old_deadline_schema':value['schema']='robotron-continuous-static192-observer-proof2s-job-v1'
            elif fault in ('work','runtime'):value[fault+'_s']=4200 if fault=='work' else 4260
            elif fault=='gap':value['maximum_gap_s']=.5
            elif fault=='initial':value['initial_samples']=99
            elif fault=='interval':value['interval_s']=1.0
            elif fault=='extra_launcher':value['sources']['launcher_census']=synthetic_pin('/SYNTHETIC-old-launcher')
            elif fault=='missing_registry':del value['sources']['registry']
            elif fault=='wrong_registry':value['sources']['registry']['sha256']='f'*64
            else:value['source_bound_static_original192_partition']=False
            with self.subTest(fault=fault),self.assertRaises(ValueError):ns['prefix'](value,{})
        # Fullgame3 are finite derivatives of the exact current static observer3.
        mappings={
            'fullgame_round_observer_v6.py':('observe_continuous_static192_v1.py',[
                ('robotron-continuous-static192-observer-proof2s-job-v1','robotron-fullgame-continuous-static192-observer-proof2s-job-v1'),
                ("job['work_s'] == 4200 and job['runtime_s'] == 4260","job['work_s'] == 22200 and job['runtime_s'] == 22260"),
                ('Exact deadline observer bounds required','Exact complete-game observer bounds required')]),
            'fullgame_round_observer_client_v8.py':('continuous_static192_observer_client_v1.py',[
                ('robotron-native-continuous-static192-main-health-proof2s-protocol-v1','robotron-native-fullgame-continuous-static192-main-health-proof2s-protocol-v1'),
                ('work_s=4200, runtime_s=4260','work_s=22200, runtime_s=22260'),('RuntimeMaxSec=4260','RuntimeMaxSec=22260'),
                ("RuntimeMaxUSec='1h 11min'","RuntimeMaxUSec='6h 11min'"),('limit=64 << 20','limit=128 << 20')]),
            'review_fullgame_round_observer_v7.py':('review_continuous_static192_observer_v1.py',[
                ('robotron-continuous-static192-observer-proof2s-job-v1','robotron-fullgame-continuous-static192-observer-proof2s-job-v1'),
                ("job['work_s'] == 4200 and job['runtime_s'] == 4260","job['work_s'] == 22200 and job['runtime_s'] == 22260"),
                ("lifecycle['native_started_monotonic_s'] + 4200","lifecycle['native_started_monotonic_s'] + 22200"),
                ("RuntimeMaxUSec='1h 11min'","RuntimeMaxUSec='6h 11min'"),('ended-started <= 4260','ended-started <= 22260'),
                ('<= 22000','<= 112000'),('64 << 20','128 << 20')]),
        }
        for name,(parent,replacements)in mappings.items():
            expected=(H/parent).read_text()
            for old,new in replacements:
                self.assertIn(old,expected);expected=expected.replace(old,new)
            self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse(selected(F/name,SELECTED[name]))))

    def test_actual_context_static_schema_eight_sources_and_validation_order(self):
        ns=self.contract('context');objects={};events=[]
        h=SimpleNamespace(pin=synthetic_pin,checked=lambda value:Path(value['path']))
        def store(name,value):
            pin=synthetic_pin('/SYNTHETIC/'+name);objects[pin['path']]=value;return pin
        binding=dict(experiment='SYNTHETIC-EXPERIMENT',input_inventory_authority=synthetic_pin('/SYNTHETIC/inventory'))
        api=dict(managed_experiment=binding['experiment']);wire=json.dumps(api)
        baseline=dict(api=api,raw_API_wire=wire,api_wire_sha256=hashlib.sha256(wire.encode()).hexdigest())
        binding['baseline_snapshot']=store('baseline',baseline);bp=store('binding',binding)
        paths=dict(client=F/'fullgame_round_observer_client_v8.py',worker=F/'fullgame_round_observer_v6.py',
            health=H/'continuous_static192_transport_v1.py',health_base=H/'continuous_static192_health_v1.py',
            registry=H/'continuous_static192_registry_v1.py',durability=ROOT/'tools/post_recovery_evaluation/buffered_raw_writer_v2.py',
            control=ROOT/'tools/post_recovery_evaluation/volatile_live_control_v1.py',interpreter=Path('/usr/bin/python3.12'))
        lease=synthetic_pin('/SYNTHETIC/lease');template=dict(schema='SYNTHETIC',actor_slots=[0,1],lease=synthetic_pin('/SYNTHETIC/old-lease'))
        objects[str(ns['TEMPLATE'])]=template
        family=dict(schema='robotron-continuous-static192-fullgame-proof2s-family-v1',runtime=h.pin(F/'run_fullgame_rounds_v7.py'),
            leg_reviewer=h.pin(F/'review_fullgame_rounds_v7.py'),contract=h.pin(F/'fullgame_round_contract_v7.py'),
            current_main_binding=bp,engineering_only=True,main_observer={k:h.pin(p)for k,p in paths.items()},
            main_observer_reviewer=h.pin(F/'review_fullgame_round_observer_v7.py'),
            main_health_finalizer=dict(path='/SYNTHETIC/finalizer',sha256='64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee'),
            private_parent_job=synthetic_pin(ns['TEMPLATE']),
            lease_recovery_authority=store('recovery',dict(restored_lease=lease,absent_pre_outage_lease=template['lease'],
                current_boot_id='SYNTHETIC_BOOT',created_exclusively_without_replacing_existing_file=True,
                exclusive_lock_acquisition_and_release_verified=True)),
            static_profile_contract=h.pin(S/'static_profile_contract_v2.py'),main_input_inventory_authority=binding['input_inventory_authority'])
        protocol=dict(schema='robotron-native-fullgame-continuous-static192-main-health-proof2s-protocol-v1',case=bp,
            raw_API_required=True,close_requires_final_sample=True,hot_max_gap_s=2.0,initial_samples=100,
            raw_queue_protocol='pending-byte-digest-v2',volatile_live_tmpfs=True,source_bound_retired_API_projection=True,
            source_bound_completed_original192_bootstrap=True,source_bound_static_original192_partition=True)
        job=dict(runtime=family['runtime'],source_family_manifest=store('family',family),main_health_protocol=store('protocol',protocol),
            main_binding=bp,lease=lease,training_experiment=binding['experiment'],schema=template['schema'],actor_slots=template['actor_slots'])
        ns.update(read=lambda pin,_h:objects[pin['path']],install_pair=lambda _job,_namespace:dict(engineering_only=True),
            static_profile=lambda:SimpleNamespace(validate_inventory=lambda _b,_h:events.append('inventory')or{'input_count':259},
                sample_domain=lambda _b,_s:events.append('sample_domain')),
            load=lambda _name,_path:SimpleNamespace(check_inputs=lambda _b,full:events.append(('inputs',full)),
                validate=lambda _b,_s:events.append('health_validate')))
        with patch.object(Path,'read_text',return_value='SYNTHETIC_BOOT'):
            result=ns['context'](job,h)
            self.assertEqual(result['inventory']['input_count'],259)
            self.assertEqual(events,['inventory',('inputs',True),'health_validate','sample_domain'])
            for fault in ('family_schema','protocol_schema','missing_registry','extra_launcher','wrong_source','wrong_inventory','experiment','raw_wire'):
                saved=copy.deepcopy((family,protocol,binding,baseline));events.clear()
                if fault=='family_schema':family['schema']='robotron-recovered-round-fullgame-family-v1'
                elif fault=='protocol_schema':protocol['schema']='robotron-native-fullgame-round-main-health-proof2s-protocol-v1'
                elif fault=='missing_registry':del family['main_observer']['registry']
                elif fault=='extra_launcher':family['main_observer']['launcher_census']=synthetic_pin('/SYNTHETIC/old-launcher')
                elif fault=='wrong_source':family['main_observer']['registry']['sha256']='f'*64
                elif fault=='wrong_inventory':family['main_input_inventory_authority']=synthetic_pin('/SYNTHETIC/wrong-inventory')
                elif fault=='experiment':binding['experiment']='SYNTHETIC-CHANGED'
                else:baseline['api_wire_sha256']='f'*64
                with self.subTest(fault=fault),self.assertRaises(ValueError):ns['context'](job,h)
                for target,original in zip((family,protocol,binding,baseline),saved):target.clear();target.update(original)

    def test_actual_root_inventory_requires_all_parent_paths_and_explicit_transition(self):
        ns=self.shared()
        with tempfile.TemporaryDirectory(prefix='synthetic-static-fullgame-inventory-')as temporary:
            h=TempEvidence(temporary)
            old={f'/SYNTHETIC/historical-{i}':{'sha256':str(i)}for i in range(247)}
            parent=h.put(dict(schema='robotron-round-main-health-case-v1',inputs=old))
            current=copy.deepcopy(old);current['/SYNTHETIC/historical-0']={'sha256':'replaced'}
            current['/SYNTHETIC/new-mode-source']={'sha256':'added'}
            authority=dict(schema='robotron-root-continuous-static192-input-inventory-v1',status='ROOT_SELECTED_EXACT_HELD_INPUTS',
                mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',source_authority={'synthetic':True},inputs=current,input_count=248,
                parent_case=parent,replacements={'/SYNTHETIC/historical-0':dict(before=old['/SYNTHETIC/historical-0'],after=current['/SYNTHETIC/historical-0'])},
                added_inputs={'/SYNTHETIC/new-mode-source':current['/SYNTHETIC/new-mode-source']})
            binding=dict(schema='robotron-continuous-static192-health-case-v1',continuous=dict(source_authority={'synthetic':True}),
                inputs=current,input_inventory_authority=h.put(authority))
            self.assertEqual(ns['validate_inventory'](binding,h)['input_count'],248)
            for fault in ('schema','old_authority','count','drop','replacement','addition','source_authority','recursive_inventory'):
                a=copy.deepcopy(authority);b=copy.deepcopy(binding)
                if fault=='schema':b['schema']='robotron-round-main-health-case-v1'
                elif fault=='old_authority':a['schema']='robotron-closed-metadata-readiness-authority-v1'
                elif fault=='count':a['input_count']=247
                elif fault=='drop':del a['inputs']['/SYNTHETIC/historical-1'];b['inputs']=a['inputs'];a['input_count']=len(a['inputs'])
                elif fault=='replacement':a['replacements']={}
                elif fault=='addition':a['added_inputs']={}
                elif fault=='source_authority':a['source_authority']={'synthetic':'wrong'}
                else:
                    # No fixed point is fabricated: redirect the metadata pointer to
                    # a selected current input, with the actual reader collaborator
                    # supplying the exact synthetic authority at that pointer.
                    b['input_inventory_authority']=dict(path='/SYNTHETIC/new-mode-source',identity=dict(mode='0o444'))
                    with patch.dict(ns,read=lambda _p,_h:a if _p==b['input_inventory_authority']else dict(schema='robotron-round-main-health-case-v1',inputs=old)):
                        with self.assertRaises(ValueError):ns['validate_inventory'](b,h)
                    continue
                b['input_inventory_authority']=h.put(a)
                with self.subTest(fault=fault),self.assertRaises(ValueError):ns['validate_inventory'](b,h)

    def test_actual_static_domain_rejects_source_recipe_owner_and_lineage_changes(self):
        ns=self.shared();fields=('pid','starttime_ticks','parent_pid','cgroup','command','environment','affinity','uids','executable')
        binding=dict(schema='robotron-continuous-static192-health-case-v1',inputs={'/SYNTHETIC/source':'sha'},
            slot_eval={str(i):i<37 for i in range(192)},continuous={'synthetic_original_membership':'fixed'},
            input_inventory_authority=synthetic_pin('/SYNTHETIC/inventory'),recipe=dict(lr=.0625,epsilon=.1,expert_ratio=.0),
            actor_environment={'SYNTHETIC':'1'},actor_command=['SYNTHETIC-MAME'],actor_executable={'synthetic':True},
            actor_affinity=[0,1],experiment='SYNTHETIC',owners={role:dict(unit='SYNTHETIC-'+role,invocation='fixed',
                process={key:'SYNTHETIC-'+key for key in fields})for role in('trainer','fleet')},
            exposure={kind:dict(process_id=10,instance_monotonic_ns=20,epoch=1,epoch_reason='SYNTHETIC')for kind in('optimizer','replay')})
        ns['same_domain'](binding,copy.deepcopy(binding))
        for fault in ('inputs','roles','membership','inventory','recipe','actor_environment','command','executable','affinity','experiment','owner','invocation','epoch','instance'):
            value=copy.deepcopy(binding)
            if fault=='inputs':value['inputs']['/SYNTHETIC/source']='changed'
            elif fault=='roles':value['slot_eval']['0']=False
            elif fault=='membership':value['continuous']['synthetic_original_membership']='changed'
            elif fault=='inventory':value['input_inventory_authority']['sha256']='f'*64
            elif fault=='recipe':value['recipe']['lr']=.125
            elif fault=='actor_environment':value['actor_environment']['SYNTHETIC']='2'
            elif fault=='command':value['actor_command']=['OTHER']
            elif fault=='executable':value['actor_executable']={'synthetic':'changed'}
            elif fault=='affinity':value['actor_affinity']=[2]
            elif fault=='experiment':value['experiment']='CHANGED'
            elif fault=='owner':value['owners']['trainer']['process']['pid']='CHANGED'
            elif fault=='invocation':value['owners']['fleet']['invocation']='CHANGED'
            elif fault=='epoch':value['exposure']['replay']['epoch']=2
            else:value['exposure']['optimizer']['instance_monotonic_ns']=21
            with self.subTest(fault=fault),self.assertRaises(ValueError):ns['same_domain'](binding,value)
        sample=dict(status=dict(schema='robotron-continuous-training-static192-snapshot-v2',mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',
            epoch=1,original_membership={'SYNTHETIC':'original'},slots={str(i):dict(eval_only=i<37,state='active',natural_result=None)for i in range(192)}),
            actors={str(i):{'SYNTHETIC':'physical'}for i in range(192)})
        binding['continuous'].update(epoch=1,original_membership={'SYNTHETIC':'original'})
        sample['status']['slots']['0'].update(state='closed_eval',natural_result={'SYNTHETIC':'already typed-positive'})
        del sample['actors']['0'];ns['sample_domain'](binding,sample)
        for fault in ('missing_train','missing_eval_without_result','wrong_membership','unknown_actor','missing_slot'):
            value=copy.deepcopy(sample)
            if fault=='missing_train':del value['actors']['37']
            elif fault=='missing_eval_without_result':value['status']['slots']['0']['natural_result']=None
            elif fault=='wrong_membership':value['status']['original_membership']={'SYNTHETIC':'changed'}
            elif fault=='unknown_actor':value['actors']['192']={}
            else:del value['status']['slots']['191']
            with self.subTest(fault=fault),self.assertRaises(ValueError):ns['sample_domain'](binding,value)

    def test_private_mode_guard_refuses_before_any_ownership_or_metadata_consumer(self):
        ns=self.contract('validate_launch')
        def forbidden(*_a,**_kw):raise AssertionError('Later private/source consumer reached')
        ns.update(read=forbidden,load=forbidden,static_profile=forbidden)
        for field in ('ROBOTRON_CONTINUOUS_TRAINING_MODE','ROBOTRON_ROLLING_TRAINING_CLEANUP'):
            with self.subTest(field=field),patch.dict(os.environ,{field:'1'},clear=True),self.assertRaisesRegex(ValueError,'mode0 before ownership'):
                ns['validate_launch']({},None,{},None)
        for environment in ({},{'ROBOTRON_CONTINUOUS_TRAINING_MODE':'0','ROBOTRON_ROLLING_TRAINING_CLEANUP':'0'}):
            with patch.dict(os.environ,environment,clear=True),self.assertRaisesRegex(ValueError,'Engineering context can never launch'):
                ns['validate_launch']({},None,dict(pair=dict(engineering_only=True),family=dict(native_launch_qualified=False)),None)


if __name__=='__main__':unittest.main()
