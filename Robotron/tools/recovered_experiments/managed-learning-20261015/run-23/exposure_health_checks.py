"""Read-only validation of process-local exposure snapshots, no model imports."""
FIELDS=('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')
CATEGORIES={'dqn','epsilon','expert','eval','unattributed'}
def snapshot_errors(exposure, previous, pid):
 errors=[]
 def require(condition,label):
  if not condition:errors.append(label)
 def counts(mapping,keys,label):
  require(set(mapping)==set(keys),label+'.keys')
  require(all(type(v) is int and v>=0 for v in mapping.values()),label+'.nonnegative_int')
 try:
  opt,rep=exposure['optimizer'],exposure['replay']
  for name,item,schema in [('optimizer',opt,'robotron-optimizer-exposure-v1'),('replay',rep,'robotron-replay-insert-exposure-v1')]:
   require(item['schema']==schema and item['enabled'],name+'.enabled_schema');require(item['process_id']==pid,name+'.process_id');require(type(item['epoch']) is int and item['epoch']>=0,name+'.epoch')
   if previous:
    before=previous[name]
    for key in ['process_id','instance_monotonic_ns','epoch','epoch_reason']:require(item[key]==before[key],name+'.stable_'+key)
  for name in ['total','since_epoch']:
   c=opt[name];counts(c,FIELDS,'optimizer.'+name);require(c['outcomes_recorded']==c['applied']+c['amp_skipped']+c['unavailable'],'optimizer.'+name+'.partition');require(c['attempts_started']-c['outcomes_recorded'] in (0,1),'optimizer.'+name+'.pending0or1');require(c['unavailable']==0,'optimizer.'+name+'.unavailable0')
   if previous:require(all(c[k]>=previous['optimizer'][name][k] for k in FIELDS),'optimizer.'+name+'.monotone')
  require(opt['unclassified_started_total']==opt['total']['attempts_started']-opt['total']['outcomes_recorded'],'optimizer.pending_consistent');require(opt['prior_epoch_outcomes_total']==0,'optimizer.straddled0');require(all(opt['since_epoch'][k]<=opt['total'][k] for k in FIELDS),'optimizer.epoch_within_total');require(opt['supported_torch']=='2.13.0+cu130','optimizer.supported_torch')
  expected_available=opt['since_epoch']['unavailable']==0 and opt['since_epoch']['outcomes_recorded']>0 and opt['total']['attempts_started']==opt['total']['outcomes_recorded']
  require(opt['available']==expected_available,'optimizer.available_consistent_pending_allowed')
  for suffix in ['total','since_epoch']:
   c=rep['accepted_by_source_'+suffix];counts(c,CATEGORIES,'replay.'+suffix);require(rep['accepted_'+suffix]==sum(c.values()),'replay.'+suffix+'.partition');require(rep['accepted_learner_'+suffix]==c['dqn']+c['epsilon'],'replay.'+suffix+'.learner_excludes_others')
   if previous:
    require(all(c[k]>=previous['replay']['accepted_by_source_'+suffix][k] for k in CATEGORIES),'replay.'+suffix+'.monotone')
  require(rep['available'] is True,'replay.available');require(all(rep['accepted_by_source_since_epoch'][k]<=rep['accepted_by_source_total'][k] for k in CATEGORIES),'replay.epoch_within_total')
  if previous:
   for k in CATEGORIES:require(rep['accepted_by_source_total'][k]-previous['replay']['accepted_by_source_total'][k]==rep['accepted_by_source_since_epoch'][k]-previous['replay']['accepted_by_source_since_epoch'][k],'replay.total_epoch_same_increment.'+k)
 except Exception as error:errors.append('snapshot_validation_exception:'+repr(error))
 return errors
