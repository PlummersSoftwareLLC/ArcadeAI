"""Read-only local ROM/startup mapping; no emulator, model, device or protocol change."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import zipfile
import zlib

GAME=Path(__file__).resolve().parents[2]
RUN=GAME/'logs/managed-learning-20261015/run-26'
OUTPUT=RUN/'readonly-ROM-startup-binary-map-original01-20261020'
CAMPAIGN=GAME/'logs/managed-learning-20261015/quality-CE1059M-vs-tail9000-fresh-next8M-quality32-trial01-20261019'
PREPARATION=RUN/'quality32-CE1059-vs-tail9000-fresh-main-next8M-original01-preparation-20261019'
UPSTREAM={
    'upstream-williams-mame0264.cpp':'eaf05a98d382270cb7a8d6ca2394ee2fc21a6fefc0ab5dba9f7d51c059159aff',
    'upstream-williams-machine-mame0264.cpp':'1c4bdafff84f29cb8e410d26bf9b9678b2c5d795866ab1fe69f033175bc3bbb4',
    'upstream-6x09dasm-mame0264.cpp':'82245e6f635eb65dd2fb79e03b417264da33cbf34b58830e0652dd05ddc3ee40',
    'upstream-base6x09-mame0264.lst':'5fe1cc954a21956d2d3a86f66af4b3a26c1f266a39001e1a6397348ff2cbd85a',
    'upstream-m6809-mame0264.lst':'e382a8c379a9058bfd87479dd03d16d1599ec6dd6fdec362b579c248b9fad7a7',
    'upstream-m6809-mame0264.h':'11eeb4d91f82b46a9e1fdf6f0a7393e926be246b26f41e4d784d232914aea266',
}


def require(value,message):
    if not value:raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(s.st_mode&0o777),uid=s.st_uid,nlink=s.st_nlink)


def analyze(output):
    require(output==OUTPUT and output.is_dir() and output==output.resolve(),'Exact unused evidence output required')
    require(not (output/'ROM-startup-binary-map.json').exists(),'Original offline analysis already consumed')
    rp=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(hashlib.sha256(rp.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','Exact evidence reader required')
    spec=importlib.util.spec_from_file_location('_ROM_map_reader_'+str(time.time_ns()),rp)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    inputs={};copies={}
    def save(name,raw):
        p=output/name
        with p.open('xb') as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        return reader.pin(p)
    def value(name,obj):return save(name,(json.dumps(obj,indent=2,allow_nan=False)+'\n').encode())
    def local(path,name=None):
        pin=reader.pin(path);raw=Path(path).read_bytes()
        require(reader.pin(path)==pin and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Local source/input changed')
        inputs[str(path)]=pin
        if name:copies[str(path)]=save(name,raw)
        return raw
    sources={}
    for name,sha in UPSTREAM.items():
        p=output/name;pin=reader.pin(p);require(pin['sha256']==sha,'Primary upstream source differs')
        sources[name]=dict(pin=pin,text=reader.read_pin(pin,as_json=False).decode())
    for name in ['RRF.ASM','RRG23.ASM','RRS22.ASM','RRSCRIPT.ASM','RRLOG.ASM','RRELESE6.ASM','ASSEMBLY.md','link_williams_rom.sh']:
        local(GAME/'Code/Williams'/name,'local-'+name+'.readonly')
    local(Path(__file__).resolve(),'analyzer-source.readonly.py')
    mame=reader.pin('/usr/games/mame');inputs[mame['path']]=mame
    # No MAME binary is executed. All ROM and assembly producer modes stay intact.
    romfiles=sorted((GAME/'roms/robotron').iterdir())
    require(len(romfiles)==15 and all(p.is_file() and not p.is_symlink() for p in romfiles),'Exact local ROM inventory required')
    loose={p.name:local(p,'loose-'+p.name+'.readonly') for p in romfiles}
    legacy_path=GAME/'roms/robotron.zip';blue_path=GAME/'roms/robotron-bluelabel.zip'
    local(legacy_path,'legacy-robotron.zip.readonly');local(blue_path,'blue-robotron.zip.readonly')
    def unzip(path):
        with zipfile.ZipFile(path) as z:
            infos=z.infolist();require(len(infos)<=32 and sum(e.file_size for e in infos)<=200000,'Bounded local ROM archive required')
            require(len({e.filename for e in infos})==len(infos),'Duplicate archive members')
            return {e.filename:z.read(e) for e in infos}
    legacy,blue=unzip(legacy_path),unzip(blue_path)
    def hashes(raw):return dict(bytes=len(raw),CRC32=f'{zlib.crc32(raw):08x}',SHA1=hashlib.sha1(raw).hexdigest(),SHA256=hashlib.sha256(raw).hexdigest())
    archives=dict(loose={k:hashes(v) for k,v in loose.items()},legacy={k:hashes(v) for k,v in legacy.items()},blue={k:hashes(v) for k,v in blue.items()})
    driver=sources['upstream-williams-mame0264.cpp']['text']
    block=re.search(r'ROM_START\( robotron \).*?ROM_END',driver,re.S).group()
    loads=re.findall(r'ROM_LOAD\(\s*"([^"]+)"\s*,\s*(0x[0-9a-f]+)\s*,\s*(0x[0-9a-f]+)\s*,\s*CRC\(([0-9a-f]+)\)\s*SHA1\(([0-9a-f]+)\)',block)
    require(len(loads)==15 and {r[0] for r in loads}==set(loose)==set(blue),'Primary parent-set inventory differs')
    cpu=[];images={key:bytearray([255])*65536 for key in ('loose','blue','legacy')};differences=[]
    for name,offset,size,crc,sha1 in loads:
        require(hashes(blue[name])['CRC32']==crc and hashes(blue[name])['SHA1']==sha1 and len(loose[name])==int(size,16),'Parent source/blue archive mismatch')
        match=re.fullmatch(r'2084_rom_(\d+)b_.*',name)
        if not match:continue
        n=int(match[1]);oldname='robotron.sb'+format(n,'x');actual=loose[name];parent=blue[name]
        require(actual==legacy[oldname],'Loose CPU chip does not match legacy archive member')
        region=int(offset,16);logical=region-0x10000 if region>=0x10000 else region
        for kind,raw in [('loose',actual),('blue',parent),('legacy',legacy[oldname])]:images[kind][logical:logical+4096]=raw
        changes=[i for i,(a,b) in enumerate(zip(actual,parent)) if a!=b]
        cpu.append(dict(chip=n,name=name,legacy_member=oldname,region_offset=region,logical_ROM_address=logical,bytes=4096))
        if changes:differences.append(dict(chip=n,name=name,bytes_differing=len(changes),first_changed_logical_addresses=[logical+i for i in changes[:16]]))
    require(len(cpu)==12 and len(differences)==6,'Actual local ROM variant inventory differs')
    machine=sources['upstream-williams-machine-mame0264.cpp']['text']
    require('configure_entry(1, memregion("maincpu")->base() + 0x10000)' in machine and 'm_mainbank->configure_entry(0, m_videoram)' in machine
        and 'm_mainbank->set_entry(data & 0x01)' in machine,'Upstream ROM/VRAM bank model differs')
    # Derive direct-page RAM symbols from the actual local source allocation.
    symbols={};at=None
    for line in (GAME/'Code/Williams/RRF.ASM').read_text().splitlines():
        if re.match(r'\s*ORG\s+\$9800\b',line):at=0x9800;continue
        if at is None:continue
        if line.lstrip().startswith('*'):continue
        m=re.match(r'^\s*(?:(\w+)\s+)?RMB\s+(\d+)\b',line)
        if m:
            if m[1]:symbols[m[1]]=at
            at+=int(m[2])
            if m[1]=='STATUS':break
    require({k:symbols[k] for k in ('STATUS','CREDIT','CURPLR','PLRCNT','BUNITS','CUNITS')}==dict(STATUS=0x9859,CREDIT=0x9851,CURPLR=0x983f,PLRCNT=0x9840,BUNITS=0x984f,CUNITS=0x9850),'Local direct-page symbols differ')
    image=images['loose'];require(image[0xd000]==0x7e,'OS INIT vector must be JMP extended')
    init=int.from_bytes(image[0xd001:0xd003],'big')
    init_bytes=bytes.fromhex('1a ff 10 ce bf 70 86 98 1f 8b 86 01 b7 c9 00')
    require(init==0xd106 and image[init:init+len(init_bytes)]==init_bytes,'Actual ROM direct-page/bank initialization differs')
    require(image[0x26cc]==0x7e,'STRT1 vector must be JMP extended')
    start=int.from_bytes(image[0x26cd:0x26cf],'big');require(start==0x26fc,'Actual STRT1 target differs')
    expected=bytes.fromhex('86 01 10 8e c3 b3 0d 59 2a f3 f6 cc 05 c4 0f c1 09 26 02 97 51 91 51 22 e4')
    require(image[start:start+len(expected)]==expected,'Actual first-start gate differs')
    require(all(v[0x26c0:0x27b5]==image[0x26c0:0x27b5] for v in images.values()),'Startup region is not common to the local variants')
    # Decode just this bounded gate using the versioned upstream opcode table.
    table=sources['upstream-6x09dasm-mame0264.cpp']['text'].split('m6x09_disassembler::m6x09_opcodes[] =',1)[1].split('const char m6809_disassembler',1)[0]
    opcodes={int(op,16):(int(n),name,mode) for op,n,name,mode in re.findall(r'\{\s*(0x[0-9A-Fa-f]+),\s*(\d+),\s*"([A-Z0-9]+)",\s*(\w+),\s*M6x09_GENERAL',table)}
    decoded=[];pc=start
    while pc<start+len(expected):
        begin=pc;opcode=image[pc];pc+=1
        if opcode in (0x10,0x11):opcode=opcode*256+image[pc];pc+=1
        count,name,mode=opcodes[opcode];data=bytes(image[pc:pc+count]);pc+=count
        require(mode in ('IMM','DIR','EXT','REL'),'Unexpected instruction in bounded start gate')
        operand=int.from_bytes(data,'big')
        row=dict(pc=begin,bytes=bytes(image[begin:pc]).hex(),mnemonic=name,mode=mode,operand=operand)
        if mode=='DIR':row['effective_address_if_DP_98']=0x9800+operand
        if mode=='REL':row['branch_target']=(pc+int.from_bytes(data,'big',signed=True))&65535
        decoded.append(row)
    require(pc==start+len(expected),'Gate decode ended inside an instruction')
    require([(r['mnemonic'],r.get('branch_target')) for r in decoded if r['mode']=='REL']==[('BPL',0x26f9),('BNE',0x2711),('BHI',0x26f9)],'Decoded gate branch targets differ')
    require(image[0x26f9:0x26fc]==bytes.fromhex('7e d0 63'),'Refusal must jump to SUCIDE vector')
    require('case 0x2A:              set_cond(cond_pl())' in sources['upstream-m6809-mame0264.lst']['text']
        and 'cond_pl() { return !(m_cc & CC_N); }' in sources['upstream-m6809-mame0264.h']['text'],
        'Primary BPL semantics differ')
    def locate(raw):
        data=bytes.fromhex(raw);positions=[i for i in range(start,0x2800-len(data)+1) if image[i:i+len(data)]==data]
        require(len(positions)==1,'Startup write pattern is missing or ambiguous')
        return dict(address=positions[0],bytes=data.hex())
    writes=dict(accepted_setup=locate('86 7f 97 59 bd d0 12 8e bd e4'),
        initial_reserves=locate('bd d0 c6 b7 bd ec'),initial_wave=locate('86 01 b7 bd ed 97 48'),
        common_player_restart=locate('86 7f 97 59 bd d0 45 6a 08'))
    logs=[];expected_warnings={d['name'] for d in differences}
    pattern=re.compile(r'(\S+) WRONG CHECKSUMS:\s*EXPECTED: CRC\(([0-9a-f]+)\) SHA1\(([0-9a-f]+)\)\s*FOUND: CRC\(([0-9a-f]+)\) SHA1\(([0-9a-f]+)\)')
    for leg in ('01-reference','02-candidate','03-reference'):
        for slot in range(4096,4128):
            path=CAMPAIGN/leg/'actors'/str(slot)/'console.log'
            with path.open('rb') as stream:
                before=identity(os.fstat(stream.fileno()));raw=stream.read(32768);after=identity(os.fstat(stream.fileno()))
            require(all(before[k]==after[k] for k in ('device','inode','mode','uid','nlink')),'Actor console inode/ownership changed')
            text=raw.decode();warnings=pattern.findall(text)
            require(len(warnings)==6 and {r[0] for r in warnings}==expected_warnings,'Original actor checksum evidence differs')
            for name,expected_crc,expected_sha,found_crc,found_sha in warnings:
                require((expected_crc,expected_sha)==(hashes(blue[name])['CRC32'],hashes(blue[name])['SHA1'])
                    and (found_crc,found_sha)==(hashes(loose[name])['CRC32'],hashes(loose[name])['SHA1']),
                    'Original actor FOUND/EXPECTED ROM checksums differ from local artifacts')
            require('[PATCH] RRCHRIS runtime ROM patch disabled.' in text,'Runtime patch-disabled startup evidence missing')
            entry=save(leg+'-slot'+str(slot)+'-console-prefix.readonly.txt',raw)
            logs.append(dict(leg=leg,slot=slot,original_path=str(path),before=before,after=after,
                readonly_prefix=entry,full_file_at_capture=before==after and len(raw)==before['bytes'],
                checksum_records=6,found_variant='loose_equals_legacy_archive',RRCHRIS_runtime_patch_disabled=True))
    for path,pin in inputs.items():require(reader.pin(path)==pin,'A local ROM/binary/assembly input changed during readback')
    result=dict(schema='robotron-offline-ROM-startup-binary-map-v1',unix_s=time.time(),
        status='LOCAL_ROM_START_GATE_MAPPED_WITH_PRIMARY_OPCODE_SOURCE_NO_RUNTIME_ACCEPTANCE_PROOF',
        source_pins={k:v['pin'] for k,v in sources.items()},local_input_pins=inputs,readonly_copies=copies,
        ROM_inventories=archives,CPU_chip_mapping=cpu,blue_vs_actual_differing_chips=differences,
        actual_loose_equals_legacy_all12=True,all_three_variants_startup_region_identical=True,
        inspected_logical_ROM_interval=[0x26c0,0x27b5],direct_page_symbols=symbols,
        initialization=dict(OS_vector=0xd000,target=init,bytes=init_bytes.hex(),DP_initialized=0x98,
            ROM_bank_select_write=0xc900,scope='Static bytes and upstream bank map; not a live CPU-register observation.'),
        startup=dict(vector=0x26cc,target=start,decoded_gate=decoded,write_patterns=writes,
            interpretation='With DP98, the gate refuses when STATUS bit7 is clear, or when requested player count exceeds available credit. Free-play mode9 supplies the requested credit. Accepted setup later writes STATUS7f and initializes score/reserves/wave; the common player-restart path also writes STATUS7f.'),
        actor_console_evidence=logs,original_actor_console_prefixes_checked=len(logs),
        local_inputs_unchanged=True,emulator_invoked=False,model_imported=False,device_queried=False,
        current_cohort_altered=False,source_or_recipe_changed=False,protocol_selected=False,
        real_ROM_start_acceptance_proven=False,quality_gain_verified=False,learning_speed_gain_verified=False,
        limitations=['Static control flow does not prove that a particular live input reached or passed START1.',
            'Upstream mame0264 sources are release-matched references, not a byte-for-byte build proof of the installed distribution binary.',
            'Actor FOUND checksums bind six differing chips. No wrong-checksum warning is not a direct memory dump of the remaining ROM bytes.',
            'STATUS7f is also written by player restart; the existing prefix contains no PC/DP/bank/loaded-ROM-region witness.',
            'No startup game may become eligible from this offline map; current R2/C2 and the sole final scientific review stay unchanged.'])
    entry=value('ROM-startup-binary-map.json',result)
    print(json.dumps(dict(report=entry,actor_prefixes=len(logs),differing_chips=len(differences),real_ROM_start_acceptance_proven=False)))
    return entry


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analyze',action='store_true');p.add_argument('--output');p.add_argument('--expected-source-sha256');a=p.parse_args(argv)
    if not a.analyze:print('PLAN_ONLY: no local source/ROM/log reads or outputs; no runtime actions');return 0
    require(a.output and a.expected_source_sha256 and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.expected_source_sha256,'Explicit exact source and output required')
    analyze(Path(a.output));return 0


if __name__=='__main__':raise SystemExit(main())
