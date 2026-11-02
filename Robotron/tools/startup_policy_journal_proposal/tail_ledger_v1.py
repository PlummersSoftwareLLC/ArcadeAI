"""Bounded host evidence for every original exchange after startup.

The rolling digest commits to bytes actually seen by this bridge. Checkpoints
do not reconstruct postprefix raw frames or prove client input application.
Those limits are explicit; complete-game/journal and final Lua lifecycle joins
remain separate requirements. No work or filesystem access occurs on import.
"""
import hashlib
import json
import os
import stat
import struct


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


class BoundedWitness:
    def __init__(self,stream,*,max_bytes=64*1024*1024,max_rows=8192):
        s=os.fstat(stream.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_size==0 and s.st_uid==os.getuid()
                and s.st_nlink==1,'Fresh owned regular witness stream required')
        require(type(max_bytes)is int and 1<=max_bytes<=64*1024*1024
                and type(max_rows)is int and 1<=max_rows<=8192,'Witness bounds differ')
        self.stream=stream;self.max_bytes=max_bytes;self.max_rows=max_rows
        self.rows=self.bytes=0
        self.identity=(s.st_dev,s.st_ino,s.st_uid,s.st_nlink)

    def emit(self,row):
        require(type(row)is dict and 'proxy_event'not in row,'Original witness record required')
        raw=canonical(dict(row,proxy_event=self.rows+1))+b'\n'
        require(len(raw)<=65536 and self.rows<self.max_rows
                and self.bytes+len(raw)<=self.max_bytes,'Original witness capacity exceeded')
        s=os.fstat(self.stream.fileno())
        require((s.st_dev,s.st_ino,s.st_uid,s.st_nlink)==self.identity and s.st_size==self.bytes,
                'Original witness stream changed outside this writer')
        require(self.stream.write(raw)==len(raw),'Original witness short write')
        self.stream.flush()
        self.rows+=1;self.bytes+=len(raw)


class TailLedger:
    def __init__(self,subject,rom_sha256,emit):
        self.subject=dict(subject)
        self.emit=emit
        self.sequence=self.accepted=self.rejected=self.payload_bytes=self.checkpoints=0
        self.last_ordinal=None
        self.closed=False
        self.stop_receipt=None
        self.digest=hashlib.sha256(canonical(dict(schema='robotron-all-exchange-tail-ledger-v1',
            subject=self.subject,loaded_rom_sha256=rom_sha256))).digest()
        self.emit(dict(kind='tail_ledger_header',subject=self.subject,loaded_rom_sha256=rom_sha256,
            seed_sha256=self.digest.hex(),checkpoint_interval=4096,max_checkpoints=4096,
            raw_prefix_frames=1200,postprefix_raw_reconstructable=False))

    def record(self,*,payload,meta,action,response,before,after,accepted,drain_receipt=None):
        require(not self.closed and self.stop_receipt is None,'Original ledger already stopped or finalized')
        sequence=meta['sequence']
        require(type(sequence)is int and sequence==self.sequence+1 and sequence<=0xffffffff
                and all(meta[k]==v for k,v in self.subject.items()),'Original ledger subject/sequence differs')
        require(type(payload)is bytes and len(payload)==7597 and type(action)is bytes and len(action)==6
                and type(response)is bytes and len(response)==48 and response[:4]==b'RSP2'
                and int.from_bytes(response[4:8],'big')==sequence and response[-6:]==action,
                'Original ledger wire/action differs')
        require(type(accepted)is bool and type(before['frames'])is type(after['frames'])is int
                and after['frames']==before['frames']+int(accepted)
                and (self.last_ordinal is None or before['frames']==self.last_ordinal),
                'Original ledger accepted ordinal differs')
        stop=bool(response[8]&4)
        require(stop==(drain_receipt is not None),'STOP and actual host consumption receipt differ')
        if stop:
            require(sequence>1200 and drain_receipt['consumed_before_send']is True
                    and drain_receipt['sequence']==sequence
                    and all(drain_receipt[k]==v for k,v in self.subject.items())
                    and drain_receipt['nonce']==meta['nonce'],'Original host STOP receipt differs')
        # Length-prefix every component. Keep only a constant-size digest and
        # counters; never allocate payload.hex() or per-frame tail log rows.
        parts=(struct.pack('>I',sequence),payload,canonical(meta),action,response,
               canonical(dict(before=before,after=after,accepted=accepted,drain_receipt=drain_receipt)))
        chain=hashlib.sha256();chain.update(self.digest)
        for part in parts:chain.update(struct.pack('>I',len(part)));chain.update(part)
        self.digest=chain.digest()
        self.sequence=sequence;self.last_ordinal=after['frames']
        self.accepted+=int(accepted);self.rejected+=int(not accepted);self.payload_bytes+=len(payload)
        if stop:self.stop_receipt=canonical(drain_receipt)
        if sequence==1200 or sequence%4096==0:self.checkpoint('startup_anchor'if sequence==1200 else 'periodic')

    def summary(self):
        return dict(sequence=self.sequence,exchange_count=self.accepted+self.rejected,
            accepted=self.accepted,rejected=self.rejected,last_accepted_ordinal=self.last_ordinal,
            original_payload_bytes=self.payload_bytes,chain_sha256=self.digest.hex(),
            checkpoint_count=self.checkpoints,postprefix_raw_reconstructable=False)

    def checkpoint(self,reason):
        require(not self.closed and self.checkpoints<4096,'Original ledger checkpoint capacity exceeded')
        self.checkpoints+=1
        self.emit(dict(kind='tail_ledger_checkpoint',reason=reason,**self.summary()))

    def finalize(self,drain_receipt):
        require(not self.closed and self.sequence>1200 and type(drain_receipt)is dict
                and drain_receipt['sequence']==self.sequence
                and canonical(drain_receipt)==self.stop_receipt,'Original drained terminal ledger required')
        self.checkpoint('drained_peer_EOF')
        self.closed=True
        return self.summary()
