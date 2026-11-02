"""Bind a complete isolated family and expose its actual actor constructor loop.

Never launch a native/CPU job. Old failed original sources and inputs stay held.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=Path(__file__).resolve().parent
P=N/'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02'
F=N/'future-capacity64-shared-slot-domain-UNSELECTED-original01'
E=N/'evaluator-count-active600-counterbalanced-engineering-original01'
R=F/'runtime-family-original02'


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m


class Bind(ast.NodeTransformer):
    def __init__(self,strings,codec):self.strings=strings;self.codec=codec;self.changes=[]
    def visit_Import(self,node):
        for alias in node.names:
            if alias.name=='fixed_slot_cohort_drain_v1':
                self.changes.append(dict(line=node.lineno,old=alias.name,new='fixed_slot_cohort_drain_v2'))
                alias.name='fixed_slot_cohort_drain_v2'
        return node
    def visit_Constant(self,node):
        if type(node.value)is str and node.value in self.strings and self.strings[node.value]!=node.value:
            self.changes.append(dict(line=node.lineno,old=node.value,new=self.strings[node.value]))
            return ast.copy_location(ast.Constant(self.strings[node.value]),node)
        return node
    def visit_BinOp(self,node):
        if ast.unparse(node)=="G / 'tools/startup_policy_journal_proposal/wire_codec_v2.py'":
            self.changes.append(dict(line=node.lineno,old=ast.unparse(node),new='Path('+repr(self.codec)+')'))
            return ast.copy_location(ast.parse('Path('+repr(self.codec)+')',mode='eval').body,node)
        return self.generic_visit(node)


def prepare():
    h=load('_shared64_complete_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    assert h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    ready=h.pin(F/'CPU-shared-domain-ready-family-integration-UNSELECTED.json')
    assert ready['sha256']=='7cfbb4668841fbf3af91dd8873a27d54ce12a61b946ba2d31787b4d776090863'
    h.checked(ready)
    assert not R.exists();R.mkdir(mode=0o700)
    shared=json.loads(h.checked(h.pin(F/'source-derivation-UNSELECTED.json')).read_bytes())
    shared_pins={r['component']:r['derived']for r in shared['derivations']}
    for p in shared_pins.values():h.checked(p)
    old_scope=h.pin(P/'engineering-scope-UNSELECTED.json')
    scope=json.loads(h.checked(old_scope).read_bytes())
    scope.update(schema='robotron-evaluator-count-shared64-active600-scope-definition-v2',
        previous_scope=old_scope,shared_domain=ready,shared_domain_sources=shared_pins,
        failed_original=h.pin(E/'original-engineering-campaign-invalid-disposition.json'),
        failed_original02=h.pin(N/'evaluator-count-active600-counterbalanced-engineering-original02/original-engineering-campaign-invalid-disposition.json'),
        actual_cold_native_import_guard_required=True,
        fresh_all_four_originals_and_identities_required=True,no_old_A1_rate_reuse=True,
        actor_constructor_loop_extracted_without_semantic_change=True,native_launch_selected=False,
        source_preparation_only=True,actual64_startup_verified=False,quality_qualified=False,created_unix_s=time.time())
    scope_pin=h.put(R/'engineering-scope-UNSELECTED.json',scope)
    old_index=json.loads(h.checked(h.pin(P/'CPU-fixture-index-v2.json')).read_bytes())
    records=[];families=[]
    names=dict(view='fixed_slot_cohort_view_v1.py',drain='fixed_slot_cohort_drain_v2.py',
        games='audit_fixed_slot64_games_v1.py',wire='audit_quota64_wire_v2.py',timing='selector_native_timing_v1.py',
        runtime='run_evaluator_count_active600_v2.py',controller='control_evaluator_count_active600_v2.py',
        reviewer='review_evaluator_count_active600_v2.py')
    for template in old_index['cases']:
        role=template['role'];directory=R/role;directory.mkdir(mode=0o700)
        parents={k:Path(v['path'])for k,v in template['sources'].items()}
        parents['drain']=F/'role-drain-prototypes'/role/'fixed_slot_cohort_drain_v2.py'
        parents['reviewer']=E/'reviewer-sources'/(role+'-review_evaluator_count_active600_v2.py')
        old_pins={k:h.pin(p)for k,p in parents.items()}
        made={};constructor_proof=None
        for key in ('view','drain','games','wire','timing','runtime','controller','reviewer'):
            text=h.checked(old_pins[key]).read_text();tree=ast.parse(text)
            strings={str(P/role):str(directory),str(P/'engineering-scope-UNSELECTED.json'):scope_pin['path'],
                     old_scope['sha256']:scope_pin['sha256'],
                     str(Path(template['job']['path']).parent):str(directory/'CPU-fixture-UNPREPARED'),
                     str(N.parent/'future-fixed-slot64-full-game-protocol-original01-preparation-20261024/native-source-family-original01'):str(F),
                     '94e95bc1f6fb8c2063393e57512f43acba57611da9d6e33ba94c857d967ca0f3':shared_pins['codec']['sha256']}
            for previous,pin in made.items():
                # The drain prototype already carries the corrected domain;
                # dependencies elsewhere still reference the originalP2 drain.
                candidates=[old_pins[previous],template['sources'][previous]]
                for parent in candidates:
                    strings[parent['path']]=pin['path'];strings[parent['sha256']]=pin['sha256']
            binder=Bind(strings,shared_pins['codec']['path']);tree=binder.visit(tree)
            if key=='runtime':
                run=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='run')
                loops=[n for n in ast.walk(run)if isinstance(n,ast.For)and isinstance(n.target,ast.Name)
                       and n.target.id=='slot'and isinstance(n.iter,ast.Name)and n.iter.id=='SLOTS'
                       and any(isinstance(z,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='private'for t in z.targets)for z in n.body)]
                assert len(loops)==1
                original_loop=copy.deepcopy(loops[0]);target=loops[0]
                params=['job','output','server','h','seed','bridge','BoundedWitness','bridge_stop',
                        'policy_reader','admission','parse_frame_data','drain_reader','actors','streams','errors']
                fn=ast.parse('def prepare_actor_resources(*, '+', '.join(params)+'):\n    pass\n').body[0]
                fn.body=[copy.deepcopy(original_loop)]
                call=ast.Expr(ast.Call(func=ast.Name(id='prepare_actor_resources',ctx=ast.Load()),args=[],
                    keywords=[ast.keyword(arg=k,value=ast.Name(id=k,ctx=ast.Load()))for k in params]))
                replaced=0
                for parent in ast.walk(run):
                    for field,value in ast.iter_fields(parent):
                        if isinstance(value,list):
                            for index,node in enumerate(value):
                                if node is target:value[index]=call;replaced+=1
                assert replaced==1
                tree.body.insert(tree.body.index(run),fn)
                constructor_proof=dict(extracted_loop_AST=ast.dump(original_loop,include_attributes=False),
                    extracted_loop_source=ast.unparse(original_loop),arguments=params,
                    native_run_calls_exact_extracted_loop=True,no_MAME_launch_or_thread_start_moved=True)
            ast.fix_missing_locations(tree)
            raw=(ast.unparse(tree)+'\n').encode()
            if not binder.changes and key!='runtime':raw=text.encode()
            target=directory/names[key];compile(raw,str(target),'exec')
            with target.open('xb')as stream:
                stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
            made[key]=h.pin(target)
            records.append(dict(role=role,component=key,parent=old_pins[key],derived=made[key],
                                binding_changes=binder.changes,constructor_loop_extraction=constructor_proof if key=='runtime'else None))
        # Derive the real parent component fixture; keep its actual controller,
        # journal, certificate and terminal-writing methods intact.
        fixture_parent=N.parent/'future-fixed-slot64-full-game-protocol-original01-preparation-20261024/fixed_slot64_engineering_fixture_v1.py'
        fixture=fixture_parent.read_text();changes=[]
        for before,after in [('SLOTS=list(range(4096,4128))','SLOTS=list(range(4096,'+str(4096+template['actor_count'])+'))'),
                             ('for _ in range(2):','for _ in range('+str(64//template['actor_count'])+'):')]:
            assert fixture.count(before)==1;fixture=fixture.replace(before,after);changes.append([before,after])
        fp=directory/'complete_family_engineering_fixture_v2.py';compile(fixture,str(fp),'exec')
        with fp.open('xb')as stream:stream.write(fixture.encode());stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        families.append(dict(role=role,actor_count=template['actor_count'],games_per_slot=64//template['actor_count'],
            sources=made,shared_sources=shared_pins,fixture=h.pin(fp),fixture_parent=h.pin(fixture_parent),
            fixture_exact_changes=changes,expected_games=64,minimum_complete_games=50,inference_batch_max_size=16,
            native_launch_ready=False,actual_complete_constructor_guards=False))
    result=h.put(R/'complete-source-family-INCOMPLETE.json',dict(
        schema='robotron-shared64-complete-evaluator-count-source-family-preparation-v1',source=h.pin(__file__),
        scope=scope_pin,shared_component_readiness=ready,families=families,derivations=records,
        status='FULL_SOURCE_DAG_BOUND_ACTUAL_COMPLETE_CONSTRUCTOR_GUARDS_REQUIRED',
        old_originals_or_main_changed=False,native_launch_ready=False,actual64_live_startup_verified=False,
        quality_qualified=False,throughput_gain_verified=False,created_unix_s=time.time()))
    print(json.dumps(dict(source_family=result,sources=len(records),native_ready=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    if p.parse_args().prepare:prepare()
    else:print('PLAN_ONLY')
