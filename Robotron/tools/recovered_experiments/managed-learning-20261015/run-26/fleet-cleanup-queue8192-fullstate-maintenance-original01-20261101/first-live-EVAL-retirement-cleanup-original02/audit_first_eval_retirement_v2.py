import pathlib,importlib.util,json,hashlib,urllib.request,urllib.parse,time,os,traceback
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');B=G/'logs/managed-learning-20261015/run-26'
R=B/'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101'
F=B/'quality32-protectedb231-vs-stopped77f9-restored8192-fullgame-original01-20261101'
D=R/'first-live-EVAL-retirement-cleanup-original02'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
h=load('_evalRetireV2Header',R/'sources/prepare_current_continuous_preservation_header_v3.py')
pin=lambda p:h.metadata(p)[0]
read=lambda p:h.read(pin(p))
D.mkdir(mode=0o700);checks=[]
def check(name,condition):
 if not condition:raise AssertionError(name)
 checks.append(name)
try:
 runtime=read(R/'actual-restored-current-training-runtime.json');startup=h.read(runtime['startup_job'])
 supervisor_source=runtime['fleet']['source'];check('exact immutable supervisor source',pin(supervisor_source['path'])==supervisor_source)
 supervisor=load('_evalRetireV2Supervisor',supervisor_source['path'])
 for source in startup['source_pins']:check('installed source '+pathlib.Path(source['path']).name,pin(source['path'])==source)
 ack_source=next(p for p in startup['source_pins']if pathlib.Path(p['path']).name=='bounded_fifo_cleanup_ack_v1.py')
 ack=load('_evalRetireV2ACK',ack_source['path']);check('unchanged ACK wait limits',ack.INITIAL_ACK_WAIT_S==5.0 and ack.TOTAL_ACK_WAIT_S==7.0)
 job=read(F/'01-reference/job.json');health_source=job['current_v6_health_source'];check('exact health source',pin(health_source['path'])==health_source)
 health=load('_evalRetireV2Health',health_source['path'])
 fleetpath=R/'post-backup-fleet-v6-original02/status.json';fleet=json.loads(fleetpath.read_bytes());row=fleet['slots']['8']
 check('closed EVAL without refill or fault',row['state']=='closed_eval' and row['eval_only']is True and row['faults']==0 and fleet['EVAL_refill_allowed']is False)
 natural=h.read(row['natural_result']);closed=h.read(row['closure']);binding=h.read(row['current_physical_binding'])
 membership=h.read(fleet['original_membership']);roles=h.read(fleet['rolemap'])['slot_eval'];original=membership['data']['original_slots']['8'];actor=binding['data']['actor']
 check('same original PID and birth',actor['pid']==row['original_pid']==original['original_child']['pid']==2795001 and actor['birth']==row['original_birth']==original['original_child']['birth']==8375640)
 check('original retirement and EVAL environment',actor['environment']['ROBOTRON_RETIRE_AFTER_GAME']=='1' and actor['environment']['ROBOTRON_EVAL_MODE']=='1')
 check('same original natural event and closure',closed['epoch']==natural['epoch']==fleet['epoch'] and closed['slot']==natural['slot']==8 and closed['data']['natural_result']==row['natural_result'])
 data=closed['data'];check('normal0 reaped without censor',data['actual_exit']==0 and data['original_wait_reaped']is True and data['original_birth_absent']is True and data['restart_censored']is False)
 proc=pathlib.Path('/proc/2795001/stat');check('original process birth absent now',not proc.exists()or int(proc.read_text().rsplit(')',1)[1].split()[19])!=8375640)
 connection=binding['data']['connection'];stamp=runtime['trainer']['server_stamp'];archived=data['connection_cleanup']
 check('archived strict old-token cleanup',len(archived)==1 and supervisor.closed_connection(connection,archived[0],stamp)is True)
 with urllib.request.urlopen('http://127.0.0.1:8771/api/connection_cleanup_token?'+urllib.parse.urlencode(dict(token=connection['token'])),timeout=5)as f:current=json.load(f)
 check('current strict old-token cleanup',supervisor.closed_connection(connection,current,stamp)is True)
 result=natural['data']['result'];check('durable known natural game',natural['data']['natural_complete']is True and all(result[k]is True for k in ['known_start','complete','eligible'])and result['eval_only']is True)
 check('recorded score and level',result['score']==1758250 and result['max_level']==64)
 journalpin=natural['data']['raw_line'];check('exact raw journal identity',pin(journalpin['path'])==journalpin)
 raw=pathlib.Path(journalpin['path']).read_bytes();canonical=(json.dumps(result,allow_nan=False,separators=(',',':'))+'\n').encode()
 check('canonical journal bytes and hashes join',raw==canonical and hashlib.sha256(raw).hexdigest()==current['terminal_line_sha256']==archived[0]['terminal_line_sha256'])
 check('terminal payload same in all receipts',current['terminal_receipt']==archived[0]['terminal_receipt']==result)
 with urllib.request.urlopen('http://127.0.0.1:8771/api/continuous_training_connections',timeout=5)as f:connections=json.load(f)
 check('retired slot and token absent from active TCPs',all(c['token']!=connection['token']and c['client_slot']!=8 for c in connections['connections']))
 metadata_pending=health.validate_metadata(fleet,connections,job['current_fleet'],membership,roles,now=time.time())
 checks.append('full fleet metadata accepted under existing transition semantics')
 after=json.loads(fleetpath.read_bytes())
 check('retired original row unchanged through audit',after['slots']['8']==row)
 report=dict(status='PASS_FIRST_NATURAL_EVAL_SCORE_NORMAL_EXIT_AND_BOUNDED_FIFO_ACK',checks=checks,
  score=result['score'],max_level=result['max_level'],slot=8,original_pid=2795001,original_birth=8375640,
  original_natural_result=row['natural_result'],original_journal=journalpin,original_membership=fleet['original_membership'],
  original_physical_binding=row['current_physical_binding'],original_reaped_closure=row['closure'],
  strict_cleanup_predicate_source=supervisor_source,ACK_helper_source=ack_source,
  actual_cleanup=h.put(D/'actual-old-token-API.json',current),actual_connections=h.put(D/'actual-connections-API.json',connections),
  actual_fleet=h.put(D/'actual-fleet.json',fleet),metadata_pending_slots=metadata_pending,
  original_birth_absent=True,normal_exit0_reaped=True,finished_actor_consumes_no_CPU=True,EVAL_refilled=False,
  remaining_active_clients=len(connections['connections']),ACK_limit_after_enqueue_s=7,
  ACK_within_existing_limit_inferred_from_pinned_helper_and_no_sticky_cleanup_error=True,
  direct_ACK_elapsed_s=None,total_cleanup_time_bound_claimed=False,causal_speed_gain_claimed=False,
  Main_changing_policy_EVAL_score_not_frozen_quality=True,quality_qualified=False,promotion=False)
except Exception:
 report=dict(status='FAILED_FRESH_READONLY_RETIREMENT_AUDIT',checks=checks,error=traceback.format_exc(),quality_qualified=False,promotion=False)
report['prior_failed_audit']=pin(R/'first-live-EVAL-retirement-cleanup-original01/failed-original-readonly-audit.json')
report['observed_unix_s']=time.time();output=h.put(D/'report.json',report)
print(json.dumps(dict(status=report['status'],report={k:output[k]for k in ['path','sha256','bytes']},checks=len(checks),error=report.get('error'))))
raise SystemExit(0 if report['status'].startswith('PASS_')else 1)
