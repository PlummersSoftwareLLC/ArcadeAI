"""One focused actual-launcher/manifest case; no MAME, unit or source action."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
C=HERE.parents[1]


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    new=load(HERE/'exec_fresh_fleet_roles_v2.py','new')
    old=load(HERE.parent/'exec_fresh_fleet_roles_v1.py','old')
    generator=load(C/'launch-sources/prepare_same_state_continuation_v1.py','pins')
    manifest=new.read(generator.small_pin(C/'live-original01/fresh-fleet-admission-original01/actual-fresh192-manifest.json'))
    rolemap=new.read(manifest['rolemap'])
    source=Path(new.GAME_ROOT,'startmame.sh').read_text()
    assert hashlib.sha256(source.encode()).hexdigest()==new.LAUNCHER_SHA
    assert '\nPREVIEW_SLOT_SELECTED=0\n'in source and '--preview-slot'not in manifest['parent_argv']
    begin=source.index('resolve_client_socket() {\n');end=source.index('\n}\n',begin)+3
    # Execute ONLY the exact pure socket/flag function, never the launcher body.
    fixture='PREVIEW_SLOT_SELECTED=0\nSOCKET_ADDRESS=dell:9998\n'+source[begin:end]+ '\nfor ((s=0;s<192;s++)); do resolve_client_socket "$s"; done\n'
    result=subprocess.run(['/usr/bin/bash','-c',fixture],capture_output=True,text=True,check=True)
    values=result.stdout.splitlines();assert len(values)==192 and values[0]=='dell:9998|1'
    assert all(value=='dell:9998|0'for value in values[1:])
    args=manifest['actor_args']
    for slot in range(192):
        env=dict(manifest['actor_environment'],ROBOTRON_CLIENT_SLOT=str(slot),
            ROBOTRON_PREVIEW_CLIENT=values[slot].rsplit('|',1)[1])
        before=dict(env);command,output,probe=new.prepare_launch(manifest,rolemap,args,env)
        assert env==before and probe is None and command==[new.MAME_EXECUTABLE,*args]
        expected=dict(env,ROBOTRON_EVAL_MODE=rolemap['forced_output_mode'][str(slot)],
            LD_PRELOAD=manifest['wait_library']['path'],ROBOTRON_SOCKET_WAIT_PORT='9998')
        assert output==expected
        if slot==0:
            assert output['ROBOTRON_EVAL_MODE']=='2' and output['ROBOTRON_PREVIEW_CLIENT']=='1'
            try:old.prepare_launch(manifest,rolemap,args,env)
            except ValueError as error:assert str(error)=='Fresh actor INPUT controls differ'
            else:raise AssertionError('V1 did not reject actual slot0 input')
        else:
            assert old.prepare_launch(manifest,rolemap,args,env)==(command,output,probe)
    print(json.dumps(dict(status='PASS',focused_cases=1,actual_launcher_pure_function=True,
        actual_manifest=True,slot0='preview1,roletrain2 accepted; V1 refused',
        other191='exact V1 command/output/probe equality',MAME_execs=0,unit_actions=0,
        model_body_reads=0,python=sys.version)))


if __name__=='__main__':main()
