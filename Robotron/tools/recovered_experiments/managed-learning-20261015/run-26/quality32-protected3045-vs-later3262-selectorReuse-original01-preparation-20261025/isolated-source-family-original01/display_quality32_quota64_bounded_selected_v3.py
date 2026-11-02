"""Project declared original quality receipts into dashboard files; no actions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

ORDER=('R1','C1','R2','C2')
FOLDERS=('01-reference','02-candidate','03-reference','04-candidate')
LABELS=('protected reference','candidate')

def read(path):
    try:
        if path.stat().st_size>16<<20:return {}
        return json.loads(path.read_bytes())
    except (FileNotFoundError,ProcessLookupError,json.JSONDecodeError):return {}

def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None

def alive(row):
    return type(row.get('pid'))is int and birth(row['pid'])==row.get('starttime_ticks',row.get('birth'))

def publish(path,value):
    temporary=path.with_name(path.name+'.next')
    with temporary.open('w')as stream:
        json.dump(value,stream,separators=(',',':'),allow_nan=False);stream.write('\n')
        stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o664)
    os.replace(temporary,path)

def terminal_zero(root,name):
    result=read(root/name)
    if result.get('actual_exit')!=0:return False
    closure=read(Path(result.get('closure',{}).get('path','/nonexistent-quality-display-closure')))
    return closure.get('original_exit')==0 and closure.get('lifecycle_complete')is True and closure.get('unit_released')is True

def project(root,index):
    folder=FOLDERS[index];directory=root/folder;native=read(directory/'diagnostic-output-original01/status.json')
    result=read(directory/'original-closed-display-summary.json')
    owner=read(directory/'execution-original01/root-original-identity.json')
    controller=read(directory/'controller-original-child.json')
    cpu_owner=read(directory/'independent-review-execution-original01/root-original-identity.json')
    report=result
    native_exit=read(directory/'controller-original-result.json');cpu_exit=read(directory/'independent-review-controller-original-result.json')
    loaded=read(directory/'diagnostic-output-original01/original-loaded-policy.json')
    policy=loaded.get('policy',{});control=native.get('controller',{})
    cohort=result.get('cohort')or control.get('cohort',{})
    count=cohort.get('count',0)
    data=dict(label=LABELS[index%2],
        count=count,started=cohort.get('started',0),pending=cohort.get('pending',0),
        expected_selected_games=64,games_per_slot=2,minimum_completed_games=50,
        mean=cohort.get('mean')if count else None,median=cohort.get('median')if count else None,
        se=cohort.get('se')if count else None,start_ts=cohort.get('start_ts'),close_ts=cohort.get('close_ts'),
        checkpoint_sha256=policy.get('checkpoint_sha256'),clocks={'learner_frame_count':policy.get('learner_frame_count')},
        valid=None,complete=False,phase='pending',reason=None,updated_unix_s=time.time())
    if (native_exit and native_exit.get('actual_exit')!=0)or(cpu_exit and cpu_exit.get('actual_exit')!=0)or report.get('valid')is False:
        state='failed';data.update(phase='invalid',valid=False,reason=report.get('error')or'Original execution/review failed; no retry')
    elif report.get('valid')is True and terminal_zero(directory,'controller-original-result.json')and terminal_zero(directory,'independent-review-controller-original-result.json'):
        state='finished';data.update(phase='finished',valid=True,complete=True)
    elif alive(cpu_owner):state='running';data.update(phase='independent_review',reason='Independent review in progress')
    elif alive(owner)or alive(controller):state='running';data['phase']=control.get('phase')or'warming'
    elif native_exit.get('actual_exit')==0:
        state='running';data.update(phase='awaiting_independent_review',reason='Native complete; independent review pending')
    elif owner or controller:
        state='unknown';data.update(phase='awaiting_terminal_receipt',reason='Original process no longer observed; terminal receipt pending')
    else:state='pending'
    publish(root/'display'/f'{folder}.json',data)
    return dict(index=index+1,role='reference'if index%2==0 else'candidate',state=state,
        evaluator_status_path=str(root/'display'/f'{folder}.json'),receipt_path=str(root/'display'/f'{folder}.json'))

PROJECTION_MAX_BYTES = 1 << 20

def projection_metadata(path):
    value = path.stat()
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
                mode=oct(value.st_mode & 0o777), uid=value.st_uid, nlink=value.st_nlink)

def projection_owned_file(path):
    return (path.is_absolute() and path.resolve() == path and path.is_file()
            and projection_metadata(path)['mode'] == '0o444'
            and projection_metadata(path)['uid'] == os.getuid()
            and projection_metadata(path)['nlink'] == 1)

def projection_read(path, pin=None):
    if not projection_owned_file(path):
        raise ValueError('Display requires an owned immutable original receipt')
    before = projection_metadata(path)
    if before['bytes'] > PROJECTION_MAX_BYTES:
        raise ValueError('Display summary exceeds the bounded receipt limit')
    if pin is not None and (pin['path'] != str(path) or pin['bytes'] != before['bytes']
                            or pin['identity'] != before):
        raise ValueError('Original receipt identity differs')
    raw = path.read_bytes()
    if len(raw) != before['bytes'] or projection_metadata(path) != before:
        raise ValueError('Original receipt changed while reading')
    if pin is not None and hashlib.sha256(raw).hexdigest() != pin['sha256']:
        raise ValueError('Original receipt digest differs')
    result = json.loads(raw)
    if type(result) is not dict:
        raise ValueError('Original receipt must be an object')
    return result

def project_campaign(root):
    """Return a terminal display projection, or None while evidence is pending.

    The complete assessment's identity is checked against the original closed
    outcome. Its contents are deliberately not rehashed or parsed every poll.
    Scientific validity remains the responsibility of the original assessor,
    sequencer and independent closeout, never this display-only projection.
    """
    try:
        outcome = projection_read(root / 'original-fresh-sequence-observer-original01-outcome.json')
        if outcome['schema'] != 'robotron-original-certified-quality32-sequence-outcome-v1':
            return None
        precommit = projection_read(root / 'original-fresh-sequence-precommit.json', outcome['precommit'])
        if precommit['schema'] != 'robotron-fresh-LR125-quality32-sequence-precommit-v1':
            return None
        if (type(outcome['original_attempts_per_leg']) is not int or outcome['original_attempts_per_leg'] != 1
                or outcome['no_retries'] is not True or outcome['existing_R1_adopted'] is not False
                or type(outcome['quality_qualified']) is not bool):
            return None
        if outcome['status'] in ('ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY', 'SEQUENCING_STOPPED_NO_NEW_ACTIONS'):
            if outcome['quality_qualified'] is not False:
                return None
            return dict(state='failed', outcome='invalid',
                        reason=str(outcome.get('error') or outcome.get('reason') or 'Original sequence stopped; no retry')[:2000])
        if outcome['status'] != 'ORIGINAL_FOUR_LEG_CAMPAIGN_COMPLETE':
            return None
        controller = projection_read(root / 'campaign-assessment-controller-original-result.json',
                                     outcome['campaign_assessment']['result'])
        if type(controller['actual_exit']) is not int or controller['actual_exit'] != 0:
            return None
        if controller['closure'] != outcome['campaign_assessment']['closure']:
            return None
        closure = projection_read(root / 'campaign-assessment-execution-original01/root-original-result-and-owned-release.json',
                                  controller['closure'])
        if (type(closure['original_exit']) is not int or closure['original_exit'] != 0
                or closure['lifecycle_complete'] is not True or closure['unit_released'] is not True):
            return None
        report = root / 'independent-campaign-assessment-original01/assessment.json'
        pin = outcome['assessment_report']
        if (pin['path'] != str(report) or not projection_owned_file(report)
                or pin['bytes'] != report.stat().st_size or pin['identity'] != projection_metadata(report)):
            return None
        return dict(state='finished', outcome='qualified' if outcome['quality_qualified'] else 'not_improved', reason=None)
    except (OSError, ValueError, KeyError, TypeError):
        return None

def main():
    global LABELS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true');parser.add_argument('--campaign');parser.add_argument('--readiness-sha256')
    args=parser.parse_args()
    if not args.run:print('PLAN_ONLY');return 0
    root=Path(args.campaign);ready=root/'new-original-quality-launch-readiness.json'
    assert root.is_absolute()and root.resolve()==root and hashlib.sha256(ready.read_bytes()).hexdigest()==args.readiness_sha256
    assert read(ready)['campaign_directory']==str(root)
    declared=read(ready);pair=read(Path(declared['quality_pair']['path']))
    LABELS=tuple(f"{pair[role]['saved_clocks']['learner_frame_count']/1e6:.1f}M {role}"for role in ('reference','candidate'))
    assert declared['display_source']['sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    intent=root/'display-observer-original-intent.json'
    with intent.open('x')as stream:
        json.dump(dict(pid=os.getpid(),birth=birth(os.getpid()),source=str(Path(__file__).resolve()),
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            readiness_sha256=args.readiness_sha256,read_only_science=True,created_unix_s=time.time()),stream,indent=2)
        stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(observer_pid=os.getpid(),birth=birth(os.getpid()),intent=str(intent))),flush=True)
    deadline=time.monotonic()+100000
    while time.monotonic()<deadline:
        legs=[project(root,index)for index in range(4)]
        current=next((row['index']for row in legs if row['state']in ('running','unknown','failed')),None)
        state='running'if current else'prepared';outcome=None;reason=None
        if any(row['state']=='failed'for row in legs):state='failed';outcome='invalid';reason='Original leg failed; no retry'
        projection=project_campaign(root)
        if projection is not None:
            state=projection['state'];outcome=projection['outcome'];reason=projection['reason']
            if state=='finished':current=None
        elif all(row['state']=='finished'for row in legs):state='running';reason='All legs reviewed; final campaign assessment pending';current=4
        publish(root/'status.json',dict(state=state,current_leg=current,total_legs=4,legs=legs,
            updated_unix_s=time.time(),outcome=outcome,reason=reason))
        if state in ('finished','failed'):return 0
        time.sleep(5)
    publish(root/'display-observer-deadline.json',dict(state='observer_deadline',original_science_not_restarted=True,unix_s=time.time()))
    return 1

if __name__=='__main__':raise SystemExit(main())
