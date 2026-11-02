"""Record actual original06 live/closed evidence through the existing CAS adopter."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

N=Path(__file__).resolve().parent
G=N.parents[3]
E=N/'evaluator-count-active600-counterbalanced-engineering-original06'
ORDER=('01-A1-control','02-B1-capacity64','03-B2-capacity64','04-A2-control')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module

def live(c,pin):
    owner=c.read(pin)
    assert c.control.show(owner['unit'])['MainPID']==str(owner['pid'])
    assert c.control.show(owner['unit'])['InvocationID']==owner['invocation_id']
    assert int(Path('/proc',str(owner['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])==owner['starttime_ticks']
    return owner

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['active','review','closed'],required=True)
    parser.add_argument('--case',choices=ORDER,required=True)
    parser.add_argument('--session',type=int)
    parser.add_argument('--readback',type=Path)
    parser.add_argument('--label',required=True)
    a=parser.parse_args();assert re.fullmatch('[a-zA-Z0-9-]+',a.label)
    c=load('_record_close',N/'close_shared64_original06_case_v1.py').CloseOriginal(a.case)
    h=c.h;index=ORDER.index(a.case);suffix=a.case.split('-')[1]
    state=json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    assert state['current_main_binding']==c.job['main_binding']
    main_readback=json.loads(subprocess.run(['/usr/bin/python3.12','-I','-B',str(h.checked(state['current_main_monitor']))],capture_output=True,text=True,check=True,timeout=30).stdout)
    completed=[]
    for name in ORDER:
        path=E/name/'independent-original-capacity64-case-closeout.json'
        if not path.exists():break
        pin=h.pin(path);proof=c.read(pin)
        assert proof['status']=='VALID_ORIGINAL_CAPACITY64_ENGINEERING_CASE_NO_QUALITY'
        assert proof['completed_valid_originals']==len(completed)+1
        completed.append(pin)
    evidence=[c.qualified_pin,c.qualified['design'],c.qualified['exact_job_CPU_guard_closeout'],c.qualified['raw_reviewer_protocol_chain_CPU'],*completed]
    wait=None;trial=None
    if a.mode=='active':
        assert a.session and a.readback and len(completed)==index
        rp=h.pin(a.readback.resolve());r=c.read(rp)
        assert r['case']==a.case and r['native_job']==c.record['native_job']
        assert 0<=time.time()-r['created_unix_s']<=90
        assert r['actual_all_declared_prefixes_ready']is True
        for item in r['owners']:live(c,item['owner'])
        wait=dict(tool_session=a.session,kind='original06_'+suffix+'_active600_native',owner=r['owners'][0]['owner'],observer=r['owners'][1]['owner'],certified_live_readback=rp)
        trial=dict(directory=str(E),kind='protected_policy_evaluator_count_ABBA_active600_common_v11_observer_and_guarded_reviewer_chain',case=a.case,order=list(ORDER),qualified_launches=c.qualified_pin,live_readback=rp,active_start=r['active_start'],actual_all_declared_prefixes_ready=True,original_attempt=1,no_retry=True,quality_qualified=False)
        evidence.append(rp)
        stage='ORIGINAL06_'+suffix+'_ACTIVE600_ALL'+str(c.count)+'_CERTIFIED'
        progress=suffix+' fixed600s load live; all'+str(c.count)+' original actors/policy/ROM1200 prefixes/argv/resources verified. Full original raw review remains required.'
        next_action='Observe same native tool'+str(a.session)+' to planned stop, independently close original scopes and run the one original full raw CPU660 review before advancing.'
    elif a.mode=='review':
        assert a.session and len(completed)==index
        terminal=h.pin(c.directory/'independent-original-native-observer-terminal-closeout.json')
        proof=c.read(terminal);assert proof['case']==a.case
        rd=c.directory/'independent-original-active600-CPU-original01'
        op=h.pin(rd/'execution-original01/root-original-identity.json');owner=live(c,op)
        cfg=c.read(h.pin(rd/'controller-config.json'))
        assert Path('/proc',str(owner['pid']),'cmdline').read_bytes().decode().split('\0')[:-1]==cfg['argv']
        wait=dict(tool_session=a.session,kind='original06_'+suffix+'_independent_raw_CPU660_review',owner=op,native_and_observer_terminal=terminal)
        trial=dict(directory=str(E),case=a.case,qualified_launches=c.qualified_pin,native_measurement_live=False,raw_review_pending=True,original_attempt=1,no_retry=True,quality_qualified=False)
        evidence.extend([terminal,op,h.pin(rd/'controller-config.json'),h.pin(rd/'job.json')])
        stage='ORIGINAL06_'+suffix+'_NATIVE_CLOSED_ORIGINAL_RAW_REVIEW_LIVE'
        progress=suffix+' reached600s planned stop; native/observer metadata and release checked. Original raw CPU reviewer live; no result accepted yet.'
        next_action='Observe same original reviewer tool'+str(a.session)+'; only actual0 and complete independent raw review permit valid case closeout.'
    else:
        assert len(completed)==index+1
        proof=c.read(completed[-1]);assert proof['case']==a.case
        assert proof['all_native_observer_reviewer_archives_resources_pins_and_release_verified']is True
        for op in proof['original_owners']:
            o=c.read(op)
            try:birth=int(Path('/proc',str(o['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])
            except (FileNotFoundError,ProcessLookupError):birth=None
            assert birth!=o['starttime_ticks']
            for unit in [o['unit'],o['timer']]:assert c.control.show(unit)['LoadState']=='not-found'
        evidence.extend([proof['independent_report'],proof['native_and_observer_terminal_closeout']])
        stage='ORIGINAL06_'+suffix+'_VALID_ALL_SCOPES_CLOSED'
        progress=suffix+' valid engineering case: all'+str(c.count)+' ROM1200 prefixes, original raw health replay, planned stop and original scopes independently reviewed. '+str(len(completed))+'/4 originals valid; no early comparison.'
        next_action=('Launch the one original '+ORDER[index+1]+' after its exact fresh preflight.'if index<3 else'Prepare and run the one independent final ABBA CPU review; both B cases need their own precommitted gates.')
    updates=dict(
        stage=stage,phase=stage,current_phase=stage,
        source_freeze=True,full_source_freeze=True,scientific_job_running=False,
        performance_job_running=a.mode!='closed',
        all_current_original_scientific_handles_terminal=True,
        all_current_original_handles_terminal=a.mode=='closed',actual_running_wait=wait,
        active_performance_trial=trial,
        current_controlled_engineering_experiment=dict(directory=str(E),qualified_launches=c.qualified_pin,design=c.qualified['design'],complete_valid_originals=len(completed),valid_original_closeouts=completed,comparison_pending=True,prior_rate_reused=False),
        active_optimization_preparation=None,current_main_readback=main_readback,
        latest_goal_turn_classification='progress',classification_basis=progress,
        latest_progress=progress,next_action=next_action)
    stem='original06-'+suffix.lower()+'-'+a.mode+'-'+a.label
    record=h.put(c.directory/(stem+'-progress-record.json'),dict(
        archive=str(E/('canonical-'+stem+'-adoption')),
        recovery=str(N.parent/('current-optimization-recovery-index-20261026-'+stem+'.json')),
        evidence=evidence,updates=updates,source=h.pin(__file__),
        documentation=progress+' Main192/197 and autosave healthy; production trainer unchanged. All four original ABBA cases and final independent comparison required. Source holds active. Original05 remains invalid and its rates are not reused. No new policy quality or learning-speed claim. Next: '+next_action))
    proc=subprocess.run(['/usr/bin/python3.12','-I','-B',str(N/'adopt_shared64_progress_v1.py'),'--record',record['path'],'--sha256',record['sha256']],capture_output=True,text=True)
    print(proc.stdout);print(proc.stderr);assert proc.returncode==0

if __name__=='__main__':main()
