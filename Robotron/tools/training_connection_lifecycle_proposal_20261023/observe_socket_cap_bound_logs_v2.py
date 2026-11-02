"""Bounded read-only API/proc/socket/log trace; never changes a training process."""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import urllib.request


def checked(entry):
    path = Path(entry['path'])
    raw = path.read_bytes()
    assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
    return path


def load(name, entry):
    path = checked(entry)
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def birth(pid):
    raw = Path('/proc',str(pid),'stat').read_text()
    return int(raw[raw.rfind(')')+2:].split()[19])


def fd_inodes(pid):
    result,vanished = {},[]
    for fd in Path('/proc',str(pid),'fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            vanished.append(fd.name);continue
        if target.startswith('socket:[') and target.endswith(']'):
            result[fd.name] = int(target[8:-1])
    return dict(pid=pid,starttime_ticks=birth(pid),socket_fds=result,vanished_fd_numbers=vanished)


def tcp():
    begin = time.time()
    with open('/proc/net/tcp','rb') as stream:
        raw = stream.read((16<<20)+1)
    assert 0 < len(raw) <= 16<<20
    lines = raw.splitlines(keepends=True)
    selected = [lines[0]];rows=[]
    for number,line in enumerate(lines[1:],1):
        cells=line.split()
        local,peer = cells[1].decode(),cells[2].decode()
        if int(local.split(':')[1],16) == 9998 or int(peer.split(':')[1],16) == 9998:
            selected.append(line)
            rows.append(dict(original_line_number=number,local=local,peer=peer,
                             state=cells[3].decode(),inode=int(cells[9]),uid=int(cells[7])))
    return dict(begin_unix_s=begin,end_unix_s=time.time(),selected_rows=rows,
                full_proc_read_bytes=len(raw),full_proc_read_sha256=hashlib.sha256(raw).hexdigest()),b''.join(selected)


def actor_connections(fd_view, table):
    own = set(fd_view['socket_fds'].values())
    return [row for row in table['selected_rows'] if row['inode'] in own
            and int(row['peer'].split(':')[1],16) == 9998]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw=Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job=json.loads(raw)
    assert job['schema'] == 'robotron-readonly-natural-socket-cap-trace-job-v2'
    assert job['duration_s'] == 120 and job['poll_s'] == .2 and job['fd_refresh_s'] == 1
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    h=load('_natural_socket_h',job['helpers']['pin'])
    witness=load('_natural_socket_raw',job['helpers']['raw_API'])
    guard=load('_natural_socket_guard',job['helpers']['guard'])
    binding=json.loads(checked(job['binding']).read_text())
    assert [actor['slot'] for actor in binding['actors']] == list(range(192))
    guard.owner_and_files(binding)
    output=Path(job['output']);output.mkdir(mode=0o700)
    (output/'samples').mkdir();(output/'cap-chunks').mkdir()
    def write_bytes(path,data):
        with path.open('xb') as stream:
            stream.write(data);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        return h.pin(path)
    def read_API():
        begin=time.time()
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
            raw=response.read(witness.MAX_WIRE_BYTES+1)
        return begin,time.time(),raw
    def all_fds():
        begin=time.time();actors={}
        trainer=fd_inodes(binding['owner']['pid'])
        assert trainer['starttime_ticks'] == binding['owner']['starttime_ticks']
        for actor in binding['actors']:
            view=fd_inodes(actor['pid'])
            assert view['starttime_ticks'] == actor['starttime_ticks']
            actors[str(actor['slot'])]=view
        return dict(begin_unix_s=begin,end_unix_s=time.time(),trainer=trainer,actors=actors)
    log_cursors={}
    for actor in binding['actors']:
        slot=actor['slot'];path=Path(os.readlink('/proc/'+str(actor['pid'])+'/fd/1'))
        origin=job['log_origins'][str(slot)]
        assert path == Path(origin['path']) and path.resolve().is_relative_to(Path(job['log_root']).resolve())
        info=path.stat()
        assert (info.st_dev,info.st_ino)==(origin['device'],origin['inode'])
        log_cursors[str(slot)]=dict(path=str(path),device=info.st_dev,inode=info.st_ino,
                                    offset=info.st_size,last_observed_unix_s=time.time())
    h.put(output/'initial-log-cursors.json',log_cursors)
    baseline_begin,baseline_end,baseline_raw=read_API()
    baseline=witness.parse_wire(baseline_raw)
    baseline_pin=write_bytes(output/'initial-API.raw.json',baseline_raw)
    assert baseline['client_count'] == len(baseline['client_rows']) == 192
    assert sorted(row['client_slot'] for row in baseline['client_rows']) == list(range(192))
    first_tcp,first_raw=tcp();first_tcp['selected_raw']=write_bytes(output/'initial-tcp-before.txt',first_raw)
    fd_view=all_fds();second_tcp,second_raw=tcp()
    second_tcp['selected_raw']=write_bytes(output/'initial-tcp-after.txt',second_raw)
    server_inodes=set(fd_view['trainer']['socket_fds'].values())
    ownership={}
    for slot,view in fd_view['actors'].items():
        first=actor_connections(view,first_tcp);second=actor_connections(view,second_tcp)
        assert len(first) == len(second) == 1
        assert all(first[0][key] == second[0][key] for key in ('local','peer','state','inode','uid'))
        row=second[0];assert row['state'] == '01'
        reverse=[entry for entry in second_tcp['selected_rows'] if entry['local'] == row['peer']
                 and entry['peer'] == row['local'] and entry['state'] == '01'
                 and entry['inode'] in server_inodes]
        assert len(reverse) == 1
        ownership[slot]=dict(actor=view,client_connection=row,server_connection=reverse[0])
    server_established=[row for row in second_tcp['selected_rows']
                        if int(row['local'].split(':')[1],16) == 9998 and row['state'] == '01']
    assert len(server_established) == 192
    initial=h.put(output/'initial-original192-ownership.json',dict(API=baseline_pin,
        API_request_begin_unix_s=baseline_begin,API_request_end_unix_s=baseline_end,
        tcp_before=first_tcp,tcp_after=second_tcp,fd_view=fd_view,ownership=ownership,
        all192_original_process_sockets_join_server_reverse_endpoints=True,
        exact_CID_to_socket_runtime_metadata_available=False))
    previous_ids={str(row['client_slot']):[row['client_id']] for row in baseline['client_rows']}
    previous_sockets={slot:[entry['client_connection']['inode']] for slot,entry in ownership.items()}
    fd_view_pin=h.put(output/'initial-fd-view.json',fd_view)
    start=time.monotonic();deadline=start+job['duration_s'];next_fds=start+1
    records=[];events=[];count_histogram=collections.Counter();cap_count=0
    while time.monotonic() < deadline:
        iteration=time.monotonic();number=len(records);stem=f'{number:05d}'
        begin,end,API_raw=read_API()
        API_pin=write_bytes(output/'samples'/(stem+'-API.raw.json'),API_raw)
        API=witness.parse_wire(API_raw)
        assert API['training_enabled'] is True and API['measurement_active'] is False
        assert API['managed_experiment'] == binding['experiment'] and API['lr'] == 6.25e-6
        assert API['pipeline_read_error'] == API['bank_persistence_read_error'] == ''
        table,TCP_raw=tcp();table['selected_raw']=write_bytes(output/'samples'/(stem+'-tcp.txt'),TCP_raw)
        changed=[];ids={}
        for row in API['client_rows']:
            ids.setdefault(str(row['client_slot']),[]).append(row['client_id'])
        ids={slot:sorted(values) for slot,values in ids.items()}
        duplicate_slots=sorted(slot for slot,values in ids.items() if len(values)>1)
        changed_slots=sorted(slot for slot in set(ids)|set(previous_ids) if ids.get(slot)!=previous_ids.get(slot))
        if API['client_count'] != 192 or duplicate_slots:
            changed.append(dict(kind='API_connection_count_or_duplicate',count=API['client_count'],
                duplicates=duplicate_slots,rows=[row for row in API['client_rows'] if str(row['client_slot']) in duplicate_slots]))
        if changed_slots:
            changed.append(dict(kind='API_client_ID_epoch_changed',slots=changed_slots,
                before={slot:previous_ids.get(slot) for slot in changed_slots},
                after={slot:ids.get(slot) for slot in changed_slots}))
        if time.monotonic() >= next_fds or changed_slots or duplicate_slots:
            fd_view=all_fds();fd_view_pin=h.put(output/'samples'/(stem+'-fd-view.json'),fd_view)
            next_fds=time.monotonic()+job['fd_refresh_s']
            sockets={slot:sorted(row['inode'] for row in actor_connections(view,table))
                     for slot,view in fd_view['actors'].items()}
            socket_changes=[slot for slot in sockets if sockets[slot]!=previous_sockets.get(slot)]
            if socket_changes:
                changed.append(dict(kind='owned_MAME_TCP_inode_changed',slots=socket_changes,
                    before={slot:previous_sockets.get(slot) for slot in socket_changes},
                    after={slot:sockets.get(slot) for slot in socket_changes}))
            previous_sockets=sockets
        caps=[]
        for slot,cursor in log_cursors.items():
            path=Path(cursor['path']);info=path.stat();now=time.time()
            assert (info.st_dev,info.st_ino)==(cursor['device'],cursor['inode']) and info.st_size>=cursor['offset']
            if info.st_size>cursor['offset']:
                size=info.st_size-cursor['offset'];assert size<=256*1024
                with path.open('rb') as stream:
                    stream.seek(cursor['offset']);chunk=stream.read(size)
                assert len(chunk)==size
                chunk_pin=write_bytes(output/'cap-chunks'/(stem+'-slot'+slot+'.txt'),chunk)
                count=chunk.count(b'[WAVECAP] wave advance 74 -> 75 - soft reset (training-data rebalance)')
                cap_count+=count
                caps.append(dict(slot=int(slot),actor_pid=binding['actors'][int(slot)]['pid'],
                    path=str(path),device=info.st_dev,inode=info.st_ino,offset=cursor['offset'],bytes=size,
                    lower_observed_unix_s=cursor['last_observed_unix_s'],upper_observed_unix_s=now,
                    cap_markers=count,raw=chunk_pin))
                cursor['offset']=info.st_size
            cursor['last_observed_unix_s']=now
        if caps:
            changed.append(dict(kind='original_actor_log_appended',chunks=caps))
        count_histogram[API['client_count']]+=1
        record=dict(index=number,API=API_pin,API_begin_unix_s=begin,API_end_unix_s=end,
            tcp=table,latest_fd_view=fd_view_pin,API_client_count=API['client_count'],API_slot_cids=ids,
            learner_frame_count=API['learner_frame_count'],training_steps=API['training_steps'],
            optimized_samples=API['optimized_samples'],fleet_fps=API['fps'],events=changed,
            observed_unix_s=time.time(),loop_elapsed_s=time.monotonic()-iteration)
        pin=h.put(output/'samples'/(stem+'-observation.json'),record)
        records.append(pin)
        if changed:
            events.append(dict(index=number,observation=pin,kinds=[item['kind'] for item in changed]))
        if number%25==0:
            progress=dict(samples=len(records),events=len(events),caps=cap_count,
                elapsed_s=time.monotonic()-start,owner_pid=os.getpid(),observed_unix_s=time.time())
            write_bytes(output/'progress.next',(json.dumps(progress,allow_nan=False)+'\n').encode())
            os.replace(output/'progress.next',output/'progress.json')
        previous_ids=ids
        time.sleep(max(0,min(job['poll_s']-(time.monotonic()-iteration),deadline-time.monotonic())))
    guard.owner_and_files(binding)
    for entry in job['helpers'].values():
        checked(entry)
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    assert 'torch' not in __import__('sys').modules
    report=dict(schema='robotron-readonly-natural-socket-cap-trace-report-v1',
        status='BOUNDED_ORIGINAL_READONLY_TRACE_COMPLETE',job_sha256=args.job_sha256,
        source_sha256=args.source_sha256,initial_original192_ownership=initial,
        samples=records,event_observations=events,API_client_count_histogram=dict(count_histogram),
        observed_cap_markers=cap_count,requested_duration_s=120,elapsed_s=time.monotonic()-start,
        all_original192_births_affinities_and197_holds_unchanged=True,
        production_runtime_changed=False,training_control_changed=False,checkpoint_requested=False,
        production_training_socket_opened=False,only_local_dashboard_HTTP_read=True,CUDA_initialized=False,
        scientific_original_retried=False,quality_qualified=False,
        limits=['Read-only proc/API/log captures are bracketed, not atomic across processes.',
                'TCP states and inode changes alone do not identify API client IDs; exact server CID/socket metadata is unavailable.',
                'Natural cap/log/connection joins require independent event review; no automatic cause certification or gate exception.',
                'Sampling overhead is bounded by CPU scope; no useful-throughput gain or zero-overhead claim.'])
    pin=h.put(output/'report.json',report)
    print(json.dumps(dict(status=report['status'],samples=len(records),event_observations=len(events),
                          caps=cap_count,count_histogram=dict(count_histogram),report=pin)),flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
