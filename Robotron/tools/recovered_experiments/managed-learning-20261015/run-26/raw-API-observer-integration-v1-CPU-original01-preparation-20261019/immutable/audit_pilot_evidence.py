"""Read-only evidence helpers for the future standalone 32-actor pilot.

These do not launch a pilot, certify its service lifecycle, compare capacities,
qualify a policy, or publish anything. The caller must separately bind the exact
prepared job, source package, checkpoint, original owner/exit, main-trainer holds
and owned cleanup. No current quality implementation imports this proposal. The corrected-source
caller must first prove all handler AST outside the score-dip helper is unchanged,
so the existing exact unused-expert branch proof still applies.
"""
import hashlib
import math
from pathlib import Path
import re
import statistics


SLOTS=list(range(4096,4128))
HANDLER_SHA='84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40'


def require(value,message):
    if not value:raise ValueError(message)


def original_games(receipt,directory,backend,auditor):
    """Rebuild all admissions and full tails from both original journal files."""
    directory=Path(directory)
    require(type(receipt['job']['actors']) is int and receipt['job']['actors']==32
        and receipt['job']['actor_slots']==SLOTS,'Only the explicit32-slot pilot is in scope')
    proof=backend.validate_original_backend(receipt,directory,verify_checkpoint=True)
    paths={name:directory/'journal'/name for name in ('games.jsonl','measurement_starts.jsonl')}
    payloads={name:path.read_bytes() for name,path in paths.items()}
    journal=auditor.lines(payloads['games.jsonl']);starts=auditor.lines(payloads['measurement_starts.jsonl'])
    games=auditor.indexed(journal,'original games');registry=auditor.indexed(starts,'original starts')
    admitted={key:entry for key,entry in registry.items()
        if entry.get('experiment')==receipt['label']
        and receipt['start_ts']<=entry['start_unix_s']<=receipt['close_ts']}
    rows=auditor.indexed(receipt['rows'],'receipt games')
    require(len(admitted)>=50 and set(rows)==set(admitted)
        and set(admitted)<=set(games),'Every original admitted full tail is required')
    raw_candidates={row['journal_game_id'] for row in journal
        if row.get('known_start') is True and row.get('measurement_active') is True
        and row.get('experiment')==receipt['label']
        and receipt['start_ts']<=row['start_unix_s']<=receipt['close_ts']}
    require(raw_candidates==set(admitted),'Original admission registry and game journal disagree')
    clients={slot:set() for slot in SLOTS};rom=[]
    for identifier,entry in admitted.items():
        row=games[identifier]
        require(row==rows[identifier],'Receipt changed an original full game')
        require(entry.get('known_start') is True and entry.get('measurement_active') is True
            and entry.get('measurement_generation')==receipt['generation'],
            'Unknown, nonmeasurement or foreign-generation admission')
        for key in ('client_id','client_slot','game_uid','start_utc','start_unix_s',
                    'start_reason','known_start','measurement_active','measurement_generation','start_frame'):
            require(entry[key]==row[key],f'Original admission/outcome identity differs: {key}')
        auditor.validate_original_context(entry,row)
        require(type(row['score']) is int and row['score']>=0,'Original integer full-game score required')
        require(type(row['client_id']) is int and type(row['client_slot']) is int
            and row['client_slot'] in clients,'Exact integer private client/slot required')
        clients[row['client_slot']].add(row['client_id'])
        rom.append(auditor.validate_rom_terminal(row,receipt['terminal_successors'][identifier]))
    require(all(len(value)==1 for value in clients.values()),'Every slot must retain one original client')
    mapped=set.union(*clients.values())
    require(len(mapped)==32 and mapped==set(receipt['boundary']['acknowledged_client_ids']),
        'Original32-slot/client boundary mapping differs')
    cohort=receipt['cohort']
    require(len(cohort['started_ids'])==len(admitted)
        and set(cohort['started_ids'])==set(admitted) and cohort['started_actor_slots']==SLOTS,
        'Full original cohort registry required')
    scores=[row['score'] for row in rows.values()]
    stats=dict(count=len(scores),started=len(scores),mean=statistics.mean(scores),
        median=statistics.median(scores),sd=statistics.stdev(scores),
        se=statistics.stdev(scores)/math.sqrt(len(scores)))
    for source in (receipt,cohort):
        for key,value in stats.items():
            actual=source[key]
            require(type(actual) in (int,float) and math.isfinite(actual)
                and math.isclose(actual,value,rel_tol=1e-12,abs_tol=1e-9),
                f'Saved {key} differs from every original game')
    for key in ('training_steps','optimized_samples','learner_frame_count'):
        require(type(receipt['clocks'][key]) is int
            and receipt['clocks'][key]==receipt['checkpoint_metadata'][key],
            'Frozen checkpoint clock metadata differs')
    require(all(hashlib.sha256(paths[name].read_bytes()).digest()==hashlib.sha256(raw).digest()
        for name,raw in payloads.items()),'Original journals changed during independent review')
    return dict(status='PASS_ORIGINAL_GAMES_AND_ROM_ONLY',statistics=dict(stats,score_sum=sum(scores)),
        original_game_ids=sorted(rows),original_terminal_readback=proof['original_terminal_readback'],
        rom_game_over_evidence=dict(status='PASS',verified_games=len(rom),links=rom),
        quality_qualified=False,promotion=False)


def actor_logs(receipt,directory,auditor):
    """Reconstruct timeouts and classify final actor logs, including slot4127."""
    require(receipt['job']['actors']==32 and receipt['job']['actor_slots']==SLOTS,'Explicit32-slot pilot required')
    cutoff=receipt['timeout_snapshot_unix_s']
    require(type(cutoff) in (int,float) and math.isfinite(cutoff)
        and cutoff>=max(row['end_unix_s'] for row in receipt['rows']),
        'Cleanup validity cutoff precedes an admitted full tail')
    result={}
    for slot in SLOTS:
        key=str(slot);path=Path(directory)/'actors'/key/'console.log';raw=path.read_bytes()
        text=raw.decode(errors='replace');lines=text.splitlines()
        events=[int(match[1]) if match else None
            for line in lines if '[SOCKET ACTION TIMEOUT]' in line
            for match in [re.search(r'\bunix_s=(\d+)\b',line)]]
        before=receipt['actor_timeout_logs_before_shutdown'][key]
        require(type(before) is int and 0<=before<=len(events),'Original before-shutdown timeout count differs')
        measured=max(before,sum(index<before or ts is None or ts<=int(cutoff)
            for index,ts in enumerate(events)))
        require(type(receipt['actor_timeout_logs'][key]) is int
            and measured==receipt['actor_timeout_logs'][key]==0,'Measured or missing-time runtime timeout')
        require(len(events)==receipt['actor_timeout_logs_after_shutdown'][key]
            and len(events)-measured==receipt['actor_cleanup_timeout_logs'][key],
            'Final original timeout accounting differs')
        allowed,issues=auditor.classify_actor_lines(lines,
            f"socket.{receipt['job']['host']}:{receipt['job']['port']}",cutoff,before,measured)
        require(not issues,f'Unclassified actor{slot} log issue: {issues}')
        observed=[dict(zip(('pid','fd','port','interval_us'),map(int,values))) for values in re.findall(
            r'\[robotron-socket-wait\] pid=(\d+) fd=(\d+) port=(\d+) interval_us=(\d+)',text)]
        owner=receipt['socket_wait']['actors'][key]
        require(any(row['pid']==owner['pid'] and row['port']==receipt['job']['port']
            and row['interval_us']==receipt['job']['wait_us'] for row in observed),
            'Missing original exact owned actor pacing activation')
        require(path.read_bytes()==raw,'Actor log changed during closed review')
        result[key]=dict(runtime=measured,cleanup=len(events)-measured,allowed_lines=allowed,
            original_sha256=hashlib.sha256(raw).hexdigest())
    return dict(status='PASS_ORIGINAL_ACTOR_LOGS_ONLY',slots=result,quality_qualified=False,promotion=False)


def console_lines(text,receipt,game,auditor,*,unused_expert_proof_validated=False):
    """Narrow source-bound diagnostics; no generic warning/error suppression."""
    require(receipt['job']['actors']==32 and receipt['job']['actor_slots']==SLOTS
        and receipt.get('valid') is True and receipt.get('complete') is True
        and receipt.get('server_error') is None and receipt.get('inference_error') is None
        and receipt.get('cleanup_errors')==[], 'Only a complete otherwise-valid32-slot receipt')
    require(receipt['timeout_snapshot_unix_s']>=max(row['end_unix_s'] for row in receipt['rows']),
        'Cleanup cutoff lacks a completed full tail')
    lines=text.splitlines();traceback_lines=set();flagged=[]
    stopped=r'Inference batcher (?:stopped before (?:completion|dispatch)|is stopped)'
    cleanup=re.compile(r'(?:Client \d+ error: |RuntimeError: )'+stopped+r'$')
    eof=re.compile(r'Client \d+ disconnected: (?:EOF|Broken payload)$')
    for index,line in enumerate(lines):
        if line!='Traceback (most recent call last):':continue
        stop=index+1
        while stop<len(lines) and lines[stop].startswith((' ','\t')):stop+=1
        frames=[entry for entry in lines[index+1:stop] if entry.lstrip().startswith('File ')]
        expected=str(Path(game)/'Scripts/dqn/socket_server.py')
        if (stop<len(lines) and cleanup.fullmatch(lines[stop]) and len(frames)==2
            and re.fullmatch(r'  File "'+re.escape(expected)+r'", line \d+, in handle_client',frames[0])
            and re.fullmatch(r'  File "'+re.escape(expected)+r'", line \d+, in infer',frames[1])):
            traceback_lines.update(range(index+1,stop+2))
    def zero(value):return type(value) in (int,float) and value==0
    job=receipt['job'];rows=receipt['rows']
    greedy=(job.get('completion_policy')=='confirmed_reset_reserves_v1'
        and job.get('game_boundary_diagnostics') is True and zero(job.get('expert_ratio'))
        and zero(job.get('epsilon')) and bool(rows)
        and all(row.get('eval_only') is True and row.get('measurement_active') is True
            and all(zero(row.get(context,{}).get(field)) for context in ('start_context','end_context')
                    for field in ('epsilon','expert_ratio')) for row in rows))
    for number,line in enumerate(lines,1):
        if not re.search(r'Traceback|\b\w*(?:Error|Exception)\b|\bfailed\b|\bfallback\b|\bunavailable\b|\bdisconnected\b|param mismatch|\[INGEST\] dropped implausible',line,re.I):continue
        if cleanup.fullmatch(line) or number in traceback_lines:kind='owned_post_cutoff_batcher_shutdown'
        elif eof.fullmatch(line):kind='owned_shutdown_EOF_after_valid_full_tail'
        elif (number==2 and line==auditor.OPTIONAL_EXPERT_WARNING and unused_expert_proof_validated is True
            and receipt['source_hashes'].get('Scripts/dqn/socket_server.py')==HANDLER_SHA and greedy):
            kind='same_proven_unused_expert_branch_under_explicit32_slot_greedy_controls'
        else:raise ValueError(f'Unclassified evaluator log issue at line{number}: {line}')
        flagged.append(dict(line_number=number,text=line,classification=kind))
    return flagged
