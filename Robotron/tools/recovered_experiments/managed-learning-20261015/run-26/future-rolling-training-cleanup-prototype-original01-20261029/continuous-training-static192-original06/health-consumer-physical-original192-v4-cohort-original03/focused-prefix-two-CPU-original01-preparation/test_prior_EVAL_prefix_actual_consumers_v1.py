"""Two actual prefix-consumer regression groups; source-only, Root alone runs.

Every journal row, cutoff, case and process-free clock is synthetic. SHA-bound
actual pure registry and file-only collector functions run on temporary files.
No selected module, live main journal, proc/API/unit/model/score body is imported
or queried. This cannot qualify an actual main case or scientific job.
"""
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SOURCES={'registry':('continuous_physical192_registry_v3.py','c57b0ef9522101c69aa551b1488921c4a97af27fd10f1c52c95387fa873cf204'),
         'base':('continuous_physical192_health_v3.py','83c1b3c1dee625c423310093eb5a13ff373875a4569435c8b14ba6d979b7d051')}


def ident(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(s.st_mode&511),uid=s.st_uid,nlink=s.st_nlink)

def pin(p):
    raw=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(p.stat()))

class Clock:
    def __init__(self):self.mono=1000.;self.unix=3000.
    def monotonic(self):return self.mono
    def time(self):return self.unix


def actual_functions(clock):
    def tree(role):
        name,sha=SOURCES[role]
        if not isinstance(sha,str)or len(sha)!=64:raise RuntimeError('Final source hash unfilled')
        path=ROOT/name;raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Changed exact prefix source')
        return ast.parse(raw),str(path)
    ns=dict(hashlib=hashlib,json=json,math=math,os=os,Path=Path,stat=stat)
    t,p=tree('registry');wanted={'require','number','identity','read_pin','completed_prefix','validate_completed_prefix_capture'}
    body=[n for n in t.body if isinstance(n,ast.FunctionDef)and n.name in wanted]
    exec(compile(ast.Module(body=body,type_ignores=[]),p,'exec'),ns)
    reg=SimpleNamespace(**ns)
    ns=dict(hashlib=hashlib,json=json,os=os,Path=Path,stat=stat,time=clock,registry=lambda:reg)
    t,p=tree('base');wanted={'require','file_identity','stat_identity','read_producer_prefix','collect_eval_evidence'}
    body=[n for n in t.body if isinstance(n,ast.FunctionDef)and n.name in wanted]
    exec(compile(ast.Module(body=body,type_ignores=[]),p,'exec'),ns)
    return reg,SimpleNamespace(**ns)

class Harness:
    def __init__(self,directory,*,old_count=17,hidden_new=False):
        self.root=Path(directory).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.clock=Clock();self.reg,self.base=actual_functions(self.clock);self.sequence=0
        self.retirement=self.root/'completed_clients.jsonl';self.main=self.root/'games.jsonl'
        self.old_rows=[self.row(i,'SYNTHETIC-OLD-'+str(i),100+i,150+i)for i in range(old_count)]
        if hidden_new:self.old_rows.append(self.row(30,'SYNTHETIC-NEW-HIDDEN-IN-OLD-PREFIX',2100,2200))
        self.old_raw=b''.join(self.line(r)for r in self.old_rows)
        self.ordinary(self.retirement,self.old_raw);self.ordinary(self.main,self.old_raw)
        self.archive=self.write('prefix-archive.jsonl',self.old_raw)
        self.value=dict(schema='robotron-prior-cohort-EVAL-completed-prefix-v1',canonical_path=str(self.retirement),
            canonical_identity={k:ident(self.retirement.stat())[k]for k in('device','inode','mode','uid','nlink')},
            archive=self.archive,prefix_bytes=len(self.old_raw),prefix_sha256=hashlib.sha256(self.old_raw).hexdigest(),
            cohort_min_spawn_unix_s=2000.)
        self.record=self.write('prefix-record.json',self.value)
        self.case=dict(continuous=dict(completed_clients_prefix=self.record,eval_journal_directory=str(self.root)),
            slot_eval={str(i):i<37 for i in range(192)},inputs={})
        self.hold(self.record);self.hold(self.archive)
    @staticmethod
    def row(slot,jid,start,end):
        return dict(journal_game_id=jid,client_slot=slot,client_id=100+slot,eval_only=True,game_uid=1,
            complete=True,eligible=True,known_start=True,score=0,boundary_reason='zero_score_restart',
            start_unix_s=start,end_unix_s=end,start_context=dict(measurement_generation=0,measurement_active=False,ratchet_frozen=False))
    @staticmethod
    def line(row):return (json.dumps(row,separators=(',',':'),allow_nan=False)+'\n').encode()
    @staticmethod
    def ordinary(path,raw):
        with path.open('wb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o664);os.fsync(f.fileno())
    def write(self,name,value):
        self.sequence+=1;p=self.root/('%03d-'%self.sequence+name)
        raw=value if isinstance(value,bytes)else(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()
        with p.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        return pin(p)
    def hold(self,p):self.case['inputs'][p['path']]=dict(sha256=p['sha256'],identity=p['identity'])
    def recase(self,value):
        case=copy.deepcopy(self.case);record=self.write('negative-record.json',value)
        case['continuous']['completed_clients_prefix']=record
        case['inputs'][record['path']]=dict(sha256=record['sha256'],identity=record['identity'])
        return case
    def suffix(self,rows,*,main_extra=b''):
        raw=b''.join(self.line(r)for r in rows)
        self.ordinary(self.retirement,self.old_raw+raw)
        self.ordinary(self.main,self.old_raw+main_extra+raw)
    def collect(self,previous=None):
        capture={};entries=self.base.collect_eval_evidence(self.case,previous,prefix_capture=capture)
        sample=dict(EVAL_completed_prefix_capture=capture,capture_started_monotonic_s=self.clock.mono-1,
            capture_ended_monotonic_s=self.clock.mono+1,monotonic_s=self.clock.mono+1)
        return entries,sample

class Tests(unittest.TestCase):
    def test_actual_immutable_historical_prefix_and_replayed_capture_guards(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);value,raw=h.reg.completed_prefix(h.case)
            self.assertEqual(raw,h.old_raw);self.assertEqual(len(raw.splitlines()),17)
            self.assertNotIn(str(h.retirement),h.case['inputs'])  # mutable producer is never a held full8 input
            for damage in('record_membership','archive_membership','schema','path','cutoff','byte_count','archive_sha'):
                case=copy.deepcopy(h.case);v=copy.deepcopy(h.value)
                if damage=='record_membership':case['inputs'].pop(h.record['path'])
                elif damage=='archive_membership':case['inputs'].pop(h.archive['path'])
                else:
                    if damage=='schema':v['schema']='FOREIGN'
                    elif damage=='path':v['canonical_path']=str(h.root/'foreign.jsonl')
                    elif damage=='cutoff':v['cohort_min_spawn_unix_s']=0
                    elif damage=='byte_count':v['prefix_bytes']+=1
                    else:v['prefix_sha256']='0'*64
                    case=h.recase(v)
                with self.subTest(damage=damage),self.assertRaises(ValueError):h.reg.completed_prefix(case)
            current=h.row(0,'SYNTHETIC-NEW-CURRENT',2100,2200);h.suffix([current])
            entries,sample=h.collect();h.reg.validate_completed_prefix_capture(h.case,sample)
            for damage in('wire','record','inode','truncation','future_bracket'):
                bad=copy.deepcopy(sample);c=bad['EVAL_completed_prefix_capture']
                if damage=='wire':c['raw_prefix_wire']='X'+c['raw_prefix_wire'][1:]
                elif damage=='record':c['record']['sha256']='0'*64
                elif damage=='inode':c['canonical_identity']['inode']+=1
                elif damage=='truncation':c['canonical_identity']['bytes']=len(h.old_raw)-1
                else:c['after_monotonic_s']=sample['capture_ended_monotonic_s']+.1
                with self.subTest(capture=damage),self.assertRaises(ValueError):h.reg.validate_completed_prefix_capture(h.case,bad)
            # A same-inode changed prefix and a truncation are rejected by the actual collector.
            canonical=h.retirement.read_bytes()
            h.ordinary(h.retirement,b'X'+canonical[1:])
            with self.assertRaises(ValueError):h.collect()
            h.ordinary(h.retirement,h.old_raw[:-1])
            with self.assertRaises(ValueError):h.collect()
            h.ordinary(h.retirement,canonical)
            replacement=h.root/'replacement-completed.jsonl';h.ordinary(replacement,canonical);os.replace(replacement,h.retirement)
            with self.assertRaises(ValueError):h.collect()
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory,hidden_new=True)
            with self.assertRaisesRegex(ValueError,'strictly before'):h.reg.completed_prefix(h.case)
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory,old_count=0)
            self.assertEqual(h.reg.completed_prefix(h.case)[1],b'')
            self.assertEqual(h.collect()[0],{})

    def test_actual_suffix_only_absolute_offsets_duplicate_bound_and_cached_row(self):
        with tempfile.TemporaryDirectory()as directory:
            h=Harness(directory);current=h.row(0,'SYNTHETIC-CURRENT-EVAL',2100,2200)
            train=h.row(40,'SYNTHETIC-ORDINARY-TRAIN',2050,2150);train['eval_only']=False
            extra=h.line(train);h.suffix([current],main_extra=extra)
            entries,sample=h.collect();self.assertEqual(set(entries),{'0'})
            row=entries['0'];self.assertEqual(row['raw_line'],h.line(current).decode())
            self.assertEqual(row['retirement_line_offset'],len(h.old_raw))
            self.assertEqual(row['main_line_offset'],len(h.old_raw)+len(extra))
            self.assertEqual(row['raw_line_sha256'],hashlib.sha256(h.line(current)).hexdigest())
            h.reg.validate_completed_prefix_capture(h.case,sample)
            previous=dict(EVAL_journal_evidence=copy.deepcopy(entries));h.clock.mono+=10;h.clock.unix+=10
            cached,_=h.collect(previous);self.assertEqual(cached,entries)  # first-observed clocks never renewed
            changed=dict(current,score=1);h.suffix([changed],main_extra=extra)
            with self.assertRaisesRegex(ValueError,'natural row changed'):h.collect(previous)
            # Both records are fresh (not cached), so this catches fresh-slot overwrite.
            second=h.row(0,'SYNTHETIC-DUPLICATE-NEW-SLOT',2201,2300)
            h.suffix([current,second])
            with self.assertRaisesRegex(ValueError,'duplicate'):h.collect()
            many=[h.row(i%37,'SYNTHETIC-TOO-MANY-'+str(i),2100+i,2200+i)for i in range(38)]
            h.suffix(many)
            with self.assertRaisesRegex(ValueError,'More than37'):h.collect()
            h.suffix([current]);h.ordinary(h.main,h.old_raw)
            with self.assertRaisesRegex(ValueError,'exact committed'):h.collect()
            h.suffix([current]);h.ordinary(h.main,h.old_raw+h.line(current)+h.line(current))
            with self.assertRaisesRegex(ValueError,'exact committed'):h.collect()

if __name__=='__main__':unittest.main()
