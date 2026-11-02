"""Pure source/proof joins for the unselected combined continuity correction.

Callbacks are supplied by the source-bound preparer. No process launch, model
load, device query, original scientific review or policy publication occurs.
"""
import ast
import json
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
H=G/'tools/quality_capacity_proposal'
E=G/'tools/eval_capacity_proposal'
PACKAGE_SHA='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
SOCKET_SHA='b552b2e83a9cc10cf7e4125cef22f571abe9189bd2ad3e63c6f48aa7df0e4516'
HELPER_SHA='263d369d54706cfead3a3671343d43fdd83d3a1f344656787c29fac71ca8d38f'
BOUND_WORKER=('run_profile06_bound_regressions_v2.py','8ea8d0aaa68b94f1adff93a68e787bb3a95fd340ae5bf5ce9d43240a6405c2b6')
OLD_SELECTED={
 'quality32_acquisition_v2.py':('quality32_acquisition_v4.py','2f8ad3d84b9033c892318d069e0c462bf3f07dd3d0e9e69211008f602153ba70'),
 'prepare_quality32_candidate_CPU_v3.py':('prepare_quality32_candidate_CPU_v5.py','993cda7a49999c2bb569f6c7ae74a691dd3e13d1048e49d90e87f8e6886f53b1'),
 'audit_quality32_evidence_v2.py':('audit_quality32_evidence_v4.py','f07ccdd098cbf879c7ff98ef26e92e525b7a0ea951c38641fa2b5c0571fa50e3'),
 'review_closed_quality32_v6.py':('review_closed_quality32_v8.py','fa7883223eca627e89663cede037e1787888080ce06b31fcf6f8462fadd28bdb'),
 'protect_quality32_winner_v4.py':('protect_quality32_winner_v6.py','815f326b3129721910450c74a96eea3bfcda0b4f70430cb1ba9545388ab9a212'),
 'quality32_runtime_guard_v6.py':('quality32_runtime_guard_v8.py','738aafda0f064fd01e6311d1b02c687f551b912d838805ca0aa79247110bbe20'),
 'prepare_quality32_campaign_v5.py':('prepare_quality32_campaign_v7.py','e2ae49f9a4d9f5b0ded62c53a1b80e1ef4d5e050b9849349c42a551238c3240f'),
 'monitor_supervised_quality32_v3.py':('monitor_supervised_quality32_v5.py','50a3f3c4f4ecc785fcae58382fc143107f07e8edca27de096e70e3ac478e356e'),
 'prepare_supervised_quality32_monitor_v3.py':('prepare_supervised_quality32_monitor_v5.py','c70a05bb6c9e33ba60b87c3b871d15c3705464c907e339e2e0f5fff4db706f43'),
}


def require(value,message):
    if not value:raise ValueError(message)


def count(value,expected):return type(value) is int and value==expected


def inventory(pins,check):
    require(type(pins) is list and pins and len({p['path'] for p in pins})==len(pins),'Distinct prospective source inputs required')
    require(all(check(p) is True for p in pins),'A prospectively bound input changed')
    return {p['path']:p for p in pins}


def console(row,report,read):
    for name in ['stdout','stderr']:
        entry=row['consoles'][name]
        archive=entry.get('archive',entry.get('readonly_archive'))
        require(archive is not None and archive['sha256']==entry['original']['sha256']
                and archive['bytes']==entry['original']['bytes'],'Exact separate producer-byte copy required')
        raw=read(archive,False)
        if name=='stdout':
            require(raw.endswith(b'\n') and json.loads(raw.splitlines()[-1])==report,'Actual original CPU console/report differs')


def report_cpu(row,n,worker,read,cpu,check,units):
    value=row['actual_tests'];report=read(value) if isinstance(value,dict) and 'path' in value else value
    require(report.get('status')=='PASS' and count(report.get('tests'),n)
        and all(count(report.get(k),0) for k in ['failures','errors','skipped']), 'Complete successful original CPU test report required')
    require(report.get('CUDA_hidden') is True and report.get('numerical_runtime_imported') is False,
            'This regression group must remain a standard-library CPU test')
    console(row,report,read)
    job=read(row['job']);inputs=inventory(job['inputs'],check)
    path=str(H/worker[0]);require(path in inputs and inputs[path]['sha256']==worker[1], 'Exact tested worker absent from prospective inputs')
    cfg=read(row['config'])
    argv=['/usr/bin/python3.12','-I','-B',path,'--job',row['job']['path'],'--job-sha256',row['job']['sha256']]
    require(cfg['argv']==argv and any(p['path']==row['job']['path'] and p['sha256']==row['job']['sha256'] for p in cfg['pins']),
            'Actual original worker/job binding differs')
    cpu(row['config'],row['original_owner'],row['original_closure'],inputs,argv,units)
    require(report.get('source_selected_for_science',row.get('source_selected_for_science')) is False,
            'CPU tests cannot select a scientific source')
    return report,job,inputs


def source_migration(stage05,stage06,inputs,read):
    """Every dependency body must be the exact reviewed binding substitution."""
    changes={'3ee43f9bd95fdda8f02abc048999a84513da71125dfd6b2e6558f45d2de6caf9':
             '41acc755d6daa728fa0b8291d27e60da8f4e80e7d55ab8a2110bcb8b377d85af','profile04/':'profile05/'}
    require(len(stage05['sources'])==9 and len(stage06['sources'])==10,'Both complete dependency migrations required')
    for stage,rows in [(5,stage05['sources']),(6,stage06['sources'])]:
        if stage==6:
            changes={'41acc755d6daa728fa0b8291d27e60da8f4e80e7d55ab8a2110bcb8b377d85af':PACKAGE_SHA,'profile05/':'profile06/'}
        for row in rows:
            old,new=Path(row['old']).name,Path(row['new']).name
            root=E if old=='audit_pilot_evidence_score_carry_v1.py' else H
            op,np=str(root/old),str(root/new)
            require(op in inputs and np in inputs and inputs[op]['sha256']==row['oldsha']
                and inputs[np]['sha256']==row['newsha'],'Migration sources absent or changed')
            original=read(inputs[op],False).decode();expected=original
            for before,after in changes.items():expected=expected.replace(before,after)
            if stage==6 and old in ['audit_pilot_evidence_score_carry_v1.py','audit_quality32_evidence_v3.py']:
                expected=expected.replace('84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40',SOCKET_SHA)
            require(expected==read(inputs[np],False).decode(),'A dependency changed beyond exact tested source bindings')
            changes[old]=new;changes[row['oldsha']]=row['newsha']


def validate(bundle,selected,read,check,cpu,baseline_authorize):
    """Join the historical baseline and every additive actual original proof.

    The source-bound caller must run the unchanged old authorize() for the
    baseline and use the unchanged resource/closure checker for each new CPU.
    Neither callback grants scientific qualification or a launch capability.
    """
    required={'baseline_precommit','baseline_preparer','package','journal34','primitive18','wire56','closed26',
              'bound77','bound36','stage05_migration','stage06_migration'}
    require(type(bundle) is dict and set(bundle)==required,'Complete combined source proof bundle required')
    require(bundle['baseline_precommit']['sha256']=='8b13316360c320dab3fce04dfe706ab7e46ccb68d7304bbcdf3877a139d74ed4'
        and bundle['baseline_preparer']['path']==str(H/'prepare_tail9000_followup_v2.py')
        and bundle['baseline_preparer']['sha256']=='bf865d33bc1c9286560459d57c6d3a0260aa75ab048847e8885e284e92d5310d',
        'Exact unchanged baseline precommit/preparer required')
    require(bundle['package']['path']==str(H/'profile06/runtime-source-package.json')
        and bundle['package']['sha256']==PACKAGE_SHA,'Exact tested combined package required')
    old=read(bundle['baseline_precommit']);read(bundle['baseline_preparer'],False)
    expected=dict(old['selected_sources'])
    for oldname,(newname,sha) in OLD_SELECTED.items():
        require(oldname in expected and newname in selected and selected[newname]['path']==str(H/newname)
            and selected[newname]['sha256']==sha,'Exact tested dependency substitutions required')
        del expected[oldname];expected[newname]=selected[newname]
    require(selected==expected,'Unchanged supervision sources or selected source set differs')
    base=baseline_authorize(old,bundle['baseline_preparer'])
    require(base['source_authority']['status']=='ORIGINAL_BASE166_AND_FINAL_COPY54_SOURCE_AUTHORITY_VERIFIED'
        and count(base['source_authority']['total_source_tests'],220)
        and base['quality_qualified'] is False and base['candidate_captured'] is False,
        'Complete original baseline220 plus its original self-test authority required')
    units=set()
    j34=read(bundle['journal34'])
    r34,job34,i34=report_cpu(j34,34,('test_start_consistency_v1.py','30df7c0a0146091120901086dd00d639838250fe2e45b9b543752b6f58c0b5e6'),read,cpu,check,units)
    require(r34.get('original_failed_receipt_remains_invalid') is True,'Failed original science must remain invalid')
    p18=read(bundle['primitive18'])
    r18,job18,i18=report_cpu(p18,18,('test_recent_start_continuity_v1.py','d061194846bcf489b2c83bbb091db39352905770ed1df10ffd4fa82e0b2604bc'),read,cpu,check,units)
    require(p18['source']['path']==str(H/'recent_start_continuity_proposal_v1.py') and p18['source']['sha256']==HELPER_SHA
        and p18['source'] in i18.values() and r18['scope']=='PURE_PRIMITIVE_ONLY'
        and r18['full_handler_validated'] is False and r18['actual_wire_validated'] is False,'Primitive18 scope or helper differs')
    c26=read(bundle['closed26'])
    rc26,jc26,ic26=report_cpu(c26,26,('run_closed_predecessor26_v4.py','ee14a37c49e3b43fbc9caee39c9977d787b2868b7d107f242859bc0d3f336e68'),read,cpu,check,units)
    require(c26['source']['path']==str(G/'tools/evaluation_startup_proposal/startup_probe_core_v3.py')
        and c26['source']['sha256']=='75ddb075e91b516242fa461eac183b5bf0a15c303097d17d74db992fd0a5d31a'
        and c26['source'] in ic26.values() and rc26['actual_native_review_outer_exits']==[1,2,1]
        and rc26['actual_startup_diagnostic_launched'] is False,'Actual current closed-original gate26 proof differs')
    b77=read(bundle['bound77']);report77,job77,inputs=report_cpu(b77,77,BOUND_WORKER,read,cpu,check,units)
    require(report77['groups']==dict(acquisition=19,cohorts=28,monitor=18,monitor_preparation=11,unchanged_final_ROM=1)
        and len(report77['selected_tests'])==len(set(report77['selected_tests']))==77,
        'All exact source-bound77 integration cases required')
    require(all(pin==inputs.get(pin['path']) for pin in selected.values()),'Selected source absent from actual bound77 inputs')
    source_migration(read(bundle['stage05_migration']),read(bundle['stage06_migration']),inputs,read)
    helper=inputs.get(str(E/'audit_pilot_evidence_score_carry_v2.py'))
    require(helper is not None and helper['sha256']=='f3b27dd4a5fb2b8f952467ac67781a846a4e21cd5a4fbe69a7a10e306300eb39',
            'Actual new b552 evidence helper required')
    package=read(bundle['package']);parent=read(package['parent_manifest']);grandparent=read(parent['parent_manifest'])
    require(package['root']==str(H/'profile06/Robotron') and count(package['source_count'],123)
        and set(package['files'])==set(parent['files'])==set(grandparent['files']) and len(package['files'])==123,
        'Complete exact123-source package lineage required')
    require({n for n in parent['files'] if parent['files'][n]!=grandparent['files'][n]}==
        {'Scripts/dqn/game_journal.py','tools/confirmed_terminal_evidence.py'}
        and {n for n in package['files'] if package['files'][n]!=parent['files'][n]}=={'Scripts/dqn/socket_server.py'}
        and package['files']['Scripts/dqn/socket_server.py']==SOCKET_SHA,'Only the tested journal/terminal/continuity deltas allowed')
    for name,sha in package['files'].items():
        pin=inputs.get(str(H/'profile06/Robotron'/name))
        require(pin is not None and pin['sha256']==sha,'Combined package file absent from actual original CPU scope')
        read(pin,False)
    b36=read(bundle['bound36']);plan36=read(b36['plan']);rows=b36['groups']
    require(b36['source_selected_for_science'] is False and count(b36['total_tests'],36)
        and b36['sequence_tool_exit']==0 and len(rows)==len(plan36['groups'])==36,
        'Every separate expensive original CPU group required')
    ids=[];group_counts={}
    for index,(row,spec) in enumerate(zip(rows,plan36['groups']),1):
        require(count(row['index'],index) and row['job']==spec['job'] and row['config']==spec['config']
            and row['name']==spec['name'],'Original expensive group/job/config order differs')
        report,job,source_inputs=report_cpu(row,1,BOUND_WORKER,read,cpu,check,units)
        require(source_inputs==inputs and report['group']==row['name'] and count(job['expected_tests'],1)
            and len(report['selected_tests'])==1,'Exact source-bound individual expensive case required')
        group=job['selection'][0]['group'];group_counts[group]=group_counts.get(group,0)+1
        ids.extend(report['selected_tests'])
    require(group_counts==dict(review=6,CPU_preparation=11,protection=10,campaign=9)
        and len(set(ids))==36 and not set(ids)&set(report77['selected_tests']), 'All112 distinct bound integration cases plus original-ROM rejection required')
    wire=read(bundle['wire56']);wp=read(wire['plan']);manifest=read(wire['original_manifest'])
    child=read(wire['original_child_result']);result=read(wire['original_parent_result'])
    wi=inventory(wp['inputs'],check);cfg=read(wire['config'])
    require(wp['source']==wire['source'] and wire['source']['path']==str(H/'prove_recent_START_on_actual_wire_v2.py')
        and wire['source']['sha256']=='bce346a069edcd308e8cd1003e32c7d6ae70e42192476ce6c03ce59633b647b9'
        and wire['source'] in wi.values() and wp['helper']==p18['source'],'Exact actual full-handler worker/helper required')
    cpu(wire['config'],wire['original_owner'],wire['original_closure'],wi,cfg['argv'],units)
    require(cfg['argv']==['/usr/bin/python3.12','-I','-B',wire['source']['path'],'--execute','--work',
        str(Path(cfg['output']).parent/'private-wire-probe'),'--package-source','confirmed'],'Actual original private full-handler command differs')
    work=Path(cfg['output']).parent/'private-wire-probe'
    for key,name in [('original_manifest','input.json'),('original_parent_result','result.json'),
                     ('original_child_result','child-result.json'),('candidate_socket','private/Scripts/dqn/socket_server.py')]:
        require(wire[key]['path']==str(work/name),'Full-handler result escaped its actual original work directory')
        read(wire[key],False)
    require(child['status']==result['status']=='PASS' and count(result['child_exit'],0)
        and count(len(child['cases']),56) and child['cases']==result['cases'] and result['input_manifest']==manifest
        and manifest['candidate_socket_sha256']==wire['candidate_socket']['sha256']==SOCKET_SHA
        and manifest['helper_sha256']==HELPER_SHA
        and manifest['base_package_sha256']==package['parent_manifest']['sha256'], 'Complete actual full-handler56 source/result joins required')
    carry=['million','two_million','ten_million','recent_million']
    other=['score_wrap','score_wrap_recent','wave_wrap','truncated_nonzero','zero_real_restart','zero_no_restart']
    variants={(case,replay,patched,torn) for case in carry for replay in [False,True]
              for patched in [False,True] for torn in [False,True]}
    variants|={(case,replay,patched,False) for case in other for replay in [False,True] for patched in [False,True]}
    require({(row['case'],row['replay'],row['patched'],row['torn']) for row in child['cases']}==variants,
            'Every actual full-handler variant is mandatory; duplicate rescue is forbidden')
    require(set(wire['original_journals'])=={f'{case}-{int(replay)}-{int(patched)}-{int(torn)}'
            for case,replay,patched,torn in variants},'Full-handler original journal scope differs')
    for label,journals in wire['original_journals'].items():
        for name,entry in journals['files'].items():
            require(name in ('games.jsonl','measurement_starts.jsonl')
                and entry['original']['path']==str(work/'journal'/label/name)
                and check(entry['original']) is True
                and entry['original']['sha256']==entry['readonly_archive']['sha256'],
                'An original full-handler journal changed or escaped its case')
            read(entry['readonly_archive'],False)
    parent_console=wire['consoles']['parent_stdout']
    require(parent_console['original']['path']==str(Path(cfg['output'])/'stdout.txt')
        and check(parent_console['original']) is True
        and parent_console['original']['sha256']==parent_console['readonly_archive']['sha256']
        and json.loads(read(parent_console['readonly_archive'],False).splitlines()[-1])==dict(status='PASS',cases=56,child_exit=0),
        'Actual original parent console does not rejoin the full-handler outcome')
    require(wire['corrected_semantics_equal_clean_trace'] is True and wire['corrected_replay_and_nstep_trace_equal_clean'] is True
        and wire['original849_recent_START_defect_reproduced'] is True and wire['old_nonrecent_carries_and_restarts_and_wraps_preserved'] is True
        and wire['physical_ROM_acceptance_proven'] is False and wire['source_selected_for_science'] is False,
        'Full-handler trace scope cannot grant physical ROM or scientific approval')
    for pin in selected.values():read(pin,False)
    return dict(status='COMBINED_PROFILE06_ORIGINAL_SOURCE_AND_CPU_CHAIN_VERIFIED',selected_sources=selected,
        baseline_source_tests=220,journal_regressions=34,primitive_regressions=18,current_closed_gate_tests=26,
        bound_integration_tests=113,full_handler_variants=56,additional_original_CPU_units=len(units)//2,
        package=bundle['package'],source_selected_for_science=False,candidate_captured=False,
        quality_qualified=False,learning_speed_gain_verified=False)
