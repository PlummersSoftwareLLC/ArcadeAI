"""CPU contracts using a NEW real complete raw window; old failed studies stay invalid."""
import argparse,copy,hashlib,importlib.util,json,os,time,unittest
from pathlib import Path

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
 if not args.execute:print('PLAN_ONLY');return 0
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256;raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256;job=json.loads(raw);assert job['schema']=='robotron-owned-proc-dynamic-fields-v3-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
 def load(pin,name):
  assert hashlib.sha256(Path(pin['path']).read_bytes()).hexdigest()==pin['sha256'];s=importlib.util.spec_from_file_location(name,pin['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
 h=load(job['helpers'],'_dyn_h');reader=load(job['reader'],'_dyn_r')
 def read(pin):return reader.read_pin(pin)
 for v in job.values():
  if isinstance(v,dict)and 'path'in v:h.checked(v)
 subject=load(job['subject'],'_dyn_subject');original=load(job['original'],'_dyn_original');engine=load(job['engine'],'_dyn_engine');base=load(job['base_collector'],'_dyn_base');selected=read(job['actual_capture_job']);report=read(job['actual_capture_report']);n=report['diagnostic']['first_strict_rejection']['index'];assert n==390 and len(report['samples'])==397 and report['diagnostic']['strict_stream_retried']is False
 modules=engine.dependencies(selected,h);p=modules['indexed_join'].bind(modules['primitives']);transport=modules['transport'];binding=read(selected['binding']);real=[base.unpacked(read(report['samples'][i]))for i in [n-1,n,n+1]];oldfailed=read(job['old_failed_health']);negative=[];certificate=None;full=None
 def certify(data):return subject.certify(p,transport,binding,p.LUA_SHA,data)
 def mutate_repeat(data,index,value):
  lines=data[1]['raw_tcp'].splitlines(keepends=True);positions=[i for i,line in enumerate(lines)if len(line.split())>=10 and line.split()[9]==b'359713499'];assert len(positions)==2;i=positions[-1];fields=lines[i].split();fields[index]=value;lines[i]=b' '.join(fields)+b'\n';data[1]['raw_tcp']=b''.join(lines)
 def jsonchange(data,key,fn):
  v=json.loads(data[1][key]);fn(v);data[1][key]=json.dumps(v,separators=(',',':')).encode()
 class Contracts(unittest.TestCase):
  def reject(self,name,change):
   data=copy.deepcopy(real);change(data)
   with self.assertRaises((ValueError,KeyError,TypeError)):certify(data)
   negative.append(name)
  def test_01_actual_complete_owned_window_retains_both_conflicting_rows(self):
   nonlocal certificate
   self.assertEqual(subject.LIMITS,original.LIMITS)
   with self.assertRaises(ValueError):original.certify(p,transport,binding,p.LUA_SHA,real)
   certificate=certify(real);self.assertEqual(certificate['slot'],176);self.assertEqual(certificate['raw_API_counts_preserved'],[192,192,192]);self.assertTrue(certificate['raw_TCP_rows_preserved']);self.assertFalse(certificate['quality_qualified']);self.assertLessEqual(certificate['charged_s'],2)
   event=certificate['original_repeat_events'][0];self.assertEqual(event['actual_changed_field_indices'],[4,5]);self.assertEqual([r['proc_ordinal']for r in event['occurrences']],['727:','728:'])
  def test_02_entire397_original_raw_samples_recompute_full_health(self):
   nonlocal full
   proposed=copy.deepcopy(selected);proposed['sources']['proc_repeat']=job['subject']
   # Recompute raw evidence; diagnostic statuses remain rejected/collect-only.
   # No old cached acceptance or original strict stream is edited or retried.
   full=engine.replay(proposed,report['samples'],read(job['actual_initial_cursors']),read,h)
   self.assertEqual(full['samples'],397);self.assertEqual(full['deep_samples'],16);self.assertTrue(full['all197_held_inputs_final_independently_hashed']);self.assertEqual(full['transport']['budget']['proc_repeat_groups'],1)
  def test_03_old_failed_original_without_after_proof_remains_invalid(self):
   before=base.unpacked(read(oldfailed['samples'][-2]));bad=base.unpacked(read(oldfailed['samples'][-1]));oldbinding=read(read(job['old_native_job'])['main_binding'])
   with self.assertRaises(ValueError):subject.certify(p,transport,oldbinding,p.LUA_SHA,[before,bad])
   with self.assertRaises(ValueError):certify(real[:2])
   negative.extend(['old2690_missing_after_stays_invalid','new_window_missing_after_rejects'])
  def test_04_explicit_synthetic_delayed_ACK_variation_and_unsupported_body_rejections(self):
   data=copy.deepcopy(real);mutate_repeat(data,13,b'4');value=certify(data);self.assertEqual(value['original_repeat_events'][0]['actual_changed_field_indices'],[4,5,13])
   for name,index,value in [('uid',7,b'0'),('inode',9,b'999999999'),('peer',2,b'8301A8C0:812B'),('state',3,b'06'),('refcount',10,b'4'),('pointer',11,b'0000000000000001'),('RTO',12,b'21'),('ACK_flags',14,b'0'),('cwnd',15,b'11'),('threshold',16,b'10'),('bad_queue',4,b'not-a-queue'),('bad_timer',5,b'05:00000014'),('negative_ACK_time',13,b'-1'),('oversized_ACK_time',13,b'4294967296')]:self.reject(name,lambda data,index=index,value=value:mutate_repeat(data,index,value))
  def test_05_all_ownership_epoch_freshness_and_caps_remain_required(self):
   for count in [191,193,194]:self.reject('API'+str(count),lambda data,count=count:jsonchange(data,'raw_API',lambda a:a.update(client_count=count)))
   self.reject('trainer_birth',lambda data:jsonchange(data,'raw_fds',lambda f:f['trainer'].update(starttime_ticks=1)))
   self.reject('actor_birth',lambda data:jsonchange(data,'raw_fds',lambda f:f['actors']['176'].update(starttime_ticks=1)))
   self.reject('missing_trainer_FD',lambda data:jsonchange(data,'raw_fds',lambda f:f['trainer']['socket_fds'].update({'180':1})))
   self.reject('stale_FD',lambda data:jsonchange(data,'raw_fds',lambda f:f.update(begin_unix_s=1,end_unix_s=1)))
   self.reject('stale_API',lambda data:jsonchange(data,'raw_API',lambda a:a.update(ts=a['ts']-10)))
   self.reject('changed_CID_epoch',lambda data:jsonchange(data,'raw_API',lambda a:next(r for r in a['client_rows']if r['client_slot']==176).update(connected_seconds=.01)))
   self.reject('concurrent_cap',lambda data:data[1]['log_chunks'].append(dict(raw=b'[WAVECAP]')))
   self.reject('bad_ordinal',lambda data:mutate_repeat(data,0,b'727:'))
   self.reject('gap',lambda data:data[1].update(observed_unix_s=data[0]['observed_unix_s']+1))
  def test_06_whole_case_charges_and_repeat_reuse_stay_strict(self):
   value=certify(real);budget=subject.closed_budget(p,[value]);self.assertEqual(budget['events'],1);self.assertEqual(budget['total_charged_s'],value['window_s'])
   with self.assertRaises(ValueError):subject.closed_budget(p,[value,value])
   changed=copy.deepcopy(value);changed['charged_s']=0
   with self.assertRaises(ValueError):subject.closed_budget(p,[changed])
   negative.extend(['duplicate_window_budget','zeroed_charge'])
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
 if not result.wasSuccessful():return 1
 output=Path(job['output']);output.mkdir(mode=0o700);h.put(output/'report.json',dict(schema='robotron-owned-proc-dynamic-fields-v3-contract-report-v1',status='REAL_COMPLETE_WINDOW_AND_FULL397_RAW_HEALTH_WITH_PROPOSED_V3_PASS',tests=result.testsRun,negative_checks=negative,actual_certificate=certificate,actual_raw_full_health_replay=full,actual_raw_source_report=job['actual_capture_report'],synthetic_variation_only='Only test04 delayed-ACK token mutation is synthetic; actual certificate covers original queue/timer differences',original_collect_only_capture_relabelled=False,old_failed2690_requalified=False,scientific_guard_selected=False,quality_qualified=False,production_changed=False,created_unix_s=time.time()));print(json.dumps(dict(tests=result.testsRun,negative_checks=len(negative),status='PASS')),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
