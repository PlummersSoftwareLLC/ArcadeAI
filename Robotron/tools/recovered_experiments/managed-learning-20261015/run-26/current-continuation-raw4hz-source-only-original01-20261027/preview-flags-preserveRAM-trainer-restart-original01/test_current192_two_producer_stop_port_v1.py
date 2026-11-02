"""Focused actual-definition CPU checks; no real backend, files or actions."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import types
import unittest

HERE=Path(__file__).resolve().parent
LINUX=HERE/'stop-sources/current192_linux_stop_v1.py'
RECOVERY=HERE/'stop-sources/current192_stop_recovery_v1.py'
CONTROL=Path('/CPUfixture/learning_control.json')

def require(value,message):
    if not value:raise RuntimeError(message)

def actual_functions(path,names,**extra):
    nodes=[n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in names]
    assert {n.name for n in nodes}==set(names)
    scope=dict(require=require,json=json,hashlib=hashlib,re=re,Path=Path,os=os,CONTROL=CONTROL,MODEL=CONTROL.parent)
    scope.update(extra);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return types.SimpleNamespace(**scope)

def actual_methods(names,**extra):
    cls=next(n for n in ast.parse(LINUX.read_text()).body if isinstance(n,ast.ClassDef)and n.name=='LinuxBackend')
    nodes=[n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name in names]
    assert {n.name for n in nodes}==set(names)
    scope=dict(require=require,Path=Path,os=os,CONTROL=CONTROL);scope.update(extra)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(LINUX),'exec'),scope)
    return types.SimpleNamespace(**scope)

class Root:
    def __init__(self,key,events,flags,fail=False):self.key=key;self.events=events;self.flags=flags;self.frozen=False;self.fail=fail
    def __truediv__(self,name):return Value(self,name)
    def resolve(self,**kwargs):return self
    def stat(self):return types.SimpleNamespace(st_uid=os.getuid())
    def __str__(self):return '/CPUfixture/'+self.key

class Value:
    def __init__(self,root,name):self.root=root;self.name=name
    def write_text(self,text):
        assert self.name=='cgroup.freeze'
        self.root.events.append(('write',self.root.key,text,dict(self.root.flags)))
        assert self.root.flags[self.root.key]
        if self.root.fail:raise RuntimeError('injected second kernel write failure')
        self.root.frozen=text.strip()=='1'
    def read_text(self):
        return ('1'if self.root.frozen else'0')if self.name=='cgroup.freeze'else'frozen '+('1'if self.root.frozen else'0')+'\n'

def freeze_fixture(fail=False):
    events=[];flags=dict(fleet=False,supplemental0=False)
    m=actual_methods({'freeze_fleet','assert_producers_held'},
        full_pin=lambda path:{'CPUfixture':'pin'},
        summarize_restart_censored_live_games=lambda *args:{'CPUfixture':'cutoff'})
    b=types.SimpleNamespace(producer_holds=flags,producer_roots={k:Root(k,events,flags,fail and k=='supplemental0')for k in flags},
        main={'held_hashes':{}},guard=types.SimpleNamespace(owner_and_files=lambda *args:None),
        api=lambda:{},out=Path('/CPUfixture/output'),counter=1,original_rows={},
        prepared=dict(original_fleet={},original_supplemental0={}),fleet_frozen=False)
    b.check_producer_owners_and_actors=lambda:events.append(('checked',))or True
    b.state=lambda:events.append(('state',dict(flags)))
    b.event=lambda name,value:value
    b.wait=lambda predicate,*args:require(predicate(),'Fake positive kernel freeze required')
    b.assert_producers_held=lambda:m.assert_producers_held(b)
    return m,b,events

class Tests(unittest.TestCase):
    def test_both_actual_freeze_intents_precede_writes_and_partial_failure_recorded(self):
        for fail in (False,True):
            m,b,events=freeze_fixture(fail)
            if fail:
                with self.assertRaisesRegex(RuntimeError,'injected'):m.freeze_fleet(b,{})
                self.assertFalse(b.fleet_frozen)
                self.assertTrue(b.producer_roots['fleet'].frozen)
                self.assertFalse(b.producer_roots['supplemental0'].frozen)
            else:
                result=m.freeze_fleet(b,{})
                self.assertTrue(result['both_original_producer_cgroups_frozen'])
                self.assertTrue(b.fleet_frozen);self.assertTrue(b.assert_producers_held())
                b.producer_roots['supplemental0'].frozen=False
                with self.assertRaises(RuntimeError):b.assert_producers_held()
            self.assertEqual(b.producer_holds,dict(fleet=True,supplemental0=True))
            writes=[e for e in events if e[0]=='write'];self.assertEqual([e[1]for e in writes],['fleet','supplemental0'])
            for i,event in enumerate(events):
                if event[0]=='write':
                    self.assertTrue(event[3][event[1]])
                    self.assertTrue(any(e[0]=='state'and e[1][event[1]]for e in events[:i]))

    def test_actual_constructor_split_registry_guards(self):
        cls=next(n for n in ast.parse(LINUX.read_text()).body if isinstance(n,ast.ClassDef)and n.name=='LinuxBackend')
        init=next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name=='__init__')
        start=next(i for i,n in enumerate(init.body)if isinstance(n,ast.Assign)and ast.unparse(n.targets[0])=='self.original_actors')
        end=next(i for i,n in enumerate(init.body)if isinstance(n,ast.Assign)and ast.unparse(n.targets[0])=='self.anchor')
        fn=ast.FunctionDef(name='registry',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='self')],kwonlyargs=[],kw_defaults=[],defaults=[]),body=init.body[start:end],decorator_list=[])
        scope=dict(require=require);exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(LINUX),'exec'),scope)
        actors=[dict(slot=i,pid=2_000_000+i,starttime_ticks=100+i,mask=[1,2])for i in range(192)]
        owners={key:dict(pid=pid,starttime_ticks=born,invocation_id=inv,unit=key+'.service',cgroup='/CPUfixture/'+key)for key,pid,born,inv in
                [('fleet',1073404,117607824,'f791a854723b4f90ab5fa8a637a13868'),('supplemental0',1122536,117687032,'ccdd44624bd142db8effc98139940e7d')]}
        main=dict(actors=actors,actual_owners=owners,actor_ownership={str(i):'supplemental0'if i==0 else'fleet'for i in range(192)})
        def fixture():return types.SimpleNamespace(main=copy.deepcopy(main),fleet=dict(owners['fleet'],original_actors=copy.deepcopy(actors[1:])),supplemental0=dict(owners['supplemental0'],original_actors=copy.deepcopy(actors[:1])))
        s=fixture();scope['registry'](s);self.assertEqual(len(s.original_actors),192)
        for damage in ('missing0','wrongmap','wrongowner','wrongsubset'):
            s=fixture()
            if damage=='missing0':s.main['actors']=s.main['actors'][1:]
            if damage=='wrongmap':s.main['actor_ownership']['0']='fleet'
            if damage=='wrongowner':s.supplemental0['starttime_ticks']+=1
            if damage=='wrongsubset':s.fleet['original_actors']+=s.supplemental0['original_actors']
            with self.assertRaises(RuntimeError,msg=damage):scope['registry'](s)

    def test_actual_closed_base_control_and_only_owned_variants(self):
        label='scorecarry-current227-preserve-original01-20261027-final'
        original=dict(measurement=None,lr_scale=.125,other_recipe='unchanged')
        measurement=dict(label=label,checkpoint=None,cohort_s=3600,timeout_s=7200)
        raw=json.dumps(dict(original,measurement=measurement)).encode()
        current=dict(path=str(CONTROL),sha256=hashlib.sha256(raw).hexdigest())
        terminal_pin=dict(path=str(CONTROL.parent/'managed-measurements'/(label+'.json')),
            sha256='ef998bcd59b58335179a0edb3b2e0d47a9c3654a84f867e88c2ff4bcdc1b5f9a')
        terminal=dict(active=False,phase='finished',complete=True,valid=False,reason='trainer_shutdown',
            label=label,request=copy.deepcopy(measurement),ended_unix_s=100.)
        qualification_pin=dict(sha256='489e47f8b0c9ce52a685d0281278e64400334678e161db5fd3acb729571a80cb',identity={'mode':'0o444'})
        objects={'base':original,'event':dict(label=label,purpose='final',control=current),
            'terminal':terminal,'qualification':dict(schema='robotron-root-readonly-closed-original-final-measurement-record-v1',
                actual_terminal_file=terminal_pin,actual_terminal_value=copy.deepcopy(terminal),
                actual_current_api=dict(measurement_active=False,training_enabled=True,managed_measurement={},ts=200.))}
        def checked(pin):
            key='qualification'if pin==qualification_pin else'terminal'if pin==terminal_pin else pin
            return json.dumps(objects[key]).encode()
        m=actual_functions(LINUX,{'validate_base_control'},checked=checked)
        binding=dict(owned_final_control_transition=dict(base_control_archive='base',actual_final_pause_event='event',current_control=current),
                     baseline_API=dict(measurement_active=False,training_enabled=True))
        self.assertEqual(m.validate_base_control(binding,raw,closed_base_measurement=qualification_pin),measurement)
        with self.assertRaises(RuntimeError):m.validate_base_control(binding,raw)
        r=actual_functions(RECOVERY,{'owned_control_variants'})
        with self.assertRaises(RuntimeError):r.owned_control_variants(raw,'scorecarry-new')
        variants=r.owned_control_variants(raw,'scorecarry-new',validated_base_measurement=measurement)
        self.assertIn(raw,variants);self.assertEqual(len(variants),3)
        for damage in ('authority','active','recipe','purpose','label','terminal_active','terminal_request','terminal_quality'):
            b=copy.deepcopy(binding);data=raw;saved=copy.deepcopy(objects)
            if damage=='authority':b['owned_final_control_transition']=None
            if damage=='active':b['baseline_API']['measurement_active']=True
            if damage=='recipe':data=json.dumps(dict(original,lr_scale=.25,measurement=measurement)).encode()
            if damage=='purpose':objects['event']['purpose']='drain'
            if damage=='label':objects['event']['label']='foreign'
            if damage=='terminal_active':objects['terminal']['active']=True
            if damage=='terminal_request':objects['terminal']['request']['cohort_s']=2
            if damage=='terminal_quality':objects['terminal']['valid']=True
            with self.assertRaises(RuntimeError,msg=damage):m.validate_base_control(b,data,closed_base_measurement=qualification_pin)
            objects.clear();objects.update(saved)

    def test_new_recovery_split_scope_and_false_hold_never_write(self):
        # Structural exact recovery order and mandatory per-group ownership gate.
        tree=ast.parse(RECOVERY.read_text());recover=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='recover')
        loop=next(n for n in recover.body if isinstance(n,ast.For))
        self.assertEqual([elt.elts[0].value for elt in loop.iter.elts],['dashboard','listener','control','fleet','supplemental0'])
        self.assertIn("state['producer_holds']['fleet']",ast.unparse(loop))
        self.assertIn("state['producer_holds']['supplemental0']",ast.unparse(loop))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='thaw_original_fleet')
        branch=next(n for n in fn.body if isinstance(n,ast.If)and ast.unparse(n.test)=='not hold_owned')
        self.assertIsInstance(branch.body[-1],ast.Return)
        self.assertFalse(any(isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='write_text'for n in ast.walk(branch)))
        # Unselected stop-only handoff has exactly its old lifecycle (job schema differs only).
        old=HERE.parent/'stop_and_preserve_current_trainer_only_v2.py'
        new=HERE/'stop_and_preserve_current192_trainer_only_v1.py'
        a=ast.parse(old.read_text());b=ast.parse(new.read_text())
        ca=next(n for n in a.body if isinstance(n,ast.ClassDef)and n.name=='Handoff')
        cb=next(n for n in b.body if isinstance(n,ast.ClassDef)and n.name=='Handoff')
        self.assertEqual(ast.dump(ca,include_attributes=False),ast.dump(cb,include_attributes=False))

if __name__=='__main__':unittest.main()
