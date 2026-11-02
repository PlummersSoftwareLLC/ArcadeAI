"""Focused pure guards/actual retained metadata; never opens checkpoint bodies."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=G/'logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/preview-flags-preserveRAM-trainer-restart-original01'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

V=module('_prospective_lr0625_verifier',HERE/'verify_recipe_phase_snapshot_lr0625_v1.py')
R=module('_prospective_lr0625_recipe',HERE/'recipe.py')
RAW=V.STRICT_PATH.read_bytes()

def context(scale=.0625):
    return dict(V.HISTORICAL_HELD_CONTEXT,learning_control_lr_scale=scale,
                optimizer_lr=3.125e-6 if scale==.0625 else 6.25e-6)

class FakeMetadata:
    """Only metadata plumbing is mocked; all transition predicates are actual."""
    GAME=G
    def __init__(self):self.data={};self.serial=0;self.original=V.load_base()
    def put(self,value,sha=None):
        self.serial+=1;p=dict(path='/CPUfixture/metadata-'+str(self.serial)+'.json',
            sha256=sha or hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest(),bytes=1)
        self.data[p['path']]=value;return p
    def pinned_json(self,pin,evidence,label):
        evidence['bound_files'][label]=dict(mode='0o444',uid=os.getuid(),nlink=1)
        return self.data[pin['path']]
    def fingerprint(self,path):return self.original.fingerprint(path)
    def trainer_identity(self,owner):return self.original.trainer_identity(owner)

def fixture():
    base=FakeMetadata();registry=json.loads((N/'actual-current-mixed192-registry-original01/current-mixed192-main-binding.json').read_text())
    owner=registry['owner'];phase=registry['active_resume_phase_record']
    stop=json.loads((N/'stop-original01/result.json').read_text());boot=json.loads(Path(stop['saved']['report']['path']).read_text())
    before=json.loads((HERE/'registered-LR125-control-before-archive.json').read_text());assert before['lr_scale']==.125
    after=copy.deepcopy(before);after['lr_scale']=.0625
    beforepin=base.put(before,sha=registry['held_hashes'][str(G/'models_dqn/learning_control.json')]);afterpin=base.put(after)
    planpath=G/'logs/managed-learning-20261015/run-26/post-preview-next-learning-knob-LR0625-precommit-original02-20261027.json'
    planpin=base.put(json.loads(planpath.read_text()),sha=hashlib.sha256(planpath.read_bytes()).hexdigest())
    regpin=base.put(registry,sha='6bfe2e5ceac0be42fce70f95ee65fbd160b8daff3b4a5e15f691b6586ad131fd')
    writer=dict(schema='robotron-owned-one-field-hot-LR-control-publication-v1',owner_before=owner,owner_after=owner,
        changed_fields=['lr_scale'],atomic_replace=True,weights_optimizer_scaler_replay_loaded_or_reset=False,
        phase_record_changed=False,before_current_control=dict(path=str(G/'models_dqn/learning_control.json'),sha256=beforepin['sha256']),
        after_current_control=dict(path=str(G/'models_dqn/learning_control.json'),sha256=afterpin['sha256']),
        publication_begin_unix_s=1002.,publication_complete_unix_s=1003.)
    writerpin=base.put(writer);snapshots=[]
    for i,t in enumerate((1000.,1004.,1006.)):
        exp={k:dict(enabled=True,available=True,process_id=owner['pid'],instance_monotonic_ns=12345+(k=='replay'),
            epoch=1,epoch_reason='optimizer_restore_begin'if k=='optimizer'else'directory_adopt_begin')for k in('optimizer','replay')}
        exp['optimizer']['total']=dict(applied=100+i);exp['replay']['accepted_total']=1000+i*100
        api=dict(ts=t+.5,pipeline_snapshot_age_s=.1,client_count=192,training_enabled=True,measurement_active=False,
            memory_buffer_size=6000000,lr=6.25e-6 if i==0 else 3.125e-6,managed_experiment=before['experiment'],
            pipeline_read_error='',bank_persistence_read_error='',host_pipeline=dict(available=True,learning_exposure=exp))
        for k in V.CLOCKS:api[k]=int(boot['clocks'][k])+1000+i*100
        snapshots.append(dict(raw_API=base.put(api),before_unix_s=t,after_unix_s=t+1))
    proof=dict(schema='robotron-owned-one-field-hot-LR125-to-LR0625-transition-v1',root_plan=planpin,owner=owner,
        current_registry=regpin,before_control=beforepin,after_control=afterpin,writer_receipt=writerpin,
        before_API=snapshots[0],first_applied_API=snapshots[1],anchor_API=snapshots[2])
    job=dict(hot_lr_transition=base.put(proof),phase_snapshot=dict(owner=owner,phase_record=phase),
        source_control_context=dict(archived_control=afterpin,held_recipe_context=context()),experiment=before['experiment'],
        clock_floor={k:base.data[snapshots[2]['raw_API']['path']][k]+100 for k in V.CLOCKS})
    return base,job,boot,proof

class Tests(unittest.TestCase):
    def test_exact_three_literals_no_numeric_body_change_and_old125_rejected(self):
        effective,p=V.specialize_strict_source(RAW,context())
        self.assertEqual(p['replacement_count'],3);self.assertTrue(p['reverse_exact_raw_source'])
        def fn(raw,name):return ast.dump(next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)and n.name==name),include_attributes=False)
        self.assertEqual(fn(RAW,'validate_checkpoint'),fn(effective,'validate_checkpoint'))
        for scale in (.125,.5):
            with self.assertRaises(Exception):V.infer_recipe(context(scale))
        # Execute the actual saved-Adam scalar guard only, not Torch/model setup.
        tree=ast.parse(effective);body=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='validate_checkpoint').body
        guard=next(n for n in body if isinstance(n,ast.For)and isinstance(n.iter,ast.Tuple)
                   and isinstance(n.iter.elts[0],ast.Tuple)and isinstance(n.iter.elts[0].elts[0],ast.Constant)and n.iter.elts[0].elts[0].value=='lr')
        code=compile(ast.Module(body=[guard],type_ignores=[]),'<ACTUAL saved Adam guard>','exec')
        scope=dict(require=V.require,math=math,HELD_RECIPE_CONTEXT=context(),group=dict(lr=3.125e-6,eps=1.5e-4,weight_decay=0.))
        exec(code,scope);scope['group']['lr']=6.25e-6
        with self.assertRaisesRegex(RuntimeError,'Saved Adam lr differs'):exec(code,scope)

    def test_control_one_typed_field_only_and_preserved_closed_measurement(self):
        before=dict(experiment='actual-training-label',reason='same',lr_scale=.125,
            epsilon_ramp=dict(anchor=42,start=.1,end=.1,duration=500),measurement=dict(label='already-closed',cohort_s=3600))
        after=copy.deepcopy(before);after['lr_scale']=.0625;recipe=R.for_scale(.0625)
        self.assertEqual(R.check_control(before,after,before['experiment'],recipe),after)
        for damage in ('experiment','reason','anchor','measurement','type','extra'):
            changed=copy.deepcopy(after)
            if damage=='experiment':changed['experiment']='renamed'
            if damage=='reason':changed['reason']='new text'
            if damage=='anchor':changed['epsilon_ramp']['anchor']+=1
            if damage=='measurement':changed['measurement']['label']='rearmed'
            if damage=='type':changed['measurement']['cohort_s']=3600.
            if damage=='extra':changed['new_key']=True
            with self.assertRaises(Exception,msg=damage):R.check_control(before,changed,before['experiment'],recipe)

    def test_actual_retained_boot_and_transition_positive_and_guard_damage(self):
        base,job,boot,proof=fixture();e=dict(bound_files={})
        V.check_hot_lr_transition(job,base,e,boot)
        self.assertTrue(e['hot_lr_transition_verified'])
        self.assertEqual(e['actual_boot_recipe_preserved']['learning_control_lr_scale'],.125)
        self.assertEqual(e['actual_saved_recipe_expected']['learning_control_lr_scale'],.0625)
        for damage in ('lr','applied','appliedtype','appliedregress','epoch','instance','admissions','phase','registry','beforebase','fields','boot','time','duration','stale','agetype','owner'):
            b,j,old,p=fixture();first=b.data[p['first_applied_API']['raw_API']['path']];last=b.data[p['anchor_API']['raw_API']['path']]
            if damage=='lr':first['lr']=6.25e-6
            if damage=='applied':last['host_pipeline']['learning_exposure']['optimizer']['total']['applied']=101
            if damage=='appliedtype':last['host_pipeline']['learning_exposure']['optimizer']['total']['applied']=102.
            if damage=='appliedregress':first['host_pipeline']['learning_exposure']['optimizer']['total']['applied']=99
            if damage=='epoch':last['host_pipeline']['learning_exposure']['optimizer']['epoch']=2
            if damage=='instance':last['host_pipeline']['learning_exposure']['replay']['instance_monotonic_ns']+=1
            if damage=='admissions':last['host_pipeline']['learning_exposure']['replay']['accepted_total']=1
            if damage=='phase':j['phase_snapshot']['phase_record']={'sha256':'changed'}
            if damage=='registry':p['current_registry']['sha256']='0'*64
            if damage=='beforebase':
                p['before_control']['sha256']='0'*64
                b.data[p['writer_receipt']['path']]['before_current_control']['sha256']='0'*64
            if damage=='fields':b.data[p['writer_receipt']['path']]['changed_fields'].append('experiment')
            if damage=='boot':old['held_recipe_context']=context()
            if damage=='time':p['first_applied_API']['before_unix_s']=1002.
            if damage=='duration':p['before_API']['before_unix_s']=990.
            if damage=='stale':first['pipeline_snapshot_age_s']=6.
            if damage=='agetype':first['pipeline_snapshot_age_s']=False
            if damage=='owner':p['owner']=dict(p['owner'],pid=123)
            with self.assertRaises(Exception,msg=damage):V.check_hot_lr_transition(j,b,dict(bound_files={}),old)

    def test_phase_predicates_inherited_and_default_readfree_no_tensor_imports(self):
        old=ast.parse((G/'tools/lr125_phase_cpu_verifier_proposal_20261023/verify_recipe_phase_snapshot.py').read_text())
        new=ast.parse((HERE/'verify_recipe_phase_snapshot_lr0625_v1.py').read_text())
        for name in ('check_acquisition','verify_phase','load_base'):
            get=lambda t:ast.dump(next(n for n in t.body if isinstance(n,ast.FunctionDef)and n.name==name),include_attributes=False)
            self.assertEqual(get(old),get(new))
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(V.main([]),0)
        self.assertFalse(any(k=='torch'or k.startswith('torch.')or k=='numpy'for k in sys.modules))

if __name__=='__main__':unittest.main()
