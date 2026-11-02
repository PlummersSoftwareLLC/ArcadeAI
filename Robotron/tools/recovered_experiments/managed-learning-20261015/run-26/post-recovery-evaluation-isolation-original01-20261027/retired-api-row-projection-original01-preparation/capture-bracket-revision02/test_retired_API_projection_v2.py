"""Failed raw46 counterexample plus prospective-only synthetic absence tests.

No original run is requalified: its actual raw snapshot has no absence witness.
No live API/process probes, model reads, MAME, units, or scientific review runs.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import types

Q=Path(__file__).resolve().parent
I=Q.parent.parent
S=I/'durable-e078b0da-launcher-mmap-study-original01'
O=S/'R1/deadline-output-original01'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value);return value


api=load('_test_retired_API',Q/'api_cached_projections_v3.py')
health=load('_test_retired_transport',Q/'round_health_transport_retired_API_v4.py')
worker=load('_test_final_worker_collect',Q/'round_observer_retired_API_v4.py')
old=load('_test_original_transport',I/'declared-launcher-census-original34-preparation/readonly-mmap-source-validation-original02/round_health_transport_launcher_mmap_v2.py')


def read(path):return json.loads(path.read_bytes())


def fixture():
    job=read(S/'R1/job.json');case=read(Path(job['main_binding']['path']))
    before=read(O/'main-observations/sample-001250.json')['snapshot']
    rejected=read(O/'main-observations/unaccepted-000003.json')['raw_snapshot']
    assert len(before['actors'])==37 and len(rejected['actors'])==36 and rejected['api']['client_count']==37
    evidence=read(I/'e078-R1-failure-readonly-audit-original01/slot46-exact-retired-API-and-TCP-schema-evidence-original01.json')
    line=evidence['committed_journal_line']['raw_utf8'];jid=rejected['results']['46']['result']['journal_game_id']
    return case,before,rejected,{jid:line}


def sync_wire(sample):
    wire=json.dumps(sample['api'],separators=(',',':'));sample['raw_API_wire']=wire
    sample['api_wire_sha256']=hashlib.sha256(wire.encode()).hexdigest()


def prospective():
    case,before,sample,lines=fixture();calls=[]
    # Reproduce the REAL unchanged worker.collect ordering: health evidence is
    # captured first, then TCP/raw-status checks, then final unix/mono retiming.
    original_probe,original_clock=api._pid_probe,api.time
    original_worker_clock,original_worker_read=worker.time,worker.read
    mono,wall=sample['monotonic_s'],sample['unix_s']
    def synthetic_positive_absence(pid):
        calls.append(pid)
        return dict(path='/proc/%d/stat'%pid,pid=pid,absent=True,current_birth=None,state=None,
            before_monotonic_s=mono+.00001,after_monotonic_s=mono+.00002)
    class HistoricalHealth:
        def collect(self,case,previous=None):
            return api.collect_retired(case,sample,previous,journal_lines=lines)
        def base(self):return health.base()
    try:
        api._pid_probe=synthetic_positive_absence
        api.time=types.SimpleNamespace(monotonic=iter([mono+.000001,mono+.00003]).__next__)
        worker.time=types.SimpleNamespace(monotonic=iter([mono-.0001,mono+.00004]).__next__,time=lambda:wall+.00004)
        worker.read=lambda path:copy.deepcopy(sample['status'])
        sample=worker.collect(HistoricalHealth(),case,previous=before)
    finally:
        api._pid_probe,api.time=original_probe,original_clock
        worker.time,worker.read=original_worker_clock,original_worker_read
    assert calls==[4002052]
    assert sample['retired_API_projection']['capture_ended_monotonic_s']<sample['monotonic_s']
    return case,before,sample


class Tests(unittest.TestCase):
    def test_actual_failed_raw_stays_invalid_without_new_positive_absence(self):
        case,before,sample,_=fixture()
        with self.assertRaises(ValueError):old.validate(case,sample,previous=before)
        with self.assertRaisesRegex(ValueError,'missing positive retirement evidence'):
            api.project_retired(case,sample,before)

    def test_future_equivalent_capture_passes_all_unchanged_health_TCP_conditions(self):
        case,before,sample=prospective();exact=copy.deepcopy(sample)
        view=api.project_retired(case,sample,before)
        self.assertEqual(sample,exact)
        self.assertEqual(sample['api']['client_count'],37)
        self.assertEqual(view['api']['client_count'],36)
        self.assertEqual(view['verified_retired_API_rows'][0]['slot'],'46')
        self.assertEqual(view['verified_retired_API_rows'][0]['birth'],12198541)
        health.validate(case,sample,previous=before)
        self.assertEqual(sample,exact)

    def test_identity_PID_TCP_and_registration_fail_closed(self):
        for damage in ('live','new_birth','wrong_anchor_birth','wrong_CID','CID_conflict','role','unknown_extra',
                       'missing_active','old_TCP_live','epoch','owner','source','raw_wire','round','probe_stale',
                       'probe_future','probe_reversed','capture_future','capture_stale'):
            case,before,sample=prospective();entry=sample['retired_API_projection']['entries']['46']
            row=next(row for row in sample['api']['client_rows']if row['client_slot']==46)
            if damage=='live':entry['PID_absence'].update(absent=False,current_birth=12198541,state='S')
            elif damage=='new_birth':entry['PID_absence'].update(absent=False,current_birth=12198542,state='S')
            elif damage=='wrong_anchor_birth':entry['anchor']['actor']['starttime_ticks']+=1
            elif damage=='wrong_CID':row['client_id']=999999;sync_wire(sample)
            elif damage=='CID_conflict':row['client_id']=sample['api']['client_rows'][0]['client_id'];sync_wire(sample)
            elif damage=='role':row['eval']=True;sync_wire(sample)
            elif damage=='unknown_extra':row['client_slot']=200;sync_wire(sample)
            elif damage=='missing_active':sample['api']['client_rows']=[v for v in sample['api']['client_rows']if v['client_slot']!=1];sample['api']['client_count']-=1;sync_wire(sample)
            elif damage=='old_TCP_live':
                oldline=next(line for line in before['transport']['raw_tables']['tcp'].splitlines()[1:]if ' 01 'in line and line.split()[9]==entry['anchor']['client']['inode'])
                sample['transport']['raw_tables']['tcp']=sample['transport']['raw_tables']['tcp'].rstrip('\n')+'\n'+oldline+'\n'
            elif damage=='epoch':sample['api']['host_pipeline']['learning_exposure']['replay']['epoch']+=1;sync_wire(sample)
            elif damage=='owner':sample['owners']['fleet']['invocation']='foreign'
            elif damage=='source':sample['owners']['trainer']['process']['executable']['path']='foreign'
            elif damage=='raw_wire':sample['api']['client_count']-=1
            elif damage=='round':sample['status']['round']+=1
            elif damage=='probe_stale':entry['PID_absence']['before_monotonic_s']=sample['monotonic_s']-1
            elif damage=='probe_future':entry['PID_absence']['after_monotonic_s']=sample['monotonic_s']+1
            elif damage=='probe_reversed':entry['PID_absence']['before_monotonic_s']=entry['PID_absence']['after_monotonic_s']+.0001
            elif damage=='capture_future':sample['retired_API_projection']['capture_ended_monotonic_s']=sample['monotonic_s']+1
            else:sample['retired_API_projection']['capture_started_monotonic_s']=sample['monotonic_s']-.500001
            with self.subTest(damage=damage),self.assertRaises((ValueError,KeyError)):
                api.project_retired(case,sample,before)

    def test_durable_receipt_journal_and_publication_fail_closed(self):
        for damage in ('no_commit_newline','wrong_journal','receipt_hash','wrong_PID','ineligible','unknown_start','wrong_round','old_publication'):
            case,before,sample=prospective();entry=sample['retired_API_projection']['entries']['46']
            if damage=='no_commit_newline':entry['journal_line']=entry['journal_line'].rstrip('\n')
            elif damage=='wrong_journal':entry['journal_line']='{}\n'
            elif damage=='receipt_hash':entry['receipt']['sha256']='0'*64
            elif damage=='wrong_PID':sample['results']['46']['pid']+=1
            elif damage=='old_publication':entry['receipt']['identity']['mtime_ns']-=10**9
            else:
                value=json.loads(entry['receipt']['raw'])
                if damage=='ineligible':value['result']['eligible']=False
                elif damage=='unknown_start':value['result']['known_start']=False
                else:value['round']+=1
                raw=json.dumps(value)+'\n';entry['receipt'].update(raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest())
                entry['receipt']['identity']['bytes']=len(raw.encode());sample['results']['46']=value
                sample['receipt_hashes']['46']=entry['receipt']['sha256'];entry['journal_line']=json.dumps(value['result'])+'\n'
            with self.subTest(damage=damage),self.assertRaises((ValueError,KeyError)):
                api.project_retired(case,sample,before)

    def test_continuation_keeps_original_anchor_and_nonrenewable_half_second_expiry(self):
        case,before,first=prospective();api.project_retired(case,first,before)
        later=copy.deepcopy(first);end=later['results']['46']['result']['end_unix_s']
        delta=end+.49-later['unix_s'];later['unix_s']+=delta;later['monotonic_s']+=delta
        later['api']['ts']=later['unix_s']-.1;sync_wire(later)
        probe=later['retired_API_projection']['entries']['46']['PID_absence']
        later['retired_API_projection'].update(capture_started_monotonic_s=later['monotonic_s']-.00003,
            capture_ended_monotonic_s=later['monotonic_s']-.000005)
        probe.update(before_monotonic_s=later['monotonic_s']-.00002,after_monotonic_s=later['monotonic_s']-.00001)
        self.assertEqual(api.project_retired(case,later,first)['api']['client_count'],36)
        expired=copy.deepcopy(later);expired['unix_s']+=.010001;expired['monotonic_s']+=.010001
        expired['api']['ts']=expired['unix_s']-.1;sync_wire(expired)
        with self.assertRaisesRegex(ValueError,'receipt-end expiry'):
            api.project_retired(case,expired,later)
        self.assertEqual(later['retired_API_projection']['entries']['46']['anchor'],first['retired_API_projection']['entries']['46']['anchor'])

    def test_original_reconnect_and_physical_TCP_predicate_AST_remain_exact(self):
        parent=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/api_reconnect_projection_v1.py')
        def functions(path):return {n.name:ast.dump(n,include_attributes=False)for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
        a,b=functions(parent),functions(Q/'api_cached_projections_v3.py')
        for name in a:self.assertEqual(a[name],b[name])
        original=I/'declared-launcher-census-original34-preparation/readonly-mmap-source-validation-original02/round_health_transport_launcher_mmap_v2.py'
        self.assertEqual(functions(original)['validate_transport'],functions(Q/'round_health_transport_retired_API_v4.py')['validate_transport'])
        original_worker=I/'declared-launcher-census-original34-preparation/readonly-mmap-source-validation-original02/round_observer_launcher_mmap_v2.py'
        self.assertEqual(functions(original_worker)['collect'],functions(Q/'round_observer_retired_API_v4.py')['collect'])


if __name__=='__main__':unittest.main()
