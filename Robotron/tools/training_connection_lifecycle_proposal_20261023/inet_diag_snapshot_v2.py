"""Unselected fixed-query kernel TCP evidence. No retries or row normalization."""
import base64,hashlib,math,secrets,socket,struct,time

SCHEMA='robotron-original-inet-diag-snapshot-v2'
MAX_BYTES=16<<20
DATAGRAM_BYTES=1<<20
MAX_DATAGRAMS=512
SNAPSHOT_KEYS={'schema','begin_unix_s','end_unix_s','sequence','portid','request_base64','datagrams','error'}
DATAGRAM_KEYS={'bytes','sha256','base64','flags','sender','ancillary'}

def require(value,message):
    if not value:raise ValueError(message)

def request(sequence,portid):
    require(type(sequence)is int and 0<sequence<=0xffffffff and type(portid)is int and 0<portid<=0xffffffff,
        'Exact nonzero original diagnostic sequence/portid required')
    body=struct.pack('=BBBBI',socket.AF_INET,socket.IPPROTO_TCP,0,0,0xfff)+bytes(40)+struct.pack('=II',0xffffffff,0xffffffff)
    return struct.pack('=IHHII',72,20,0x301,sequence,portid)+body

def messages(data):
    require(type(data)is bytes and 0<len(data)<=DATAGRAM_BYTES,'Bounded original diagnostic datagram required')
    position=0
    while position<len(data):
        require(len(data)-position>=16,'Truncated original netlink header')
        length,kind,flags,seq,pid=struct.unpack_from('=IHHII',data,position)
        require(length>=16 and position+length<=len(data),'Malformed original netlink message size')
        aligned=(length+3)&~3
        require(position+aligned<=len(data),'Truncated original netlink alignment')
        yield dict(length=length,kind=kind,flags=flags,sequence=seq,portid=pid,payload=data[position+16:position+length])
        position+=aligned
    require(position==len(data),'Original netlink bytes not fully consumed')

def capture():
    result=dict(schema=SCHEMA,begin_unix_s=time.time(),end_unix_s=None,sequence=secrets.randbelow(0xffffffff)+1,
        portid=None,request_base64=None,datagrams=[],error=None)
    deadline=time.monotonic()+.4;total=0
    try:
        with socket.socket(socket.AF_NETLINK,socket.SOCK_DGRAM,4)as sock:
            sock.bind((0,0));result['portid']=sock.getsockname()[0];sock.settimeout(.3)
            raw=request(result['sequence'],result['portid']);result['request_base64']=base64.b64encode(raw).decode()
            require(sock.sendto(raw,(0,0))==72,'Original diagnostic request short send')
            done=False
            while not done:
                require(time.monotonic()<deadline and len(result['datagrams'])<MAX_DATAGRAMS,'Bounded original socket dump exceeded')
                data,ancillary,flags,address=sock.recvmsg(DATAGRAM_BYTES);total+=len(data)
                # Preserve received bytes/sender/flags before asserting anything.
                result['datagrams'].append(dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),base64=base64.b64encode(data).decode(),
                    flags=flags,sender=list(address),ancillary=[repr(x)for x in ancillary]))
                require(total<=MAX_BYTES and data and not ancillary and flags==0 and address==(0,0),'Unknown/truncated nonkernel socket-dump datagram')
                done=any(message['kind']==3 for message in messages(data))
    except BaseException as error:result['error']=repr(error)
    result['end_unix_s']=time.time();return result

def parse(value):
    require(type(value)is dict and set(value)==SNAPSHOT_KEYS and value['schema']==SCHEMA and value['error']is None,
        'Exact original complete socket-dump envelope required')
    expected=request(value['sequence'],value['portid'])
    require(type(value['request_base64'])is str and len(value['request_base64'])==96,'Exact fixed-query request bytes required')
    require(base64.b64decode(value['request_base64'],validate=True)==expected,'Foreign or partial original TCP/IPv4 query')
    require(all(type(value[k])in (int,float)and math.isfinite(value[k])for k in ('begin_unix_s','end_unix_s'))
        and 0<value['begin_unix_s']<value['end_unix_s'] and value['end_unix_s']-value['begin_unix_s']<=.5,'Unbounded original socket-dump epoch')
    require(type(value['datagrams'])is list and 0<len(value['datagrams'])<=MAX_DATAGRAMS,'Complete bounded datagram list required')
    result=[];done=False;seen=set();all_rows=0;total=0
    for datagram in value['datagrams']:
        require(type(datagram)is dict and set(datagram)==DATAGRAM_KEYS,'Exact original datagram metadata required')
        require(type(datagram['bytes'])is int and 0<datagram['bytes']<=DATAGRAM_BYTES
            and type(datagram['base64'])is str and len(datagram['base64'])<=(DATAGRAM_BYTES+2)//3*4,'Bounded original encoded datagram required')
        data=base64.b64decode(datagram['base64'],validate=True);total+=len(data)
        require(total<=MAX_BYTES and len(data)==datagram['bytes']and hashlib.sha256(data).hexdigest()==datagram['sha256'],'Original socket-dump bytes differ')
        require(type(datagram['sender'])is list and len(datagram['sender'])==2 and all(type(x)is int and x==0 for x in datagram['sender'])
            and type(datagram['flags'])is int and datagram['flags']==0 and datagram['ancillary']==[],
            'Nonkernel/truncated original datagram')
        for message in messages(data):
            require(not done and message['sequence']==value['sequence']and message['portid']==value['portid'],'Foreign or post-terminal socket-dump message')
            require(message['flags']==2,'Interrupted or unexpected socket-dump flags')
            body=message['payload']
            if message['kind']==3:
                require(len(body)==4 and struct.unpack('=i',body)[0]==0,'Unsuccessful original socket-dump termination');done=True;continue
            require(message['kind']==20 and len(body)>=72 and body[0]==socket.AF_INET,'Unknown original inet_diag message')
            all_rows+=1;sport,dport=struct.unpack_from('!HH',body,4)
            if sport!=9998 and dport!=9998:continue
            state=body[1];require(1<=state<=12,'Unknown original TCP state')
            require(body[12:24]==bytes(12)and body[28:40]==bytes(12),'Non-IPv4 diagnostic address bytes')
            src=struct.unpack_from('<I',body,8)[0];dst=struct.unpack_from('<I',body,24)[0];uid,inode=struct.unpack_from('=II',body,64)
            row=dict(local='%08X:%04X'%(src,sport),peer='%08X:%04X'%(dst,dport),state='%02X'%state,uid=uid,inode=inode)
            identity=tuple(row[k]for k in ('local','peer','state','inode'))
            require(identity not in seen,'Duplicate original diagnostic socket row');seen.add(identity);result.append(row)
    require(done and result,'Original terminated nonempty socket dump required')
    return result,dict(all_kernel_socket_rows=all_rows,selected_rows=len(result),complete_raw_bytes=total,datagrams=len(value['datagrams']))
