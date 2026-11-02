"""Selected full-observation bridge to the unchanged isolated frozen server.

No listeners, imports of Torch, file writes or process actions occur on import.
The owning diagnostic must bind original actor birth, source/ROM/policy inputs,
fresh trace/lifecycle inodes, ports, complete-cohort drain and intentional
shutdown. Dense trace ends at1200; ordinary wire/inference continues. This is
not a quality runner and cannot relax the separate confirmation protocol.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import threading
import time

import startup_handoff_v2 as authority
import wire_codec_v2 as codec
from boot_readiness_v3 import boot_readiness
from tail_ledger_v1 import TailLedger


def require(value,message):
    if not value:
        raise ValueError(message)


def recv_exact(sock,count):
    out=[]
    while count:
        value=sock.recv(count)
        require(value,'Original startup connection ended during a frame')
        out.append(value);count-=len(value)
    return b''.join(out)


class TracePrefix:
    """Bounded append-only prefix of the exact precreated actor-owned file.

    Only device/inode/mode/uid/link identity is held during append. Size and
    timestamps are expected to advance. Final disposition must retain the
    complete closed bytes separately; an open prefix is not a sealed log.
    """
    def __init__(self,path,identity,subject,expected_rom_sha256):
        self.path=Path(path)
        self.identity=dict(identity)
        require(set(self.identity)=={'device','inode','mode','uid','nlink'},
                'Explicit append-stable trace identity required')
        self.subject=dict(subject)
        self.expected_rom_sha256=expected_rom_sha256
        self.closed_pin=None

    def rows(self,through_event):
        codec.integer(through_event,1,4096,'prefix event')
        fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd)
            actual=dict(device=before.st_dev,inode=before.st_ino,mode=oct(stat.S_IMODE(before.st_mode)),
                        uid=before.st_uid,nlink=before.st_nlink)
            require(actual==self.identity and stat.S_ISREG(before.st_mode)
                    and before.st_size<=16*1024*1024,'Original actor trace identity/bound differs')
            with os.fdopen(fd,'rb',closefd=False)as stream:
                raw=stream.read(before.st_size)
            after=os.fstat(fd)
            require((before.st_dev,before.st_ino,before.st_mode,before.st_uid,before.st_nlink)==
                    (after.st_dev,after.st_ino,after.st_mode,after.st_uid,after.st_nlink)
                    and after.st_size>=before.st_size and len(raw)==before.st_size,
                    'Original actor trace replaced or truncated')
        finally:
            os.close(fd)
        complete=[line for line in raw.splitlines(keepends=True)if line.endswith(b'\n')]
        require(len(complete)>=through_event,'Original producer prefix is incomplete')
        rows=[]
        for index,line in enumerate(complete[:through_event],1):
            require(len(line)<=2048,'Original producer row exceeds bound')
            row=codec.decode_json(line)
            require(row.get('schema')=='robotron-full-policy-startup-trace-v2'
                    and type(row.get('event'))is int and row['event']==index
                    and all(type(row.get(k))is type(v)and row[k]==v for k,v in self.subject.items()),
                    'Original producer event or bound subject differs')
            rows.append(row)
        return rows

    def loaded_rom(self):
        rows=self.rows(801)
        require(rows[0]['kind']=='header'and rows[0]['frame_limit']==1200,
                'Full producer header differs')
        chunks=rows[1:]
        require(all(row['kind']=='raw_ROM_chunk'and type(row['offset'])is int
                    and row['offset']==128*index for index,row in enumerate(chunks)),
                'Whole loaded ROM prefix differs')
        image=b''.join(bytes.fromhex(codec.hex_value(row['data_hex'],256,'loaded ROM chunk'))
                       for row in chunks)
        require(len(image)==0x19000 and hashlib.sha256(image).hexdigest()==self.expected_rom_sha256,
                'Actual loaded ROM differs from precommitted complete image')
        return image

    def evidence(self,meta,issuer,origin):
        rows=self.rows(meta['event'])
        initialized=rows[-1]
        require(initialized['kind']=='snapshot'and initialized['sequence']==meta['sequence']
                and all(initialized[k]==meta[k]for k in ['status','score_hex','wave','reserves',
                    'player_count','current_player','credit','nonce','first_play_sequence']),
                'Actual snapshot does not match original wire metadata')
        apps=[r for r in rows if r['kind']=='input_applied'and r['sequence']==issuer.sequence]
        gates=[r for r in rows if r['kind']=='ROM_write'and r['address']==0x9840
               and r['instruction_pc']==0x2715 and r['dp']==0x98 and r['bank_entry']==1]
        setups=[r for r in rows if r['kind']=='ROM_write'and r['address']==0x9859
                and r['instruction_pc']==0x2751 and r['dp']==0x98 and r['bank_entry']==1]
        require(len(apps)==len(gates)==len(setups)==1,'Unique original application/gate/setup required')
        require(initialized['score_hex']=='00000000','Initialized raw score differs')
        normalized={k:initialized[k]for k in ['session','connection','slot','nonce','sequence','event',
                                             'wave','player_count','current_player','first_play_sequence']}
        normalized.update(score=0,raw_reserves=initialized['reserves'],
                          player_alive=bool((initialized['status']&1)==0))
        return dict(application=apps[0],gate=gates[0],setup=setups[0],
                    initialization=normalized,origin_acceptance=origin)

    def _closed_bytes(self):
        fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd)
            identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,
                mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),
                uid=s.st_uid,nlink=s.st_nlink)
            require(stat.S_ISREG(before.st_mode) and before.st_size<=16*1024*1024
                    and all(identity(before)[k]==v for k,v in self.identity.items()),
                    'Original closed prefix identity/bound differs')
            with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(before.st_size+1)
            require(identity(os.fstat(fd))==identity(before) and len(raw)==before.st_size,
                    'Original supposedly closed prefix is still changing')
            return raw,dict(path=str(self.path),sha256=hashlib.sha256(raw).hexdigest(),
                            bytes=len(raw),identity=identity(before))
        finally:os.close(fd)

    def closed_summary(self,nonce,accepted_init_sequence):
        require(self.closed_pin is None,'Original prefix closure already bound')
        raw,pin=self._closed_bytes()
        require(raw.endswith(b'\n'),'Original closed prefix has an incomplete row')
        lines=raw.splitlines();require(801<len(lines)<=4096,'Original closed prefix event bound differs')
        rows=[]
        for index,line in enumerate(lines,1):
            require(len(line)<=2048,'Original closed prefix row exceeds bound')
            row=codec.decode_json(line)
            require(row.get('schema')=='robotron-full-policy-startup-trace-v2'
                    and type(row.get('event'))is int and row['event']==index
                    and all(type(row.get(k))is type(v)and row[k]==v for k,v in self.subject.items()),
                    'Original closed prefix subject/event differs')
            rows.append(row)
        footer=rows[-1]
        require(rows[0]['kind']=='header'and rows[0]['frame_limit']==1200
                and rows[0]['continues_after_prefix']is True
                and footer['kind']=='footer'and footer['reason']=='prefix_complete'
                and footer['sequence']==footer['frame_limit']==1200
                and footer['failed']is footer['machine_exit_requested']is False
                and 0<footer['initialized_sequence']<=footer['latched_sequence']==accepted_init_sequence
                    <footer['first_play_sequence']<=1200
                and not any(r['kind']=='fault'for r in rows),'Original prefix failed or did not enter certified play')
        for kind in ('snapshot','input_applied'):
            selected=[r for r in rows if r['kind']==kind]
            require([r['sequence']for r in selected]==list(range(1,1201)),
                    'Original complete1200 snapshot/input pairs required')
            if kind=='input_applied':
                require(all(r['socket_ok']is r['apply_ok']is True and r['debug_bypass']is False
                            for r in selected),'Original prefix input application failed')
        require(all(r['nonce']==nonce for r in rows if r['kind']in ('snapshot','input_applied')
                    and r['sequence']>=accepted_init_sequence),'Original prefix nonce changed')
        self.closed_pin=pin
        return dict(trace=pin,footer=footer,events=len(rows),dense_prefix_frames=1200,
                    continues_after_prefix=True)

    def verify_closed_unchanged(self):
        require(self.closed_pin is not None,'Original prefix closure not yet bound')
        _,current=self._closed_bytes()
        require(current==self.closed_pin,'Original closed startup trace changed during the full tail')
        return current


class StartupProxy:
    def __init__(self,server,*,slot,session,connection,trace_path,trace_identity,
                 rom_sha256,policy_reader,admission_reader,frame_parser,emit,stop_event,
                 drain_reader,parked_origin_timeout_s,wall_ns=time.time_ns,monotonic_ns=time.monotonic_ns):
        self.server=server
        self.subject=dict(slot=slot,session=session,connection=connection)
        require(codec.decode_handshake(codec.encode_handshake(**self.subject))==self.subject,
                'Explicit original proxy subject required')
        self.trace=TracePrefix(trace_path,trace_identity,self.subject,rom_sha256)
        self.rom_sha256=rom_sha256
        self.policy_reader,self.admission_reader=policy_reader,admission_reader
        self.frame_parser,self.emit,self.stop_event=frame_parser,emit,stop_event
        self.wall_ns,self.monotonic_ns=wall_ns,monotonic_ns
        require(type(parked_origin_timeout_s)is int and 120<=parked_origin_timeout_s<=22200,
                'Explicit bounded retired-origin lifetime required')
        self.parked_origin_timeout_s=parked_origin_timeout_s
        self.drain_reader=drain_reader
        self.sent_complete=threading.Event()
        self.prefix_verified=threading.Event()
        self.stop_sent=threading.Event()
        self.peer_eof=threading.Event()
        self.sequence=0
        self.issuer=None
        self.handoff=None
        self.error=None
        self.cid=None
        self.last_response=None
        self.handoff_sequence=None
        self.prefix_summary=None
        self.stop_receipt=None
        self.final_ledger=None
        self.ledger=TailLedger(self.subject,rom_sha256,self.emit)

    def state(self):
        with self.server.client_lock:
            cs=self.server.client_states.get(self.cid)
            require(isinstance(cs,dict),'Original origin client disappeared')
            keys=['frames','game_uid','client_slot','eval_only','game_score','level_number',
                  'player_alive','num_lasers','lives']
            return {key:cs.get(key)for key in keys}

    def find_client(self):
        end=time.monotonic()+3
        while time.monotonic()<end:
            with self.server.client_lock:
                matches=[cid for cid,cs in self.server.client_states.items()
                         if cs.get('client_slot')==self.subject['slot']]
            require(len(matches)<=1,'Duplicate origin slot')
            if matches:
                self.cid=matches[0]
                return
            require(not self.stop_event.is_set(),'Original startup stopped during handshake')
            time.sleep(.005)
        raise TimeoutError('Original origin slot handshake did not complete')

    def open_window(self):
        window=self.admission_reader()
        if window is None:
            return False
        require(set(window)=={'open_unix_ns','close_unix_ns','generation','experiment'},
                'Actual controller window differs')
        now=self.wall_ns()
        # Closing admission never cuts off an already admitted game's tail.
        # An incomplete first-start certificate still rejects in issue().
        return window['open_unix_ns']<=now<window['close_unix_ns']

    def process(self,peer,origin,raw):
        payload,meta=codec.decode_request(raw)
        require(meta['sequence']==self.sequence+1
                and all(meta[k]==v for k,v in self.subject.items()),'Original request subject/sequence changed')
        sequence=meta['sequence']
        require(not self.stop_sent.is_set(),'Unexpected request after original STOP')
        if sequence>1:
            require(meta['last_apply_ok']is meta['last_socket_ok']is True
                    and meta['last_start']==(self.last_response[8]&1)
                    and meta['last_coin']==self.last_response[9],
                    'Actual previous response/input echo failed')
        if self.issuer is None:
            require(meta['mode']=='gated'and meta['nonce']=='0'*64,'Premature startup bypass')
        else:
            require(meta['nonce']==self.issuer.nonce,'Actual input nonce did not echo original response')
            require(meta['mode']in (['latched','legacy']if self.handoff else ['authorized']),
                    'Original startup phase differs')
            if not self.handoff:
                require(meta['first_play_sequence']==-1,'Actual play preceded journal handoff')
        if sequence>1200:
            require(self.handoff is not None and meta['mode']=='legacy','Uncertified postprefix continuation')
            if not self.prefix_verified.is_set():
                self.prefix_summary=self.trace.closed_summary(self.issuer.nonce,self.handoff_sequence)
                self.emit(dict(kind='original_closed_prefix_verified',**self.prefix_summary,
                               ledger_anchor=self.ledger.summary()))
                self.prefix_verified.set()
            require(meta['first_play_sequence']==self.prefix_summary['footer']['first_play_sequence'],
                    'Original first-play witness changed during the tail')
        before=self.state()
        origin.sendall(struct.pack('>I',len(payload))+payload)
        action=recv_exact(origin,6)
        codec.validate_action(action)
        after=self.state()
        require(type(before['frames'])is int and type(after['frames'])is int
                and after['frames']in (before['frames'],before['frames']+1),
                'Origin accepted ordinal advanced ambiguously')
        accepted=after['frames']==before['frames']+1
        require(self.server.inference_only_error is None,'Actual origin inference failed')
        if sequence<=1200:
            self.emit(dict(kind='origin_exchange',sequence=sequence,original_payload_hex=payload.hex(),
                metadata=meta,actual_action_hex=action.hex(),before=before,after=after,
                accepted=accepted,after_original_action_monotonic_ns=self.monotonic_ns()))
        initialized=(meta['score_hex']=='00000000'and meta['wave']==1 and meta['reserves']==2
            and meta['player_count']==meta['current_player']==1 and (meta['status']&1)!=0
            and meta['first_play_sequence']==-1)
        if self.issuer and not self.handoff and accepted and initialized:
            current=self.frame_parser(payload)
            for key,value in [('game_score',after['game_score']),('level_number',after['level_number']),
                              ('player_alive',after['player_alive']),('num_lasers',after['num_lasers']),
                              ('lives',after['lives'])]:
                setattr(current,key,value)
            origin_record=dict(client_id=self.cid,client_slot=after['client_slot'],
                frame_sequence=sequence,accepted=True,accepted_frames=after['frames'],
                game_uid=after['game_uid'],raw_payload_sha256=hashlib.sha256(payload).hexdigest())
            evidence=self.trace.evidence(meta,self.issuer,origin_record)
            permit=self.issuer.issue(lambda:evidence)
            self.handoff=self.issuer.handoff(permit,current,after,
                                            lambda:self.server._journal_context(after))
            self.handoff_sequence=sequence
            self.emit(dict(kind='actual_policy_journal_handoff',sequence=sequence,
                           result=self.handoff,certificate=json.loads(permit.payload)))
            drain=self.drain_reader()
            require(drain is not None,'Actual host cohort drain must be bound before handoff publication')
            drain.register_start(**self.subject,nonce=self.issuer.nonce,client_id=self.cid,
                journal_game_id=self.handoff['journal_game_id'],
                certificate_identifier=self.handoff['certificate_identifier'])
            self.emit(dict(kind='original_host_drain_start_registered',sequence=sequence,
                           journal_game_id=self.handoff['journal_game_id']))
        window_open=self.open_window()
        can_start=(self.issuer is None and accepted and window_open
                   and meta['planned_start']==1 and meta['status']==243 and meta['credit']>=1
                   and meta['first_play_sequence']==-1)
        readiness=boot_readiness(self.trace.rows(meta['event']),meta)if can_start else None
        can_start=bool(can_start and readiness is not None)
        if can_start:
            self.emit(dict(kind='original_boot_coin_readiness',sequence=sequence,readiness=readiness))
            self.issuer=authority.StartupHandoff(self.server.game_journal.journal,client_id=self.cid,
                slot=self.subject['slot'],session=self.subject['session'],connection=self.subject['connection'],
                expected_rom_sha256=self.rom_sha256,policy_reader=self.policy_reader,
                admission_reader=self.admission_reader,wall_ns=self.wall_ns,monotonic_ns=self.monotonic_ns)
            self.issuer.loaded_rom(self.trace.loaded_rom())
            def send_authorization(response):
                self.emit(dict(kind='before_authorizing_response',sequence=sequence,
                               response_hex=response.hex(),host_unix_ns=self.wall_ns(),
                               host_monotonic_ns=self.monotonic_ns()))
                self.ledger.record(payload=payload,meta=meta,action=action,response=response,
                                   before=before,after=after,accepted=accepted)
                return peer.sendall(response)
            response=self.issuer.authorize(sequence,action,send_authorization)
        else:
            if self.handoff and meta['mode']=='legacy':
                start,coin=meta['planned_start'],meta['planned_coin']
            elif self.issuer and not self.handoff:
                start=int(meta['planned_start']==1 and sequence<self.issuer.sequence+3)
                coin=0
            else:
                start=0
                coin=int(self.issuer is None and window_open and meta['planned_coin']==1)
            if sequence>1200:
                drain=self.drain_reader()
                require(drain is not None,'Original host drain authority disappeared')
                with drain.lock:drain_permit=drain.permit
                if drain_permit is not None:
                    self.stop_receipt=drain.authorize_slot(drain_permit,**self.subject,
                        nonce=self.issuer.nonce,sequence=sequence)
                    self.emit(dict(kind='before_original_host_drained_STOP',sequence=sequence,
                                   receipt=self.stop_receipt))
            response=codec.encode_response(sequence,action,start=start,coin=coin,
                nonce=self.issuer.nonce if self.issuer else '0'*64,latched=self.handoff is not None,
                stop=self.stop_receipt is not None)
            self.ledger.record(payload=payload,meta=meta,action=action,response=response,
                               before=before,after=after,accepted=accepted,drain_receipt=self.stop_receipt)
            if sequence<=1200 or self.stop_receipt is not None:
                self.emit(dict(kind='before_wrapped_response',sequence=sequence,
                               response_hex=response.hex(),host_unix_ns=self.wall_ns()))
            peer.sendall(response)
        self.sequence=sequence
        self.last_response=response
        if sequence<=1200 or self.stop_receipt is not None:
            self.emit(dict(kind='response_send_complete',sequence=sequence,host_monotonic_ns=self.monotonic_ns()))
        if sequence==1200:self.sent_complete.set()
        if self.stop_receipt is not None:self.stop_sent.set()

    def serve(self,peer,origin):
        """Caller owns sockets and stops origin BEFORE releasing this bridge.

        After prefix closure every ordinary original exchange continues. Only
        an actual selected-game host permit can send STOP. Require peer EOF,
        then the owner must join Lua lifecycle and actual MAME0 before it stops
        SocketServer and releases this bridge. A send/EOF alone is not validity.
        """
        try:
            peer.settimeout(5);origin.settimeout(5)
            peer.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            origin.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            normal=recv_exact(peer,2)
            handshake,=struct.unpack('>H',normal)
            require(handshake>>14==1 and ((handshake>>1)&8191)==self.subject['slot'],
                    'Original forced-eval slot handshake differs')
            actual=codec.decode_handshake(recv_exact(peer,codec.HANDSHAKE.size))
            require(actual==self.subject,'Original custom session handshake differs')
            origin.sendall(normal)
            self.find_client()
            # Header/whole-ROM bytes precede the client's first socket open.
            self.trace.loaded_rom()
            while not self.stop_sent.is_set():
                require(not self.stop_event.is_set(),'Original full-tail exchange interrupted')
                size,=struct.unpack('>I',recv_exact(peer,4))
                require(codec.REQUEST.size<=size<=codec.REQUEST.size+codec.MAX_PAYLOAD+codec.MAX_META,
                        'Original startup envelope length differs')
                self.process(peer,origin,recv_exact(peer,size))
            peer.settimeout(30)
            require(peer.recv(1)==b'','Unexpected request/partial bytes after original STOP')
            self.trace.verify_closed_unchanged()
            self.final_ledger=self.ledger.finalize(self.stop_receipt)
            self.emit(dict(kind='original_drained_peer_EOF',receipt=self.stop_receipt,
                           ledger=self.final_ledger,closed_prefix=self.trace.closed_pin))
            self.peer_eof.set()
            require(self.stop_event.wait(self.parked_origin_timeout_s),'Owner did not intentionally close completed full-tail origin')
            require(self.server.shutdown_event.is_set(),'Origin must stop before bridge release')
        except Exception as error:
            self.error=repr(error)
            self.emit(dict(kind='original_proxy_failure',sequence=self.sequence,error=self.error))
            raise
