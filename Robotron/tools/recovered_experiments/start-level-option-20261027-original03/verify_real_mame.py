import json,os,socket,struct,subprocess,sys,threading,time
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');D=Path(__file__).resolve().parent
sys.path.insert(0,str(G/'Scripts'))
from dqn.socket_server import parse_frame_data
listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(3);listener.settimeout(20)
port=listener.getsockname()[1];expected={0:20,1:81,2:1};errors=[];results={};threads=[];children=[]
def exact(c,n):
 b=bytearray()
 while len(b)<n:
  part=c.recv(n-len(b))
  if not part:raise EOFError('client closed before confirmation')
  b.extend(part)
 return bytes(b)
def serve(c):
 try:
  c.settimeout(10);slot=(struct.unpack('>H',exact(c,2))[0]>>1)&0x1fff;started=False;t=time.monotonic()
  for i in range(10000):
   n=struct.unpack('>I',exact(c,4))[0];assert 0<n<4194304;f=parse_frame_data(exact(c,n));assert f is not None
   started=started or bool(f.start_pressed and f.level_number==0)
   done=started and f.player_alive and 1<=f.level_number<=81
   # Server deliberately requests a conflicting start on every reply.
   c.sendall(struct.pack('>bbBBBB',-1,-1,0x20 if done else 0,1,40 if slot==2 else 1,0x85))
   if done:
    results[slot]=dict(requested=expected[slot],first_live_level=f.level_number,frames=i+1)
    assert f.level_number==expected[slot],results[slot]
    break
   assert time.monotonic()-t<30,'boot timed out'
  else:raise AssertionError('No first live level')
 except BaseException as e:errors.append(repr(e))
 finally:c.close()
def accept():
 try:
  for _ in range(3):
   c,_=listener.accept();th=threading.Thread(target=serve,args=(c,));threads.append(th);th.start()
 except BaseException as e:errors.append(repr(e))
a=threading.Thread(target=accept);a.start()
try:
 for slot,level in expected.items():
  env=dict(os.environ,ROBOTRON_START_LEVEL=str(level),ROBOTRON_CLIENT_SLOT=str(slot),ROBOTRON_SOCKET_ADDRESS='127.0.0.1:'+str(port),ROBOTRON_EVAL_MODE='1',ROBOTRON_RETIRE_AFTER_GAME='1',SDL_VIDEODRIVER='dummy');env.pop('LD_PRELOAD',None)
  with(D/('client-'+str(slot)+'.log')).open('wb')as log:
   children.append(subprocess.Popen(['/usr/games/mame','robotron','-rompath',str(G/'roms'),'-cheat','-nothrottle','-sound','none','-video','none','-skip_gameinfo','-autoboot_script',str(G/'Scripts/start_at_level.lua')],env=env,stdout=log,stderr=subprocess.STDOUT))
 a.join(25);assert not a.is_alive()
 for th in threads:th.join(35);assert not th.is_alive()
 exits=[c.wait(timeout=10)for c in children]
 assert not errors,errors
 assert len(results)==3 and exits==[0,0,0],(results,exits)
 report=dict(results=results,exits=exits,isolated_random_port=True,production_clients_untouched=True,not_a_game_score_or_quality_result=True)
 (D/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:
 listener.close()
 for c in children:
  if c.poll()is None:c.kill()
  c.wait(timeout=5)
