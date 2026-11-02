"""Actual kernel-payload compatibility and explicit synthetic rejection fixtures."""
import argparse,base64,copy,hashlib,importlib.util,json,os,socket,struct,sys,time
from pathlib import Path
from unittest.mock import patch
def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def pack(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode(),flags=0,sender=[0,0],ancillary=[])
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-inet-diag-filtered-capture-contracts-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_inet_contract_h');rd=load(job['reader'],'_inet_contract_r')
    def read(pin,as_json=True):return rd.read_pin(pin,as_json=as_json)
    for pin in job['inputs']:h.checked(pin)
    helper=load(job['helper'],'_inet_contract_helper');primitives=load(job['primitives'],'_inet_contract_primitive');io=load(job['io'],'_inet_contract_io')
    prototype=load(job['prototype'],'_inet_contract_prototype');report=read(job['prototype_report']);root=Path(job['output']);root.mkdir(mode=0o700)
    positives=[];first=None
    for item in report['records']:
        original=read(item['original_netlink']);value=dict(original,schema=helper.SCHEMA)
        expected,summary=prototype.parse(original)
        assert helper.parse(value)==(expected,summary)
        envelope=json.dumps(value,separators=(',',':'),allow_nan=False).encode()+b'\n'
        assert primitives.tcp(envelope)==expected
        with patch.object(io,'_inet_capture',lambda:value):meta,returned=io.tcp()
        assert returned==envelope and meta['begin_unix_s']==value['begin_unix_s']and meta['end_unix_s']==value['end_unix_s']
        positives.append(dict(original=item['original_netlink'],actual_kernel_payload_bytes_unchanged=True,original_filtered_envelope_schema_unchanged=True,rows=len(expected)))
        if first is None:first=value
    assert len(positives)==40
    # A tiny SYNTHETIC message-format fixture keeps one original selected socket
    # message and a terminal marker. It never represents a full192 observation.
    target=None
    for d in first['datagrams']:
        data=base64.b64decode(d['base64']);offset=0
        for m in helper.messages(data):
            if m['kind']==20 and len(m['payload'])>=72:
                sport,dport=struct.unpack_from('!HH',m['payload'],4)
                if sport==9998 or dport==9998:target=data[offset:offset+((m['length']+3)&~3)];break
            offset+=(m['length']+3)&~3
        if target is not None:break
    assert target is not None
    footer=struct.pack('=IHHIIi',20,3,2,first['sequence'],first['portid'],0)
    base=copy.deepcopy(first);base['datagrams']=[pack(target+footer)];assert len(helper.parse(base)[0])==1
    negative=[]
    def reject(name,mutation,selected=base):
        value=copy.deepcopy(selected);mutation(value)
        try:helper.parse(value)
        except ValueError as error:negative.append(dict(case=name,error=str(error)))
        else:raise AssertionError('Malformed synthetic socket evidence accepted: '+name)
    for name,key,value in [('schema','schema','other'),('extra','extra',0),('error','error','failed'),('sequence_bool','sequence',True),('sequence_zero','sequence',0),
        ('sequence_overflow','sequence',1<<32),('portid_bool','portid',True),('portid_zero','portid',0),('portid_overflow','portid',1<<32),
        ('begin_bool','begin_unix_s',True),('begin_negative','begin_unix_s',-1.),('end_nan','end_unix_s',float('nan')),('end_inf','end_unix_s',float('inf')),
        ('end_zero_span','end_unix_s',base['begin_unix_s']),('end_late','end_unix_s',base['begin_unix_s']+.500001),('no_datagrams','datagrams',[]),('many_datagrams','datagrams',base['datagrams']*513)]:
        reject(name,lambda d,k=key,v=value:d.update({k:v}))
    for key in sorted(helper.SNAPSHOT_KEYS):reject('missing_envelope_'+key,lambda d,k=key:d.pop(k))
    request=base64.b64decode(base['request_base64'])
    for index in range(len(request)):
        changed=bytearray(request);changed[index]^=1
        reject('fixed_request_byte_%02d'%index,lambda d,b=bytes(changed):d.update(request_base64=base64.b64encode(b).decode()))
    reject('bad_request_encoding',lambda d:d.update(request_base64='?'*152))
    for key in sorted(helper.DATAGRAM_KEYS):reject('missing_datagram_'+key,lambda d,k=key:d['datagrams'][0].pop(k))
    for key,value in [('extra',0),('bytes',True),('bytes',0),('bytes',(1<<20)+1),('sha256','0'*64),('base64','?'),('flags',True),('flags',socket.MSG_TRUNC),('flags',socket.MSG_CTRUNC),('sender',[1,0]),('sender',[0,1]),('sender',[False,0]),('ancillary',['unknown'])]:
        reject('datagram_'+key+'_'+str(value),lambda d,k=key,v=value:d['datagrams'][0].update({k:v}))
    def packet(name,raw):reject(name,lambda d:d.update(datagrams=[pack(raw)]))
    for name,offset,fmt,value in [('length_small',0,'=I',15),('length_past_packet',0,'=I',len(target+footer)+1),('kind_error',4,'=H',2),('kind_unknown',4,'=H',99),
        ('interrupted_dump',6,'=H',18),('flags_unknown',6,'=H',0),('filtered_dump_interrupted',6,'=H',50),('foreign_sequence',8,'=I',base['sequence']^1),('foreign_portid',12,'=I',base['portid']^1),
        ('wrong_family',16,'B',socket.AF_INET6),('state_zero',17,'B',0),('state_unknown',17,'B',255),('nonIPv4_source',28,'B',1),('nonIPv4_destination',44,'B',1)]:
        changed=bytearray(target+footer);struct.pack_into(fmt,changed,offset,value);packet(name,bytes(changed))
    foreign_ports=bytearray(target+footer);struct.pack_into('!HH',foreign_ports,20,22,23);packet('socket_outside_fixed_kernel_port_query',bytes(foreign_ports))
    packet('empty_packet',b'');packet('truncated_header',(target+footer)[:15]);packet('truncated_body',target[:25]);packet('no_DONE',target)
    packet('post_DONE',footer+target);packet('two_DONE',target+footer+footer);packet('duplicate_socket',target+target+footer)
    changed=bytearray(target);uid=struct.unpack_from('=I',changed,80)[0];struct.pack_into('=I',changed,80,uid^1)
    packet('duplicate_socket_conflicting_UID',target+bytes(changed)+footer)
    bad_footer=bytearray(footer);struct.pack_into('=i',bad_footer,16,-1);packet('DONE_error',target+bytes(bad_footer))
    packet('DONE_wrong_length',target+struct.pack('=IHHII',16,3,2,base['sequence'],base['portid']))
    for name,raw in [('no_newline',json.dumps(base).encode()),('old_proc',b'  sl local_address rem_address\n'),('duplicate_JSON_keys',b'{"schema":1,"schema":2}\n'),('nonfinite_JSON',b'{"value":NaN}\n'),('too_large',b'x'*((2<<20)+1)+b'\n')]:
        try:primitives.tcp(raw)
        except ValueError as error:negative.append(dict(case='primitive_'+name,error=str(error)))
        else:raise AssertionError('Malformed raw primitive envelope accepted: '+name)
    # Failed capture must reach the caller as original bytes, never an omitted
    # observation. These are explicit syscall-return fixtures in this CPU suite.
    capture_failures=[]
    for case in ('truncated','foreign_sender','ancillary','malformed','timeout'):
        instances=[]
        class Fake:
            def __init__(self,*args):assert args==(socket.AF_NETLINK,socket.SOCK_DGRAM,4);self.calls=0;self.closed=False;instances.append(self)
            def __enter__(self):return self
            def __exit__(self,*unused):self.closed=True
            def bind(self,address):assert address==(0,0)
            def getsockname(self):return(4242,0)
            def settimeout(self,value):assert value==.3
            def sendto(self,data,address):self.request=data;assert address==(0,0);return len(data)
            def recvmsg(self,size):
                assert size==1<<20;self.calls+=1
                if case=='timeout':raise TimeoutError('explicit synthetic timeout')
                seq,pid=struct.unpack_from('=II',self.request,8);data=struct.pack('=IHHIIi',20,3,2,seq,pid,0)
                if case=='malformed':data=b'x'
                return(data,[('synthetic',)]if case=='ancillary'else[],socket.MSG_TRUNC if case=='truncated'else 0,(123,0)if case=='foreign_sender'else(0,0))
        with patch.object(helper.socket,'socket',Fake):value=helper.capture()
        assert len(instances)==1 and instances[0].closed and instances[0].calls==1 and value['error']is not None
        with patch.object(io,'_inet_capture',lambda:value):meta,returned=io.tcp()
        assert json.loads(returned)==value and meta['original_capture_error']==value['error']
        try:primitives.tcp(returned)
        except ValueError:pass
        else:raise AssertionError('Failed original syscall fixture accepted')
        capture_failures.append(dict(case=case,one_receive_no_retry=True,failed_original_bytes_returned=True,error=value['error']))
    assert 'torch'not in sys.modules
    pin=h.put(root/'report.json',dict(schema='robotron-inet-diag-filtered-capture-contracts-report-v1',helper=job['helper'],source_provenance=job['source_provenance'],actual_filtered40_kernel_payload_compatibility=positives,
        negative_checks=negative,synthetic_single_socket_fixture_explicit=True,synthetic_syscall_failure_fixtures=capture_failures,
        old_failed_jobs_not_replayed_with_new_sources=True,original_health_game_and_clock_limits_unchanged=True,production_changed=False,scientific_selection=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=pin,old_actual_payloads=40,negative_checks=len(negative),capture_failure_cases=len(capture_failures))),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
