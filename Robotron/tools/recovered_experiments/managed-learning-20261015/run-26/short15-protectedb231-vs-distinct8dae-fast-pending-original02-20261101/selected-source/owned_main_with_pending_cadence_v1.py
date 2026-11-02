"""Original strict Main replay plus a prospective faster-pending scheduling check."""
import importlib.util,sys
PARENT = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/short15-protectedb231-vs-stopped77f9-immutable-review-original02-20261101/selected-source/owned_main_auditor.py', 'sha256': 'cc5fe6bfab1e907a071eb85e8c2e4c325864e33a1c78c6110df57e3aeaa9b23b', 'bytes': 6772, 'identity': {'device': 2304, 'inode': 85486314, 'bytes': 6772, 'mtime_ns': 1793538064059167994, 'ctime_ns': 1793538064059167994, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}

def check_pending_cadence(samples,read):
 raw=[read(s['physical_v6'])for s in samples];rows=[]
 for i,value in enumerate(raw):
  if value['accepted']:continue
  if i+1>=len(raw):raise ValueError('Pending final sample has no real recovery observation')
  gap=raw[i+1]['started_monotonic_s']-value['completed_monotonic_s']
  if not 0<gap<5:raise ValueError('Actual pending cadence did not obtain next observation before5s')
  rows.append(dict(after_pending_index=i,next_observation_gap_s=gap))
 return rows

def audit_main(job,result,read,h):
 spec=importlib.util.spec_from_file_location('_unchanged_strict_Main_replay',h.checked(PARENT));m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
 original=m.audit_main(job,result,read,h)
 cadence=check_pending_cadence(result['main_samples'],read)
 return dict(original,all_original_strict_predicates_retained=True,actual_pending_cadence_audited=True,live_pending_coverage=bool(cadence),actual_pending_next_observation_gaps=cadence)
