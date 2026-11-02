"""NEW focused CPU/fake-MAME checks. Never run actual startmame/MAME or units."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest

HERE=Path(__file__).resolve().parent
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=ROOT/'logs/managed-learning-20261015/run-26'
P=RUN/'preview-selected-client-wallclock-original01-preparation-20261027'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class CapturedExec(Exception):pass


class Tests(unittest.TestCase):
    def fixture(self,directory):
        helper=load('_fresh_fixture',HERE/'exec_fresh_fleet_roles_v1.py')
        prep=load('_fresh_prep',HERE/'prepare_fresh_fleet_roles_v1.py')
        # Only CPU fixture constants differ in memory: tempRoot/fake executable/
        # fake launcher SHA. Actual production sources/contract stay unchanged.
        helper.GAME_ROOT=str(directory)
        (directory/'Scripts').mkdir();(directory/'tools').mkdir()
        lua=directory/'Scripts/main.lua';lua.write_bytes((P/'fast-preview-rgb565-capture-original01-preparation-20261027/raw-format1-existing-wire-policy-original01/main-lua-preview-fast-raw-format1-v1.lua').read_bytes());lua.chmod(0o444)
        launcher=directory/'startmame.sh';launcher.write_text('# CPU fixture only, NEVER executed\n');launcher.chmod(0o444)
        helper.LAUNCHER_SHA=hashlib.sha256(launcher.read_bytes()).hexdigest()
        fake=directory/'fake MAME $ only.py'
        fake.write_text('#!/usr/bin/python3.12\nimport os,sys,json\nprint(json.dumps(dict(argv=sys.argv[1:],mode=os.environ["ROBOTRON_EVAL_MODE"],literal=os.environ.get("LITERAL"))))\n');fake.chmod(0o555)
        helper.MAME_EXECUTABLE=str(fake)
        def pin(p):
            b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=helper.identity(p.lstat()))
        rolemap=HERE.parent/'actual227-rolemap-for-future-fresh192-NOT-ACTIVE.json'
        wait=Path('/home/dave/.cache/robotron-socketwait/robotron-socketwait-13399f4428d28fe88290c833.so')
        sources=dict(helper=pin(HERE/'exec_fresh_fleet_roles_v1.py'),collector=pin(ROOT/'tools/quality_capacity_proposal/supervised_main_fleet_v2.py'),
            rolemap=pin(rolemap),launcher=pin(launcher),canonical_lua=pin(lua),wait_library=pin(wait),
            original_wrapper=pin(P/'role-bound-wrapper-trial-original01/original-mame-with-socket-wait.sh'))
        manifest=prep.prepare_manifest(sources,helper)
        p=directory/'immutable fresh manifest.json';p.write_text(json.dumps(manifest));p.chmod(0o444);mp=pin(p)
        wrapper=Path(manifest['wrapper_path']);wrapper.write_bytes(prep.prepare_wrapper(mp,manifest,helper));wrapper.chmod(0o555)
        return helper,manifest,mp,helper.read(sources['rolemap']),fake

    def test_all192_roles_literal_args_and_two_actual_temporary_fake_execs(self):
        with tempfile.TemporaryDirectory(prefix='fresh192 literal $ ')as td:
            h,m,mp,roles,fake=self.fixture(Path(td))
            h.validate_manifest(m);h.verify_rendered_wrapper(mp,m)
            self.assertEqual(sum(roles['slot_eval'].values()),37)
            for slot in sorted(h.SLOTS,key=int):
                incoming=dict(m['actor_environment'],ROBOTRON_CLIENT_SLOT=slot,LITERAL="spaces ; $() ' ` untouched")
                command,output,probe=h.prepare_launch(m,roles,m['actor_args'],incoming)
                self.assertIsNone(probe);self.assertEqual(command,[str(fake),*m['actor_args']])
                expected=dict(incoming,ROBOTRON_EVAL_MODE='1'if roles['slot_eval'][slot]else'2',
                    LD_PRELOAD=m['wait_library']['path'],ROBOTRON_SOCKET_WAIT_PORT='9998')
                self.assertEqual(output,expected)
            for slot in ('0','1'):
                env=dict(m['actor_environment'],ROBOTRON_CLIENT_SLOT=slot,LITERAL="spaces ; $() ' ` untouched")
                seen=[]
                def fake_exec(path,command,output):
                    # Real exec replacement ONLY in a new temporary Python fake,
                    # never real MAME or its wait library.
                    output=dict(output);output.pop('LD_PRELOAD')
                    result=subprocess.run(command,env=output,capture_output=True,text=True,timeout=5)
                    self.assertEqual(result.returncode,0,result.stderr);seen.append(json.loads(result.stdout));raise CapturedExec()
                with self.assertRaises(CapturedExec):
                    h.dispatch(mp,m,m['actor_args'],env,None,exec_function=fake_exec,parent_check=lambda probe:self.assertIsNone(probe))
                self.assertEqual(seen[0]['mode'],'1'if roles['slot_eval'][slot]else'2')
                self.assertEqual(seen[0]['argv'],m['actor_args']);self.assertEqual(seen[0]['literal'],env['LITERAL'])

    def test_runtime_parent_direct_actor_and_single_verifyroms_intermediate_only(self):
        with tempfile.TemporaryDirectory(prefix='fresh parent fixture ')as td:
            h,m,mp,roles,_=self.fixture(Path(td))
            main=dict(pid=900001,starttime_ticks=100,parent_pid=1,command=m['parent_argv'],cgroup='/CPUfixture/new.service',
                uids=[os.getuid()]*4,executable=dict(path='/usr/bin/bash',identity={'CPUfixture':True}),affinity=[0,1])
            intermediate=dict(main,pid=900002,parent_pid=900001,starttime_ticks=101)
            records={main['pid']:main,intermediate['pid']:intermediate}
            collector=types.SimpleNamespace(process_record=lambda pid:copy.deepcopy(records[pid]))
            fields=dict(Id=h.UNIT,ActiveState='active',SubState='running',NRestarts='0',InvocationID='a'*32,
                MainPID=str(main['pid']),ControlGroup=main['cgroup'])
            kwargs=dict(query=lambda unit:dict(fields),environment_reader=lambda pid:m['parent_environment'])
            actual=h.verify_runtime_parent(m,None,collector,parent_pid=lambda:main['pid'],**kwargs)
            self.assertTrue(actual['direct_parent'])
            actual=h.verify_runtime_parent(m,'verifyroms',collector,parent_pid=lambda:intermediate['pid'],**kwargs)
            self.assertFalse(actual['direct_parent'])
            for probe in (None,'showusage'):
                with self.assertRaises(ValueError):h.verify_runtime_parent(m,probe,collector,parent_pid=lambda:intermediate['pid'],**kwargs)
            fields['NRestarts']='1'
            with self.assertRaises(ValueError):h.verify_runtime_parent(m,None,collector,parent_pid=lambda:main['pid'],**kwargs)

    def test_exact_readonly_probe_allowlist_unknown_controls_and_inert_default(self):
        with tempfile.TemporaryDirectory(prefix='fresh probes ')as td:
            h,m,mp,roles,_=self.fixture(Path(td))
            for args,kind in ((['-showusage'],'showusage'),(['-rompath',h.GAME_ROOT+'/roms','-verifyroms','robotron'],'verifyroms')):
                command,env,probe=h.prepare_launch(m,roles,args,dict(m['parent_environment']))
                self.assertEqual(probe,kind);self.assertEqual(command[1:],args);self.assertEqual(env['ROBOTRON_EVAL_MODE'],'0')
            for kind in ('unknown','slot','control','inputMode','source'):
                args=list(m['actor_args']);env=dict(m['actor_environment'],ROBOTRON_CLIENT_SLOT='0');changed=copy.deepcopy(m)
                if kind=='unknown':args=['-verifyroms','*']
                if kind=='slot':env['ROBOTRON_CLIENT_SLOT']='00'
                if kind=='control':env['ROBOTRON_UNKNOWN_NEW_CONTROL']='1'
                if kind=='inputMode':env['ROBOTRON_EVAL_MODE']='2'
                if kind=='source':changed['canonical_lua']['sha256']='0'*64
                with self.assertRaises(ValueError):
                    h.validate_manifest(changed);h.prepare_launch(changed,roles,args,env)
        inert=subprocess.run(['/usr/bin/python3.12','-I','-B',str(HERE/'exec_fresh_fleet_roles_v1.py')],capture_output=True,text=True,timeout=5)
        self.assertEqual(inert.returncode,0);self.assertIn('PLAN_ONLY',inert.stdout)


if __name__=='__main__':unittest.main()
