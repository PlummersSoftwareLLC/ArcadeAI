"""Read-only additive authority for the guard6 final-file copy correction.

The unchanged original scientific chain retains its own proof. New sources
must also occur in the separately closed original CPU tests that exercised them.
All I/O and original-archive predicates are supplied by source-bound callers.
"""
import json
from pathlib import Path
import re
import shlex

H=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal')
REPLACEMENTS={
    'quality32_runtime_guard_v5.py':('quality32_runtime_guard_v6.py','acade462044aad43c00d2207709e9e7ad75abcc53141582ac5b954b468cc808e'),
    'prepare_quality32_campaign_v4.py':('prepare_quality32_campaign_v5.py','6b258e4d0052b3013eee093f2231aa893b69d149fc8b259daf13ba30b47b411a'),
    'monitor_supervised_quality32_v2.py':('monitor_supervised_quality32_v3.py','7d75601d6512afc982393080a6c398b4061f4f944bbfa571d46debca3003ee1a'),
    'prepare_supervised_quality32_monitor_v2.py':('prepare_supervised_quality32_monitor_v3.py','ed14fb7879343d56e05a2ead7dade2336c7b17a64b90fc16f77d74b13d411929'),
}
WORKERS={
    'normal13':('test_final_authority_normal_producers_v3.py','8c6b52e86750145873dcb5dc4c08c9bd6a60ffd11aafc0a63e6b2d351b063b8e'),
    'close3':('test_final_authority_close_path_v1.py','e49eb7198ab39dcd6ada9b87075a9ce47b5ff3f5228243e0d77af5dd8cba95f8'),
    'bound38':('run-original-bound-source-group-v1.py','b6b11bf6da77850fc70df2d66b0b5ef03591e0b93624223eaa5dd3b84a445ed6'),
}

def require(value,message):
    if not value:raise ValueError(message)

def count(value,wanted):
    return type(value) is int and value==wanted

def input_inventory(pins,check_input):
    require(type(pins) is list and pins and len({p['path'] for p in pins})==len(pins),'Distinct prospective input inventory required')
    require(all(check_input(p) is True for p in pins),'A prospectively bound input changed')
    return {p['path']:p for p in pins}

def cpu(config_pin,owner_pin,closure_pin,inputs,argv,read,archives,absent,duration,units):
    c,owner,closed=(read(p) for p in (config_pin,owner_pin,closure_pin))
    require(owner['unit'] not in units and owner['timer'] not in units
        and owner['timer']==owner['unit'].removesuffix('.service')+'.timer','Distinct original CPU owners required')
    units.update((owner['unit'],owner['timer']))
    fields=archives(closed,owner,read,exit_zero=True)
    require(count(closed['original_exit'],0) and closed['lifecycle_complete'] is True and closed['unit_released'] is True,
        'Successful complete original CPU lifecycle required')
    require(len(closed['full_original_archives'])==6 and len(closed['owned_release'])==2,'All six archives and both releases required')
    require(c['unit']==owner['unit'] and c['argv']==argv,'Selected original CPU command differs')
    require(argv[:3]==['/usr/bin/python3.12','-I','-B'],'Selected CPU interpreter differs')
    script=argv[4] if argv[3]=='-u' else argv[3]
    require(script in inputs,'Selected worker was not bound by original CPU inputs')
    for p in inputs.values():
        require(any(e['path']==p['path'] and e['sha256']==p['sha256'] and e['bytes']==p['bytes']
            and all(p['identity'][k]==v for k,v in e['identity'].items()) for e in c['pins']),
            'Full prospective input is absent from original controller configuration')
    wrapper=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+c['output']+'/tmp']+argv
    match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
    require(match is not None and shlex.split(match[1])==wrapper,'Actual archived CPU command differs')
    require(duration(fields['RuntimeMaxUSec'])==180 and fields['MemoryMax']==str(4<<30)
        and duration(fields['CPUQuotaPerSecUSec'])==2 and fields['MemorySwapMax']=='0'
        and fields['Restart']=='no' and fields['SendSIGKILL']=='no','Original CPU resource scope differs')
    require(absent(owner['unit']) and absent(owner['timer']),'An original CPU unit remains loaded')
    return c

def console_report(console,expected,read):
    raw=read(console['stdout'],False);read(console['stderr'],False)
    require(raw and raw.endswith(b'\n') and json.loads(raw.decode().splitlines()[-1])==expected,
        'Original immutable CPU console does not rejoin the reported result')
    require(expected.get('successful') is True and count(expected.get('failures'),0)
        and count(expected.get('errors'),0) and count(expected.get('skipped',0),0),'Original CPU tests failed or skipped')

def worker(inputs,kind,read):
    name,sha=WORKERS[kind]
    matches=[p for p in inputs.values() if Path(p['path']).name==name and p['sha256']==sha]
    require(len(matches)==1,'Exact originally tested worker source required')
    read(matches[0],False)
    return matches[0]['path']

def validate(bundle,selected,read,archives,absent,duration,check_input,baseline_validate):
    require(type(bundle) is dict and set(bundle)=={'baseline_scope','normal13','close3','bound38'},'Exact additive proof bundle required')
    base=read(bundle['baseline_scope'])
    require(base['status']=='TAIL9000_CHAIN152_AUTHORITY11_FOLLOWUP3_CPU_PASS_NOT_YET_ACQUIRED'
        and count(base['total_actual_passed_CPU_tests'],166) and base['candidate_captured'] is False,
        'Complete unchanged original baseline166 required')
    require(base['authority_source']['sha256']=='4954b0fd03bc3bbb09dcaddb490e11868fe662b6d313211a55bc589c8b49e7d4',
        'Exact original baseline authority source required')
    read(base['authority_source'],False)
    chain=read(base['chain']);pre=read(chain['precommit']);job=read(pre['job'])
    baseline_validate(chain,pre,job,base['selected_sources'],read,archives,absent,duration)
    units=set()
    for row in chain['groups']:
        owner=read(row['owner']);units.update((owner['unit'],owner['timer']))
    for key,group,n in [('authority_CPU','authority',11),('followup_CPU','followup',3)]:
        proof=read(base[key]);c=read(proof['config']);j=read(proof['job']);report=read(proof['actual_tests'])
        require(count(proof['actual_count'],n) and report['group']==group
            and count(report['actual_tests_run'],n) and count(report['loaded_test_count'],n)
            and report['passed'] is True and all(count(report[k],0) for k in ('failures','errors','skipped'))
            and report['selected_tests']==j['groups'][group] and report['CUDA_hidden'] is True
            and report['numerical_runtime_imported'] is False and report['actual_quality_run'] is False
            and report['actual_policy_publication'] is False,'Original baseline auxiliary tests differ')
        require(proof['source'] in j['sources'] and proof['tests'] in j['sources'],'Auxiliary source/test membership differs')
        require(c['argv'][4:]==['--execute','--job',proof['job']['path'],'--job-sha256',proof['job']['sha256'],'--group',group],
            'Original auxiliary job/group differs')
        cpu(proof['config'],proof['original_owner'],proof['original_closure'],input_inventory(j['sources'],check_input),
            c['argv'],read,archives,absent,duration,units)
    expected=dict(base['selected_sources'])
    for old,(new,sha) in REPLACEMENTS.items():
        require(old in expected and new in selected and selected[new]['path']==str(H/new)
            and selected[new]['sha256']==sha,'Only exact tested final-copy source replacements allowed')
        del expected[old];expected[new]=selected[new];read(selected[new],False)
    require(selected==expected,'Unchanged scientific sources or selected source set differ')
    guard=selected['quality32_runtime_guard_v6.py']
    normal=read(bundle['normal13']);np=read(normal['prospective_plan'])
    require(normal['guard_source']==guard and count(normal['total_actual_tests'],13)
        and normal['status']=='ALL13_FUTURE_NORMAL_PRODUCER_REGRESSIONS_PASS_FOUR_ORIGINAL_GROUPS_CLOSED'
        and normal['actual_guard_selected'] is False and normal['actual_scientific_review_retried'] is False,
        'Original normal-producer13 proof scope differs')
    ni=input_inventory(np['source_pins'],check_input);require(guard in ni.values(),'Guard absent from original13 inputs')
    require(normal['source_pins']==np['source_pins'] and normal['quality_qualified'] is False,
        'Original13 input inventory or scientific scope differs')
    require(np['counts']==dict(A=7,B=4,C=1,D=1) and [x['group'] for x in normal['groups']]==list(np['counts']),
        'Four original normal-producer groups required')
    ws=worker(ni,'normal13',read)
    for row in normal['groups']:
        group=row['group'];n=np['counts'][group];report=row['result']
        require(count(report['tests'],n) and count(report['expected_tests'],n) and report['group']==group,
            'Original normal-producer test count differs')
        console_report(row['console'],report,read)
        cpu(np['configs'][group],row['owner'],row['closure'],ni,
            ['/usr/bin/python3.12','-I','-B',ws,'--group',group],read,archives,absent,duration,units)
    close=read(bundle['close3']);cp=read(close['prospective_plan']);ci=input_inventory(cp['source_pins'],check_input)
    require(guard in ci.values() and close['actual_close_method_invoked'] is True
        and close['review_scheduling_and_result_capabilities_substituted'] is True
        and close['original_scientific_review_retried'] is False and count(close['actual_tests']['tests'],3),
        'Original direct close3 scope differs')
    console_report(close['console'],close['actual_tests'],read)
    cpu(cp['config'],close['original_owner'],close['original_closure'],ci,
        ['/usr/bin/python3.12','-I','-B',worker(ci,'close3',read)],read,archives,absent,duration,units)
    bound=read(bundle['bound38']);bp=read(bound['plan']);bi=input_inventory(bp['input_fullpins'],check_input)
    require(bound['status']=='PASS38_ORIGINALS_EXIT0_ALL18_ARCHIVED_SIX_UNITS_RELEASED_NOT_SELECTED_FOR_SCIENCE'
        and bound['actual_source_bindings']=={name:selected[name] for name,_ in REPLACEMENTS.values()}
        and all(selected[name] in bi.values() for name,_ in REPLACEMENTS.values())
        and count(bound['total_tests'],38) and bound['actual_candidate_captured'] is False,
        'New scientific source membership requires separate bound38 proof')
    counts=dict(campaign9=9,monitor18=18,monitor_preparation11=11)
    require(set(bound['groups'])==set(bp['groups'])==set(counts),'Exact original bound38 groups required')
    ws=worker(bi,'bound38',read)
    for group,n in counts.items():
        row=bound['groups'][group];report=row['summary']
        require(report['group']==group and count(report['tests'],n) and count(report['loaded_count'],n)
            and len(set(report['selected_tests']))==n and report['CUDA_hidden'] is True
            and report['numerical_runtime_imported'] is False and report['actual_quality_run'] is False
            and report['actual_policy_publication'] is False,'Bound38 original test selection/scope differs')
        console_report(row['consoles'],report,read)
        cpu(bp['groups'][group]['config'],row['owner'],row['closure'],bi,
            ['/usr/bin/python3.12','-I','-B',ws,'--group',group],read,archives,absent,duration,units)
    return dict(status='ORIGINAL_BASE166_AND_FINAL_COPY54_SOURCE_AUTHORITY_VERIFIED',baseline_tests=166,
        added_tests=54,total_source_tests=220,original_CPU_units=len(units),selected_sources=selected,
        candidate_captured=False,quality_qualified=False,learning_speed_gain_verified=False)
