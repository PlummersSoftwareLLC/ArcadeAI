"""Selected full-observation bridge to the unchanged isolated frozen server.

No listeners, imports of Torch, file writes or process actions occur on import.
The owning diagnostic must bind original actor birth, source/ROM/policy inputs,
fresh trace inode, ports and intentional shutdown. This is not a quality runner.
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

import startup_handoff_v1 as authority
import wire_codec_v1 as codec
from boot_readiness_v1 import boot_readiness


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
            require(row.get('schema')=='robotron-full-policy-startup-trace-v1'
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


class StartupProxy:
    def __init__(self,server,*,slot,session,connection,trace_path,trace_identity,
                 rom_sha256,policy_reader,admission_reader,frame_parser,emit,stop_event,
                 wall_ns=time.time_ns,monotonic_ns=time.monotonic_ns):
        self.server=server
        self.subject=dict(slot=slot,session=session,connection=connection)
        require(codec.decode_handshake(codec.encode_handshake(**self.subject))==self.subject,
                'Explicit original proxy subject required')
        self.trace=TracePrefix(trace_path,trace_identity,self.subject,rom_sha256)
        self.rom_sha256=rom_sha256
        self.policy_reader,self.admission_reader=policy_reader,admission_reader
        self.frame_parser,self.emit,self.stop_event=frame_parser,emit,stop_event
        self.wall_ns,self.monotonic_ns=wall_ns,monotonic_ns
        self.sent_complete=threading.Event()
        self.sequence=0
        self.issuer=None
        self.handoff=None
        self.error=None
        self.cid=None

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
        if self.issuer is None:
            require(meta['mode']=='gated'and meta['nonce']=='0'*64,'Premature startup bypass')
        else:
            require(meta['nonce']==self.issuer.nonce,'Actual input nonce did not echo original response')
            require(meta['mode']in (['latched','legacy']if self.handoff else ['authorized']),
                    'Original startup phase differs')
            if not self.handoff:
                require(meta['first_play_sequence']==-1,'Actual play preceded journal handoff')
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
            self.emit(dict(kind='actual_policy_journal_handoff',sequence=sequence,
                           result=self.handoff,certificate=json.loads(permit.payload)))
        window_open=self.open_window()
        can_start=(self.issuer is None and accepted and window_open
                   and meta['planned_start']==1 and meta['status']==243 and meta['credit']==1
                   and meta['first_play_sequence']==-1)
        readiness=boot_readiness(self.trace.rows(meta['event']),meta)if can_start else None
        can_start=bool(can_start and readiness is not None)
        if can_start:
            self.emit(dict(kind='original_boot_coin_readiness',sequence=sequence,readiness=readiness))
            self.issuer=authority.StartupHandoff(self.server.game_journal,client_id=self.cid,
                slot=self.subject['slot'],session=self.subject['session'],connection=self.subject['connection'],
                expected_rom_sha256=self.rom_sha256,policy_reader=self.policy_reader,
                admission_reader=self.admission_reader,wall_ns=self.wall_ns,monotonic_ns=self.monotonic_ns)
            self.issuer.loaded_rom(self.trace.loaded_rom())
            def send_authorization(response):
                self.emit(dict(kind='before_authorizing_response',sequence=sequence,
                               response_hex=response.hex(),host_unix_ns=self.wall_ns(),
                               host_monotonic_ns=self.monotonic_ns()))
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
            response=codec.encode_response(sequence,action,start=start,coin=coin,
                nonce=self.issuer.nonce if self.issuer else '0'*64,latched=self.handoff is not None)
            self.emit(dict(kind='before_wrapped_response',sequence=sequence,
                           response_hex=response.hex(),host_unix_ns=self.wall_ns()))
            peer.sendall(response)
        self.sequence=sequence
        self.emit(dict(kind='response_send_complete',sequence=sequence,host_monotonic_ns=self.monotonic_ns()))

    def serve(self,peer,origin):
        """Caller owns sockets and stops origin BEFORE releasing this bridge.

        After frame1200 the origin connection stays open. The runtime must wait
        for the original MAME exit/footer, intentionally stop SocketServer, then
        set stop_event. A successful send is not proof of client application.
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
            for _ in range(1200):
                require(not self.stop_event.is_set(),'Original prefix interrupted')
                size,=struct.unpack('>I',recv_exact(peer,4))
                require(codec.REQUEST.size<=size<=codec.REQUEST.size+codec.MAX_PAYLOAD+codec.MAX_META,
                        'Original startup envelope length differs')
                self.process(peer,origin,recv_exact(peer,size))
            self.sent_complete.set()
            require(self.stop_event.wait(30),'Owner did not intentionally close completed prefix')
            require(self.server.shutdown_event.is_set(),'Origin must stop before bridge release')
        except Exception as error:
            self.error=repr(error)
            self.emit(dict(kind='original_proxy_failure',sequence=self.sequence,error=self.error))
            raise
