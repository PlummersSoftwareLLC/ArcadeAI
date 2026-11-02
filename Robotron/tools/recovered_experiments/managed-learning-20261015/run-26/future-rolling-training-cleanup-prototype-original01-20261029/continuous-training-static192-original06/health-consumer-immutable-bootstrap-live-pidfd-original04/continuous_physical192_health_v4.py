"""Prospective read-only original192 continuous-main census; no import-time IO.

Only a separately Root-bound, completed original192 physical bootstrap is
accepted. This module cannot launch, repair, stop or adopt a replacement.
"""
import hashlib
import importlib.util
import json
import mmap
import stat
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
LINUX=ROOT/'tools/quality_capacity_proposal/supervised_main_fleet_v2.py'
LINUX_SHA='1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'
STATIC=('parent_pid','cgroup','command','environment','affinity','uids','executable')
REGISTRY=Path(__file__).with_name('continuous_physical192_registry_v4.py')
REGISTRY_SHA='4bd2cd67c68a908a44c984f00f2586cd7116e6fb2ab4cf53ad8037dd2052b8a2'

def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def linux():
    require(hashlib.sha256(LINUX.read_bytes()).hexdigest() == LINUX_SHA, 'Linux reader changed')
    spec = importlib.util.spec_from_file_location('_round_health_linux', LINUX)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def birth(process):
    return process['pid'], process['starttime_ticks']


def process_record(pid, reader):
    result = reader.process_record(pid)
    # Also bind DQN and CUDA recipe settings; omit unrelated environment data.
    environment = Path('/proc', str(pid), 'environ').read_bytes()
    for item in environment.split(b'\0'):
        if b'=' not in item:
            continue
        key, value = item.split(b'=', 1)
        name = key.decode()
        if name.startswith('DQN_') or name in ('CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER'):
            result['environment'][name] = value.decode()
    stat = reader.process_stat(pid)
    require(stat is not None and stat['starttime_ticks'] == result['starttime_ticks'], 'Process raced capture')
    result['state'] = stat['state']
    return result


def unit_record(name, reader):
    raw = subprocess.check_output(['systemctl', '--user', 'show', name], text=True, timeout=5)
    values = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    require(values['ActiveState'] == 'active' and values['SubState'] == 'running'
            and values['NRestarts'] == '0', 'Main unit stopped or restarted')
    process = process_record(int(values['MainPID']), reader)
    require(process['cgroup'] == values['ControlGroup'], 'Main unit cgroup differs')
    return dict(unit=name, invocation=values['InvocationID'], process=process, raw_show=raw)


def file_identity(path):
    return stat_identity(path.stat())


def stat_identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(info.st_mode & 0o777), uid=info.st_uid, nlink=info.st_nlink)


def check_inputs(case, full=False):
    for path, value in case['inputs'].items():
        actual = Path(path)
        require(str(actual.resolve(strict=True)) == path and not actual.is_symlink()
                and file_identity(actual) == value['identity'], 'Held input identity changed: ' + path)
        if full:
            with actual.open('rb') as stream:
                info = os.fstat(stream.fileno())
                require(stat.S_ISREG(info.st_mode) and stat_identity(info) == value['identity'],
                        'Held source must remain the selected regular file: ' + path)
                if info.st_size:
                    with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
                        digest = hashlib.sha256(view).hexdigest()
                else:
                    digest = hashlib.sha256(b'').hexdigest()
                require(digest == value['sha256'], 'Held input bytes changed: ' + path)
                require(not actual.is_symlink() and file_identity(actual) == value['identity']
                        and stat_identity(os.fstat(stream.fileno())) == value['identity'],
                        'Held input changed during full hash: ' + path)


def validate_optimizer_accounting(value):
    """One admitted update may be in flight; unknown outcomes never qualify."""
    require(value['schema'] == 'robotron-optimizer-exposure-v1' and value['enabled'] is True,
            'Optimizer accounting disabled or foreign')
    names = ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable')
    total, epoch = value['total'], value['since_epoch']
    for counters in (total, epoch):
        require(all(type(counters.get(name)) is int and counters[name] >= 0 for name in names)
                and counters['unavailable'] == 0
                and counters['outcomes_recorded'] == counters['applied'] + counters['amp_skipped'],
                'Unknown or inconsistent optimizer outcomes')
    pending = total['attempts_started'] - total['outcomes_recorded']
    require(pending in (0, 1)
            and epoch['attempts_started'] - epoch['outcomes_recorded'] == pending
            and all(epoch[name] <= total[name] for name in names)
            and epoch['outcomes_recorded'] > 0
            and type(value['unclassified_started_total']) is int
            and value['unclassified_started_total'] == pending
            and type(value['available']) is bool and value['available'] is (pending == 0),
            'Optimizer in-flight accounting differs')
    return pending


def registry():
    require(hashlib.sha256(REGISTRY.read_bytes()).hexdigest() == REGISTRY_SHA,
            'Exact selected static192 registry verifier required')
    import sys
    name = '_prospective_immutable_bootstrap_pidfd_registry_v4'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, REGISTRY)
        value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
        sys.modules[name] = value
    return sys.modules[name]


class CensusFailure(ValueError):
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.raw_snapshot = dict(schema='robotron-rejected-continuous-static192-census-v1', evidence=evidence)


def stable_round_status(value):
    # Operational TRAIN quarantine/counters do not change physical ownership.
    fields=('schema','mode','epoch','supervisor','trainer','rolemap','source_authority',
            'original_membership','initial_admission')
    result={key:value[key] for key in fields}
    result['slots']={slot:{key:row[key] for key in ('eval_only','incarnation',
        'original_pid','original_birth','original_slot_sha256')} for slot,row in value['slots'].items()}
    return result


def observed_counts(sample):
    """Report physical presence only; complete state counts require validate()."""
    roles=sample['status']['slots'];actors=sample['actors']
    return dict(total=192,active_train=sum(slot in actors and not row['eval_only'] for slot,row in roles.items()),
        present_eval=sum(slot in actors and row['eval_only'] for slot,row in roles.items()),
        absent_eval=sum(slot not in actors and row['eval_only'] for slot,row in roles.items()),
        closed_eval=None,retiring_eval=None,typed_partition_required_for_retirement_counts=True)


def read_status(path):
    path = Path(path)
    require(path.resolve(strict=True) == path and not path.is_symlink(), 'Canonical publisher path required')
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
                and before.st_size <= 524288, 'Bounded actual normal publisher snapshot required')
        raw = stream.read(524289)
        require(len(raw) <= 524288 and stat_identity(before) == stat_identity(os.fstat(stream.fileno()))
                and stat_identity(before) == file_identity(path), 'Atomic publisher changed during capture')
    return raw, json.loads(raw)


def get(path):
    before = time.monotonic_ns()
    with urllib.request.urlopen('http://127.0.0.1:8771' + path, timeout=2) as response:
        raw = response.read(1_048_577)
    require(len(raw) <= 1_048_576, 'API body exceeds declared bound')
    after = time.monotonic_ns()
    return dict(path=path, before_monotonic_ns=before, after_monotonic_ns=after,
                raw_wire=raw.decode('utf-8'), sha256=hashlib.sha256(raw).hexdigest(), value=json.loads(raw))


def probe(pid, reader):
    before = time.monotonic()
    value = reader.process_stat(pid)
    return dict(pid=pid, path=str(Path('/proc', str(pid), 'stat')),
                before_monotonic_s=before, after_monotonic_s=time.monotonic(),
                absent=value is None, current_birth=None if value is None else value['starttime_ticks'],
                state=None if value is None else value['state'])


def raw_identity(pid):
    value = dict(pid=pid)
    for name in ('stat', 'cmdline', 'cgroup'):
        try:
            with Path('/proc', str(pid), name).open('rb') as stream:
                raw = stream.read(65537)
            value[name] = dict(raw=raw[:65536].decode('utf-8', 'backslashreplace'), truncated=len(raw) > 65536)
        except OSError as error:
            value[name] = dict(error=repr(error))
    return value


def read_producer_prefix(path, maximum):
    path=Path(path)
    require(path.is_absolute() and path.resolve(strict=True)==path and not path.is_symlink(),
            'Exact append-only journal path required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=stat_identity(os.fstat(fd))
        require(stat.S_ISREG(os.fstat(fd).st_mode) and before['uid']==os.getuid()
                and before['nlink']==1 and 0<=before['bytes']<=maximum,
                'Bounded owned ordinary journal required')
        with os.fdopen(os.dup(fd),'rb') as stream:raw=stream.read(before['bytes'])
        after=stat_identity(os.fstat(fd));actual=file_identity(path)
        fixed=('device','inode','mode','uid','nlink')
        require(len(raw)==before['bytes'] and all(before[k]==after[k]==actual[k] for k in fixed)
                and after['bytes']>=before['bytes'] and actual['bytes']>=before['bytes'],
                'Ordinary journal replaced/shrunk during bounded prefix capture')
        return raw,before
    finally:os.close(fd)


def collect_eval_evidence(case, previous=None, prefix_capture=None):
    root=Path(case['continuous']['eval_journal_directory'])
    retirement=root/'completed_clients.jsonl';main=root/'games.jsonl'
    began=time.monotonic();prefix,prefix_raw=registry().completed_prefix(case)
    raw,retirement_id=read_producer_prefix(retirement,262144)
    require(all(retirement_id[k]==v for k,v in prefix['canonical_identity'].items())
            and len(raw)>=prefix['prefix_bytes'] and raw[:prefix['prefix_bytes']]==prefix_raw,
            'Current completed journal replaced/truncated/changed its held historical prefix')
    suffix=raw[prefix['prefix_bytes']:]
    require(not suffix or suffix.endswith(b'\n'), 'Uncommitted EVAL retirement tail')
    lines=suffix.splitlines(keepends=True);require(len(lines)<=37,'More than37 original EVAL retirements')
    if prefix_capture is not None:
        prefix_capture.update(record=case['continuous']['completed_clients_prefix'],
            canonical_path=str(retirement),canonical_identity=retirement_id,
            raw_prefix_wire=prefix_raw.decode(),prefix_bytes=prefix['prefix_bytes'],
            prefix_sha256=prefix['prefix_sha256'],before_monotonic_s=began,after_monotonic_s=time.monotonic())
    old={} if previous is None else previous.get('EVAL_journal_evidence',{})
    entries={};new=[];seen=set();offset=prefix['prefix_bytes']
    for line in lines:
        row=json.loads(line);slot=str(row['client_slot'])
        require(type(row['client_slot']) is int and slot in case['slot_eval']
                and case['slot_eval'][slot] is True and row['eval_only'] is True
                and slot not in seen,'Unknown/duplicate/non-EVAL ordinary retirement row')
        seen.add(slot)
        text=line.decode();digest=hashlib.sha256(line).hexdigest()
        if slot in old:
            require(old[slot]['raw_line']==text and old[slot]['raw_line_sha256']==digest,
                    'An original committed EVAL natural row changed')
            entries[slot]=old[slot]
        else:new.append((slot,line,offset))
        offset+=len(line)
    require(set(old)<=set(entries)|{slot for slot,_,_ in new},'Original EVAL retirement journal lost a prior row')
    if new:
        main_raw,main_id=read_producer_prefix(main,16<<20)
        for slot,line,retirement_offset in new:
            at=main_raw.find(line)
            require(at>=0 and main_raw.find(line,at+1)<0 and (at==0 or main_raw[at-1:at]==b'\n'),
                    'Retirement is not one exact committed ordinary main journal line')
            now=time.time();mono=time.monotonic()
            entries[slot]=dict(schema='robotron-independent-original-EVAL-journal-evidence-v1',
                raw_line=line.decode(),raw_line_sha256=hashlib.sha256(line).hexdigest(),
                main_raw_line=line.decode(),retirement_raw_line=line.decode(),
                main_path=str(main),retirement_path=str(retirement),
                main_prefix_identity=main_id,main_line_offset=at,
                retirement_prefix_identity=retirement_id,retirement_line_offset=retirement_offset,
                first_observed_unix_s=now,first_observed_monotonic_s=mono)
    return entries


def collect_eval_cleanup(case, natural_evidence, absence):
    from urllib.parse import quote
    result={}
    for slot in natural_evidence:
        if slot not in absence:continue
        row=case['continuous']['original_slots'][slot]
        conn=registry().binding(case,slot,row['connection_binding'],row['original_child'])
        result[slot]=get('/api/connection_cleanup_token?token='+quote(conn['token'],safe=''))
    return result


def collect_eval_kernel_receipts(case, capture):
    selected=case['continuous'].get('eval_exit_witness');result={}
    if selected is None:return result
    publication=capture['publication']['value']
    for slot,value in publication['exit_receipts'].items():
        require(slot in case['slot_eval'] and case['slot_eval'][slot] is True
                and Path(value['path'])==Path(selected['output'])/('exit-slot-%03d.json'%int(slot)),
                'Unknown/non-EVAL/misnamed published kernel receipt')
        registry().read_pin(value)
        result[slot]=value
    return result


def pidfd_descriptor(path):
    value=os.stat(path)
    return dict(device=value.st_dev,inode=value.st_ino,mode=oct(value.st_mode),uid=value.st_uid)


def read_pidfd_info(path):
    with Path(path).open('rb') as stream:
        raw=stream.read(16385)
    require(len(raw)<=16384,'Bounded actual pidfd fdinfo required')
    text=raw.decode('ascii')
    require(all(32<=ord(ch)<=126 or ch in '\t\n' for ch in text), 'Kernel pidfd info must be printable ASCII fields')
    return text


def collect_keeper_descriptors(case, publication, reader, owner_before):
    """Fresh read-only evidence of the selected keeper's original held FDs."""
    selected=case['continuous']['eval_exit_witness'];anchors=registry().read_pin(selected['anchors'])
    slots={slot for slot,role in case['slot_eval'].items() if role}-set(publication['exit_receipts'])
    begin=time.monotonic_ns();rows={};pid=selected['holder']['pid']
    for slot in sorted(slots,key=int):
        anchor=anchors['originals'][slot];number=anchor['fd_number']
        require(type(number)is int and number>=0,'Exact original pidfd number required')
        fd=Path('/proc',str(pid),'fd',str(number));info=Path('/proc',str(pid),'fdinfo',str(number))
        started=time.monotonic_ns()
        before=pidfd_descriptor(fd);link_before=os.readlink(fd);raw_before=read_pidfd_info(info)
        raw_after=read_pidfd_info(info);link_after=os.readlink(fd);after=pidfd_descriptor(fd)
        rows[slot]=dict(fd_number=number,path=str(fd),fdinfo_path=str(info),
            descriptor_before=before,descriptor_after=after,link_before=link_before,link_after=link_after,
            raw_fdinfo_before=raw_before,raw_fdinfo_after=raw_after,
            before_monotonic_ns=started,after_monotonic_ns=time.monotonic_ns())
    owner_after=unit_record(selected['holder']['unit'],reader)
    return dict(schema='robotron-fresh-original37-keeper-pidfd-census-v4',
        before_monotonic_ns=begin,after_monotonic_ns=time.monotonic_ns(),
        owner_before=owner_before,owner_after=owner_after,descriptors=rows)


def validate_keeper_descriptors(case,sample,capture):
    """Descriptor continuity is liveness evidence, never normal-exit evidence."""
    reg=registry();selected=case['continuous']['eval_exit_witness'];anchors=reg.read_pin(selected['anchors'])
    value=capture['descriptor_census'];published=capture['publication']['value']['exit_receipts']
    unresolved={slot for slot,role in case['slot_eval'].items() if role}-set(published)
    require(value['schema']=='robotron-fresh-original37-keeper-pidfd-census-v4'
            and set(value['descriptors'])==unresolved
            and sample['capture_started_monotonic_s']*1e9<=value['before_monotonic_ns']
            <=value['after_monotonic_ns']<=sample['capture_ended_monotonic_s']*1e9
            and 0<=sample['monotonic_s']-value['before_monotonic_ns']/1e9<=2,
            'Actual selected keeper FD census is missing, stale or unbracketed')
    for owner in (value['owner_before'],value['owner_after']):
        reg.owner_join(selected['holder'],owner)
        process=owner['process'];command=process['command']
        require(process['uids']==[os.getuid()]*4 and process['state']not in('T','t','Z','X','x')
                and selected['source']['path'] in command and selected['source']['sha256'] in command
                and selected['selection']['path'] in command and selected['selection']['sha256'] in command,
                'Original selected keeper process/source/selection changed')
    require(capture['holder']==value['owner_before']
            and all(value['owner_before']['process'][key]==value['owner_after']['process'][key]
                    for key in ('pid','starttime_ticks',*STATIC)),
            'Original keeper identity changed across descriptor census')
    seen=set();seen_fds=set()
    for slot,row in value['descriptors'].items():
        anchor=anchors['originals'][slot];original=anchor['original'];descriptor=anchor['descriptor']
        require(row['fd_number']==anchor['fd_number']
                and row['path']==str(Path('/proc',str(selected['holder']['pid']),'fd',str(anchor['fd_number'])))
                and row['fdinfo_path']==str(Path('/proc',str(selected['holder']['pid']),'fdinfo',str(anchor['fd_number'])))
                and all(type(descriptor[key])is int for key in ('device','inode','uid'))
                and descriptor['inode']>0 and descriptor['uid']==0 and descriptor['mode']=='0o700'
                and row['descriptor_before']==row['descriptor_after']==descriptor
                and row['link_before']==row['link_after']=='anon_inode:[pidfd]'
                and value['before_monotonic_ns']<=row['before_monotonic_ns']
                <=row['after_monotonic_ns']<=value['after_monotonic_ns'],
                'Selected original pidfd inode/number/type or capture bracket changed')
        pair=(descriptor['device'],descriptor['inode'])
        require(pair not in seen and row['fd_number']not in seen_fds,'Duplicate selected pidfd descriptor/number')
        seen.add(pair);seen_fds.add(row['fd_number'])
        for raw in (row['raw_fdinfo_before'],row['raw_fdinfo_after']):
            require(type(raw)is str and len(raw.encode('ascii'))<=16384
                    and all(32<=ord(ch)<=126 or ch in '\t\n' for ch in raw), 'Bounded kernel ASCII pidfd info required')
            lines=[line.split(':',1)for line in raw.splitlines()if ':' in line]
            fields={key:body.strip()for key,body in lines}
            require(len(fields)==len(lines) and int(fields['ino'])==descriptor['inode']
                    and int(fields['Pid']) in (original['pid'],-1)
                    and fields['NSpid'].split()==[fields['Pid']],
                    'Original pidfd raw inode/target/namespace changed')
            if slot in sample['actors']:
                require(int(fields['Pid'])==original['pid'], 'Live original EVAL lacks its held pidfd target')
        # Pid=-1 never proves exit status. kernel_eval_exit still requires an
        # authenticated published raw80 EXITbit+normal0 and actual birth absence.


def collect_eval_holder(case, reader):
    selected=case['continuous'].get('eval_exit_witness')
    if selected is None:return None
    terminal=Path(selected['output'])/'holder-terminal.json'
    started=time.monotonic_ns()
    if terminal.exists():
        before=file_identity(terminal);raw=terminal.read_bytes()
        require(file_identity(terminal)==before,'Kernel terminal publication changed')
        published=dict(path=str(terminal),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)
        value=registry().read_pin(published)
        return dict(state='ALL37_IMMUTABLE_EXIT_RECEIPTS_PUBLISHED',holder=None,descriptor_census=None,
            publication=dict(kind='COMPLETE_TERMINAL_PUBLICATION',immutable_pin=published,
                before_monotonic_ns=started,after_monotonic_ns=time.monotonic_ns(),
                raw_wire=raw.decode(),sha256=hashlib.sha256(raw).hexdigest(),value=value))
    owner=unit_record(selected['holder']['unit'],reader)
    raw,value=read_status(str(Path(selected['output'])/'holder-live.json'))
    require(len(raw)<=128<<10,'Bounded live keeper publication required')
    descriptors=collect_keeper_descriptors(case,value,reader,owner)
    return dict(state='HOLDING_UNRESOLVED_ORIGINALS',holder=owner,descriptor_census=descriptors,
        publication=dict(kind='LIVE_HEARTBEAT',path=str(Path(selected['output'])/'holder-live.json'),
            before_monotonic_ns=started,after_monotonic_ns=time.monotonic_ns(),
            raw_wire=raw.decode(),sha256=hashlib.sha256(raw).hexdigest(),value=value))


def validate_eval_holder(case, sample, previous=None):
    selected=case['continuous'].get('eval_exit_witness')
    if selected is None:
        require(sample.get('EVAL_exit_witness_capture') is None
                and sample.get('EVAL_kernel_exit_receipts',{})=={},'Unselected kernel holder capture')
        return
    eval_slots={slot for slot,role in case['slot_eval'].items() if role}
    receipts=sample.get('EVAL_kernel_exit_receipts',{});capture=sample['EVAL_exit_witness_capture']
    pub=capture['publication'];raw=pub['raw_wire'].encode();value=pub['value']
    anchors=registry().read_pin(selected['anchors'])
    require(hashlib.sha256(raw).hexdigest()==pub['sha256'] and json.loads(raw)==value
            and value['holder']==selected['holder'] and value['source']==selected['source']
            and value['selection']==selected['selection'] and value['anchors']==selected['anchors']
            and value['nonce']==anchors['nonce']
            and pub['before_monotonic_ns']<=pub['after_monotonic_ns']<=sample['monotonic_s']*1e9
            and value['exit_receipts']==receipts and set(receipts)<=eval_slots,
            'Actual source/holder/raw/publication/receipt fullpin coverage differs')
    if previous is not None:
        old=previous.get('EVAL_kernel_exit_receipts',{})
        require(set(old)<=set(receipts) and all(receipts[slot]==pin for slot,pin in old.items()),
                'A previously accepted durable original EVAL exit receipt disappeared or changed')
    if capture['state']=='ALL37_IMMUTABLE_EXIT_RECEIPTS_PUBLISHED':
        require(capture['holder'] is None and pub['kind']=='COMPLETE_TERMINAL_PUBLICATION'
                and value['schema']=='robotron-original37-EVAL-pidfd-holder-terminal-v1'
                and value['all37_exit_receipts_present'] is True and set(receipts)==eval_slots
                and value['unresolved_slots']==[]
                and value['status'] in ('ALL37_REAPED_NORMAL0','ALL37_REAPED_WITH_NONZERO_OR_SIGNAL')
                and registry().read_pin(pub['immutable_pin'])==value
                and Path(pub['immutable_pin']['path'])==Path(selected['output'])/'holder-terminal.json',
                'Complete producer terminal publication does not bind all37 fsynced exits')
        # This proves exit-file publication order, never the keeper's unit exit
        # or release. Every raw kernel exit is independently decoded below.
        return
    require(capture['state']=='HOLDING_UNRESOLVED_ORIGINALS' and pub['kind']=='LIVE_HEARTBEAT',
            'Unresolved EVAL pidfds lost their original holder')
    validate_keeper_descriptors(case,sample,capture)
    require(value['schema']=='robotron-original37-EVAL-pidfd-holder-live-v1'
            and value['state']=='HOLDING_UNRESOLVED_ORIGINALS'
            and type(value['updated_monotonic_ns'])is int
            and 0<=value['updated_monotonic_ns']<=pub['after_monotonic_ns']
            and 0<=registry().number(value['updated_unix_s'])<=sample['unix_s']
            and set(value['unresolved_slots'])==eval_slots-set(receipts),
            'Authentic durable keeper publication coverage differs')
    # The publication map proves already-fsynced immutable receipts. Its clock
    # is historical provenance only; fresh exact owner/FD census proves liveness.



def collect(case, previous=None):
    evidence = dict(stage='owners', started_monotonic_s=time.monotonic())
    try:
        reader = linux(); started = evidence['started_monotonic_s']
        status=registry().bootstrap_projection(case)
        raw=json.dumps(status,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        require(len(raw)<=524288,'Bounded historical original192 bootstrap certificate required')
        owners = {key: unit_record(case['units'][key], reader) for key in ('trainer', 'fleet')}
        evidence.update(raw_status=raw.decode(), owners=owners, children=[])
        fleet = owners['fleet']['process']
        child_ids = Path('/proc', str(fleet['pid']), 'task', str(fleet['pid']), 'children').read_text().split()
        evidence['original_children'] = child_ids
        require(len(child_ids) == len(set(child_ids)) <= 192, 'Unknown/duplicate supervisor child count')
        expected = {r['original_child']['pid']: slot for slot, r in case['continuous']['original_slots'].items()}
        actors = {}; capture = []
        for text in child_ids:
            pid = int(text); row = dict(pid=pid); evidence['children'].append(row)
            try:
                first = process_record(pid, reader); row['record'] = first
                second = process_record(pid, reader); row['confirm_record'] = second
                require(all(first[k] == second[k] for k in ('pid', 'starttime_ticks', *STATIC)),
                        'Original actor exec/identity raced capture')
                require(pid in expected and expected[pid] not in actors, 'Unknown/replaced/duplicate child PID')
                slot = expected[pid]
                require(first['environment'].get('ROBOTRON_CLIENT_SLOT') == slot, 'Original child slot changed')
                actors[slot] = first; capture.append(row)
            except (OSError, ValueError, KeyError) as error:
                row.update(error=repr(error), raw_rejection_identity=raw_identity(pid))
                raise
        evidence['stage'] = 'policy-API-and-absence'
        policy = get('/api/continuous_training_policy')
        connections = get('/api/continuous_training_connections')
        api = get('/api/now')
        completed_prefix_capture={}
        eval_evidence = collect_eval_evidence(case, previous, completed_prefix_capture)
        probes = {slot: probe(row['original_child']['pid'], reader)
                  for slot, row in case['continuous']['original_slots'].items() if slot not in actors}
        eval_cleanup = collect_eval_cleanup(case, eval_evidence, probes)
        eval_holder = collect_eval_holder(case, reader)
        eval_kernel = collect_eval_kernel_receipts(case, eval_holder)
        require(status==registry().bootstrap_projection(case), 'Held immutable bootstrap projection changed')
        require(time.monotonic() - started <= 5, 'Continuous physical/registry/API census exceeded5s')
        ended = time.monotonic()
        return dict(schema='robotron-original192-immutable-bootstrap-live-pidfd-snapshot-v4',
                    unix_s=time.time(), monotonic_s=ended, owners=owners,
                    status=status, raw_status_wire=raw.decode(), actors=actors,
                    original_children=child_ids, child_census=capture,
                    api=api['value'], raw_API_wire=api['raw_wire'], api_wire_sha256=api['sha256'],
                    policy_capture=policy, connections_capture=connections,
                    EVAL_journal_evidence=eval_evidence,EVAL_completed_prefix_capture=completed_prefix_capture,
                    EVAL_cleanup_captures=eval_cleanup,
                    EVAL_kernel_exit_receipts=eval_kernel,EVAL_exit_witness_capture=eval_holder,
                    PID_absence=probes, capture_started_monotonic_s=started,
                    capture_ended_monotonic_s=ended)
    except (OSError, ValueError, KeyError) as failure:
        evidence.update(failure=repr(failure), ended_monotonic_s=time.monotonic())
        raise CensusFailure(repr(failure), evidence) from failure


def validate_policy(case, sample, capture, schema):
    c = case['continuous']; value = capture['value']; raw = capture['raw_wire'].encode()
    require(hashlib.sha256(raw).hexdigest() == capture['sha256'] and json.loads(raw) == value,
            'Policy/connection raw wire changed')
    require(type(capture['before_monotonic_ns']) is int and type(capture['after_monotonic_ns']) is int
            and capture['before_monotonic_ns'] <= value['observed_monotonic_ns'] <= capture['after_monotonic_ns']
            and 0 <= sample['monotonic_s'] - capture['before_monotonic_ns']/1e9 <= 2
            and capture['after_monotonic_ns']/1e9 <= sample['monotonic_s']
            and 0 <= sample['unix_s'] - value['observed_unix_s'] <= 2,
            'Actual original policy/connection observation is future/unbracketed/stale')
    require(value['schema'] == schema and value['server_stamp'] == c['server_stamp']
            and value['continuous_training_mode'] is True and value['main_measurement_entry_disabled'] is True
            and value['measurement_active'] is False and value['measurement_generation'] == c['policy_generation']
            and type(value['measurement_generation']) is int and value['ratchet_frozen'] is False
            and value['training_enabled'] is True and value['replay_admission_open'] is True
            and value['consumer_error'] is None, 'Actual permanent main-policy mode/epoch/fence changed')
    return value


def validate(case, sample, previous=None):
    reg = registry(); c = case['continuous']
    validate_eval_holder(case,sample,previous)
    require(case['schema'] == reg.CASE_SCHEMA, 'Explicit new continuous health case required')
    view = reg.validate_snapshot(case, sample, previous)
    require(sample['schema'] == 'robotron-original192-immutable-bootstrap-live-pidfd-snapshot-v4'
            and json.loads(sample['raw_status_wire']) == sample['status'], 'Historical bootstrap certificate raw encoding changed')
    require(0 <= sample['monotonic_s'] - sample['capture_started_monotonic_s'] <= 5
            and sample['capture_started_monotonic_s'] <= sample['capture_ended_monotonic_s'] <= sample['monotonic_s'],
            'Physical census capture bracket differs')
    for role in ('trainer', 'fleet'):
        actual, baseline = sample['owners'][role], case['owners'][role]
        require(actual['unit'] == baseline['unit'] and actual['invocation'] == baseline['invocation']
                and birth(actual['process']) == birth(baseline['process'])
                and all(actual['process'][key] == baseline['process'][key] for key in STATIC),
                'Original main owner/source/recipe/affinity/cgroup changed')
    reg.owner_join(c['trainer'], sample['owners']['trainer'])
    reg.owner_join(c['supervisor'], sample['owners']['fleet'])
    actors = sample['actors']; absent = reg.SLOTS - set(actors)
    require(set(actors) <= reg.SLOTS and absent <= view['retiring'] | view['closed']
            and not set(actors) & view['closed'] and set(sample['PID_absence']) == absent,
            'An original TRAIN/active EVAL vanished, unknown child appeared, or closed EVAL remains live')
    census = sample['child_census']
    require(len(census) == len(sample['original_children']) == len(actors)
            and {str(row['pid']) for row in census} == set(sample['original_children']),
            'Raw original child census coverage differs')
    for slot, actor in actors.items():
        original = c['original_slots'][slot]['original_child']
        matches = [entry for entry in census if entry['pid'] == actor['pid']]
        require(len(matches) == 1 and matches[0]['record'] == actor
                and all(actor[k] == matches[0]['confirm_record'][k] for k in ('pid', 'starttime_ticks', *STATIC))
                and actor['pid'] == original['pid'] and actor['starttime_ticks'] == original['birth']
                and actor['parent_pid'] == c['supervisor']['pid'] and actor['cgroup'] == c['supervisor']['cgroup']
                and actor['command'] == case['actor_command'] and actor['executable'] == case['actor_executable']
                and actor['environment'] == reg.expected_environment(case, slot)
                and actor['affinity'] == case['actor_affinity'] and actor['uids'] == [os.getuid()]*4
                and actor['state'] not in ('T', 't', 'Z', 'X', 'x'),
                'Actual original MAME birth/argv/role/source/env/affinity/state changed')
    for slot in absent:
        old = c['original_slots'][slot]['original_child']; probe = sample['PID_absence'][slot]
        require(probe['pid'] == old['pid'] and probe['path'] == str(Path('/proc', str(old['pid']), 'stat'))
                and (probe['absent'] is True and probe['current_birth'] is probe['state'] is None
                     or probe['absent'] is False and type(probe['current_birth']) is int and probe['current_birth'] != old['birth'])
                and sample['capture_started_monotonic_s'] <= probe['before_monotonic_s']
                <= probe['after_monotonic_s'] <= sample['capture_ended_monotonic_s'],
                'No fresh positive original birth absence for retired EVAL')
    validate_policy(case, sample, sample['policy_capture'], 'robotron-continuous-main-policy-v1')
    connections = validate_policy(case, sample, sample['connections_capture'], 'robotron-continuous-active-connections-v1')
    current = connections['connections']; conn_slots = [str(x['client_slot']) for x in current]
    require(len(conn_slots) == len(set(conn_slots)) and set(conn_slots) <= set(actors)
            and set(actors) - set(conn_slots) <= view['retiring'], 'Fresh connection batch misses active original or has unknown slot')
    for slot, connection in zip(conn_slots, current):
        if case['slot_eval'][slot]:
            expected = reg.binding(case, slot, c['original_slots'][slot]['connection_binding'],
                                   c['original_slots'][slot]['original_child'])
            require(connection == expected, 'EVAL original connection token/CID/role/endpoints changed')
        else:
            require(connection == view['current_connections'][slot],
                    'Current TRAIN handler differs from its derived physical slot view')
    api = sample['api']; raw = sample['raw_API_wire'].encode()
    require(hashlib.sha256(raw).hexdigest() == sample['api_wire_sha256'] and json.loads(raw) == api,
            'Raw main API changed')
    require(api['training_enabled'] is True and api['measurement_active'] is False
            and 0 <= sample['unix_s'] - api['ts'] <= 5 and 0 <= api['pipeline_snapshot_age_s'] <= 5
            and all(api[key] == value for key, value in case['recipe'].items()), 'Main recipe/training API stale or changed')
    for kind in ('optimizer', 'replay'):
        actual = api['host_pipeline']['learning_exposure'][kind]
        require(all(actual[key] == case['exposure'][kind][key]
                    for key in ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')),
                'Original optimizer/replay lineage changed')
        require(actual['enabled'] is True, 'Learning exposure disabled')
        if kind == 'optimizer': validate_optimizer_accounting(actual)
        else: require(actual['available'] is True, 'Replay exposure unavailable')
    if previous is not None:
        require(0 <= sample['monotonic_s'] - previous['monotonic_s'] <= 2,
                'Prospective accepted main-proof gap exceeds2s')
        require(all(api[key] >= previous['api'][key] for key in
                    ('training_steps', 'learner_frame_count', 'optimized_samples', 'frame_count')),
                'Main coherent clock rolled back')
    return view


if __name__ == '__main__':
    print('SOURCE_ONLY_INERT_NO_READS_WRITES_PROBES_OR_ACTIONS')


