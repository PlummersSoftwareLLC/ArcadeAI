"""Focused pure actual-method tests; no server construction/import or devices."""
import ast
import copy
from pathlib import Path
import types
from typing import Optional
import unittest

HERE = Path(__file__).resolve().parent
BASE = HERE/'base-socket-server-8a288947.py'
NEW = HERE/'socket_server_consolidated_preview_flags_v1.py'
METHODS = {'_pick_default_preview_client_locked', '_ensure_preview_client_selected_locked',
    '_is_preview_client', '_preview_enabled_for_client', '_hud_enabled_for_client',
    '_clear_preview_cache', '_cache_client_preview'}


class Lock:
    def __init__(self,name,held): self.name=name; self.held=held; self.count=0
    def __enter__(self):
        if self.held: raise AssertionError('Client/metrics locks must not be nested')
        self.held.append(self.name);self.count+=1;return self
    def __exit__(self,*args):
        assert self.held.pop()==self.name


def actual_class(path):
    whole=ast.parse(path.read_text());origin=next(n for n in whole.body if isinstance(n,ast.ClassDef)and n.name=='SocketServer')
    names=METHODS | ({'_preview_flags_for_client'}if path==NEW else set())
    selected=[copy.deepcopy(n)for n in origin.body if isinstance(n,ast.FunctionDef)and n.name in names]
    assert {n.name for n in selected}==names
    cls=ast.ClassDef(name='ActualMethods',bases=[],keywords=[],body=selected,decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[]))
    env=dict(Optional=Optional,FrameData=object,time=types.SimpleNamespace(time=lambda:123.5))
    exec(compile(module,str(path),'exec'),env)
    return env['ActualMethods']


def fixture(path,*,selected=10,disabled=False,capture=True,viewers=1,hud=False):
    server=actual_class(path)();held=[];server.client_lock=Lock('client',held)
    server.metrics=types.SimpleNamespace(lock=Lock('metrics',held),preview_capture_enabled=capture,
        web_client_count=viewers,hud_enabled=hud,game_preview_seq=99,game_preview_client_id=10,
        game_preview_updated_ts=120.,game_preview_data=b'old')
    server.preview_disabled=disabled;server.preview_cid=selected
    server.client_states={10:dict(preview_capable=True,client_slot=163),20:dict(preview_capable=True,client_slot=0)}
    return server


def old_flags(server,cid):
    return server._preview_enabled_for_client(cid),server._hud_enabled_for_client(cid)


def frame():
    return types.SimpleNamespace(preview_pixels=b'\x12\x34\x56\x78',preview_width=2,preview_height=1,
        preview_format=1,preview_encoded_format=1,preview_encoded_bytes=4,preview_raw_bytes=4)


class Tests(unittest.TestCase):
    def test_actual_flags_equivalent_all_stable_modes_fallback_and_cache_reset(self):
        count=0
        for disabled in (False,True):
          for capture in (False,True):
           for viewers in (None,0,1):
            for hud in (False,True):
             for state in ('valid','stale','incapable','none','empty'):
              for cid in (10,20):
                args=dict(disabled=disabled,capture=capture,viewers=viewers,hud=hud)
                a=fixture(BASE,**args);b=fixture(NEW,**args)
                for s in (a,b):
                    if state=='stale':s.preview_cid=999
                    if state=='incapable':s.client_states[10]['preview_capable']=False
                    if state=='none':s.preview_cid=None
                    if state=='empty':s.client_states={}
                expected=old_flags(a,cid);actual=b._preview_flags_for_client(cid)
                self.assertEqual(actual,expected,(args,state,cid))
                self.assertEqual(b.preview_cid,a.preview_cid)
                self.assertEqual(b.metrics.game_preview_seq,a.metrics.game_preview_seq)
                self.assertEqual(b.metrics.game_preview_data,a.metrics.game_preview_data)
                self.assertIs(type(actual[0]),bool);self.assertIs(type(actual[1]),bool);count+=1
        self.assertEqual(count,240)

    def test_selected_and_background_actual_acquisition_reduction(self):
        for path in (BASE,NEW):
            s=fixture(path);get=old_flags if path==BASE else lambda s,c:s._preview_flags_for_client(c)
            pv,hud=get(s,10)
            should=bool(pv and s._is_preview_client(10))if path==BASE else bool(pv)
            if should:s._cache_client_preview(10,frame())
            self.assertEqual(s.metrics.game_preview_data,frame().preview_pixels)
            self.assertEqual((s.client_lock.count,s.metrics.lock.count),(5,3)if path==BASE else(2,2))
            s.client_lock.count=s.metrics.lock.count=0
            self.assertEqual(get(s,10),(True,False))
            self.assertEqual((s.client_lock.count,s.metrics.lock.count),(3,2)if path==BASE else(1,1))
            s.client_lock.count=s.metrics.lock.count=0
            self.assertEqual(get(s,20),(False,False))
            self.assertEqual((s.client_lock.count,s.metrics.lock.count),(2,0)if path==BASE else(1,0))

    def test_fresh_send_after_inference_switch_disable_and_no_viewer(self):
        s=fixture(NEW,hud=True)
        ingress=s._preview_flags_for_client(10);self.assertEqual(ingress,(True,True))
        # Model a UI selection/cache-clear between inference entry and return.
        s.preview_cid=20;s._clear_preview_cache()
        self.assertEqual(s._preview_flags_for_client(10),(False,False))
        s._cache_client_preview(10,frame());self.assertEqual(s.metrics.game_preview_seq,0)
        self.assertEqual(s._preview_flags_for_client(20),(True,True))
        s._cache_client_preview(20,frame());self.assertEqual(s.metrics.game_preview_client_id,20)
        s.metrics.web_client_count=0
        self.assertEqual(s._preview_flags_for_client(20),(False,True))
        s.metrics.web_client_count=1;s.metrics.preview_capture_enabled=False
        self.assertEqual(s._preview_flags_for_client(20),(False,True))
        s.preview_disabled=True
        self.assertEqual(s._preview_flags_for_client(20),(False,False))
        self.assertIsNone(s.preview_cid);self.assertEqual(s.metrics.game_preview_seq,0)

    def test_full_server_AST_unchanged_except_declared_UI_snapshot_changes(self):
        tree=ast.parse(NEW.read_text())
        class Undo(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                if node.name=='_preview_flags_for_client':return None
                return self.generic_visit(node)
            def visit_Assign(self,node):
                if isinstance(node.value,ast.Call)and isinstance(node.value.func,ast.Attribute)and node.value.func.attr=='_preview_flags_for_client':
                    names=node.targets[0].elts
                    return [ast.Assign(targets=[names[0]],value=ast.Call(func=ast.Attribute(value=ast.Name(id='self',ctx=ast.Load()),attr='_preview_enabled_for_client',ctx=ast.Load()),args=node.value.args,keywords=[])),
                            ast.Assign(targets=[names[1]],value=ast.Call(func=ast.Attribute(value=ast.Name(id='self',ctx=ast.Load()),attr='_hud_enabled_for_client',ctx=ast.Load()),args=node.value.args,keywords=[]))]
                if any(isinstance(t,ast.Name)and t.id=='should_parse_preview'for t in node.targets):
                    node.value=ast.parse('bool(preview_enabled and self._is_preview_client(cid))',mode='eval').body
                return self.generic_visit(node)
        self.assertEqual(ast.dump(ast.parse(BASE.read_text()),include_attributes=False),
                         ast.dump(Undo().visit(tree),include_attributes=False))
        calls=[n for n in ast.walk(ast.parse(NEW.read_text()))if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute)and n.func.attr=='_preview_flags_for_client']
        self.assertEqual(len(calls),4)
        # Timing observer labels and every gameplay/wire branch survive exact AST restoration.
        for path in (BASE,NEW):compile(path.read_text(),str(path),'exec')


if __name__=='__main__':unittest.main()
