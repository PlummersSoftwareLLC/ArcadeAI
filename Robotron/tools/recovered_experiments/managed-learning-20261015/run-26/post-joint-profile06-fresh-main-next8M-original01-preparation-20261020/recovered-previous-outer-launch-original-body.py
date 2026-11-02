import pathlib,json,hashlib,importlib.util,sys,time,os
G=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron');Q=G/'logs/managed-learning-20261015/run-26/quality32-CE1059-vs-finalcopy-fresh-main-next8M-original01-preparation-20261020'
def load(n,p,h):
 assert hashlib.sha256(p.read_bytes()).hexdigest()==h;spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);sys.modules[n]=m;spec.loader.exec_module(m);return m
r=load('_original_quality_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071');c=load('_original_quality_control',G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14');read=lambda p:r.read_pin(p)
pp=r.pin(Q/'original-outer-launch-plan.json');assert pp['sha256']=='bfbb3c6c6804d007386ae5138b6afd94d851c3a6686c7450e0cd3ddec64b81df';plan=read(pp);config=read(plan['native_config']);proofpin=r.pin(Q/'root-window-and-CPU-acquisition-independent-readback.json');proof=read(proofpin);assert proof['outer_plan']==pp and proof['native_config']==plan['native_config'] and proof['status']=='ACTUAL_FIRST_BOTH8M_STRICT_CPU_AND_ACQUISITION_VERIFIED_NOT_LAUNCHED'
assert r.pin(plan['guard_source']['path'])==plan['guard_source'] and r.pin(plan['native_config']['path'])==plan['native_config'];assert r.pin(plan['argv'][3])['sha256']=='db1119b3ea7db7e9878b7ebd89f06a3b1c126bde46a5398617a3739917a2d9b9'
for p in config['pins']:assert c.pin(p['path'])==p
unit=plan['unit'];timer=unit.removesuffix('.service')+'.timer';assert c.show(unit)['LoadState']==c.show(timer)['LoadState']=='not-found';assert c.show(config['unit'])['LoadState']=='not-found';out=pathlib.Path(plan['output']);out.mkdir(mode=0o700);(out/'tmp').mkdir(mode=0o700)
props=['Type=exec','RemainAfterExit=yes','Restart=no','WorkingDirectory='+str(G.parent),'StandardOutput=append:'+str(out/'stdout.txt'),'StandardError=append:'+str(out/'stderr.txt')]+plan['properties']
actual=['systemd-run','--user','--unit='+unit,'--on-active=3s','--timer-property=AccuracySec=100ms']+['--property='+p for p in props]+['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(out/'tmp')]+plan['argv']
c.publish(out/'root-launch-intent.json',dict(unit=unit,timer=timer,actual_argv=actual,outer_plan=pp,native_config=plan['native_config'],independent_acquisition=proofpin,original_attempt=1,no_retry=True))
scheduled=c.command(out,'root-scheduling-carrier',actual);assert scheduled['exit']==0 and not scheduled['timed_out']
tshown=c.command(out,'original-launch-timer-show',['systemctl','--user','show',timer]);tcat=c.command(out,'original-launch-timer-cat',['systemctl','--user','cat',timer]);context=dict(unit=unit,timer=timer,timer_invocation_id=c.fields(tshown)['InvocationID']);assert c.timer_state(c.fields(tshown),context)=='original_loaded' and tcat['exit']==0;c.publish(out/'root-original-timer-launch-archive.json',dict(**context,timer_show=tshown,timer_cat=tcat))
deadline=time.monotonic()+15
while time.monotonic()<deadline:
 s=c.show(unit);pid=int(s.get('MainPID','0'))
 if pid:
  raw=pathlib.Path('/proc',str(pid),'stat').read_text();start=int(raw[raw.rfind(')')+2:].split()[19]);argv=[x.decode() for x in pathlib.Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if x];again=c.show(unit);assert argv==plan['argv'] and again['MainPID']==str(pid) and again['InvocationID']==s['InvocationID'] and s['NRestarts']=='0'
  raw2=pathlib.Path('/proc',str(pid),'stat').read_text();assert start==int(raw2[raw2.rfind(')')+2:].split()[19]);owner=dict(pid=pid,starttime_ticks=start,unit=unit,invocation_id=s['InvocationID'],cgroup=s['ControlGroup'],timer=timer,timer_invocation_id=context['timer_invocation_id'],observed_live=True);c.publish(out/'root-original-live-owner.json',owner);c.command(out,'original-first-observed-show',['systemctl','--user','show',unit]);print(json.dumps(dict(status='ORIGINAL_QUALITY_OUTER_LIVE',owner=owner)));break
 time.sleep(.03)
else:raise RuntimeError('Original outer birth was not captured; preserve handles; never retry')
