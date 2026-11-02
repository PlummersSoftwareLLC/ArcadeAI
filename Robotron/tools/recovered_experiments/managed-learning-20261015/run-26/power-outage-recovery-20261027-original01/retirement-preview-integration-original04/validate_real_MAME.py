"""Two real isolated MAME clients: selected-only30Hz images and committed exit."""
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
D=Path(__file__).resolve().parent
sys.path.insert(0,str(G/'Scripts'))
sys.path.insert(0,str(G))
from dqn.socket_server import SocketServer,parse_frame_data
from dqn import test_game_journal,test_training_round
from dqn.game_journal import GameJournal
from tools.power_recovery import test_round_fleet

suite=unittest.TestSuite()
for module in [test_game_journal,test_training_round,test_round_fleet]:
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
server=SocketServer.__new__(SocketServer)
server.client_states={slot:dict(proto_v2=True)for slot in [0,1]}
server._is_eval_client=lambda cid:True
listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2);listener.settimeout(20)
port=listener.getsockname()[1]
stats={};errors=[]
def exact(conn,count):
    out=bytearray()
    while len(out)<count:
        part=conn.recv(count-len(out))
        if not part:raise EOFError('Unexpected client EOF')
        out.extend(part)
    return bytes(out)
def serve(conn):
    try:
        conn.settimeout(10)
        _,slot,_=SocketServer._parse_client_handshake(struct.unpack('>H',exact(conn,2))[0])
        assert slot in [0,1]
        started=time.monotonic();frames=0;images=[];imagebytes=0;trace=[];known=False
        journal=GameJournal(D/("journal-"+str(slot)),retire_after_game=True)
        cs=dict(client_slot=slot,game_uid=1,eval_only=True)
        while True:
            count=struct.unpack('>I',exact(conn,4))[0];assert 0<count<4194304
            frame=parse_frame_data(exact(conn,count),parse_preview=True);assert frame is not None
            frames+=1
            if len(trace)<20:trace.append(dict(score=frame.game_score,alive=frame.player_alive,level=frame.level_number,start=frame.start_pressed))
            journal.observe(slot,frame,cs,context=lambda:dict(experiment="integration"))
            known=known or journal.active[slot]["known_start"]
            if frame.preview_encoded_bytes:
                images.append(time.monotonic());imagebytes+=frame.preview_encoded_bytes
            finished=time.monotonic()-started>=3
            if finished:
                # A control-only integration receipt, not a fabricated game score.
                receipt=D/('client-'+str(slot)+'-exit-control-receipt.json')
                with receipt.open('x')as stream:
                    json.dump(dict(control_integration_only=True,not_a_game_result=True,slot=slot),stream)
                    stream.flush();os.fsync(stream.fileno())
                server.client_states[slot]['retire_after_game']=True
            conn.sendall(server._pack_action(-1,-1,0,cid=slot,preview_enabled=slot==0 and not finished))
            if finished:break
            time.sleep(.01)
        stats[slot]=dict(frames=frames,preview_frames=len(images),preview_bytes=imagebytes,
                         measured_preview_FPS=(len(images)-1)/(images[-1]-images[0])if len(images)>1 else 0,
                         committed_exit_control_sent=True,known_start_observed=known,first20=trace)
    except BaseException as error:
        errors.append(repr(error))
    finally:conn.close()
threads=[]
def accept():
    try:
        for _ in range(2):
            conn,_=listener.accept();thread=threading.Thread(target=serve,args=(conn,));threads.append(thread);thread.start()
    except BaseException as error:errors.append(repr(error))
acceptor=threading.Thread(target=accept);acceptor.start();children=[]
try:
    for slot in [0,1]:
        env=dict(os.environ,ROBOTRON_SOCKET_ADDRESS='127.0.0.1:'+str(port),ROBOTRON_CLIENT_SLOT=str(slot),
                 ROBOTRON_EVAL_MODE='1',ROBOTRON_PREVIEW_CLIENT='1'if slot==0 else'0',
                 ROBOTRON_PREVIEW_FPS='30',ROBOTRON_RETIRE_AFTER_GAME='1',SDL_VIDEODRIVER='dummy')
        env.pop('LD_PRELOAD',None)
        with (D/('client-'+str(slot)+'.log')).open('ab')as stream:
            children.append(subprocess.Popen(['/usr/games/mame','robotron','-rompath',str(G/'roms'),'-cheat',
                '-nothrottle','-sound','none','-video','none','-skip_gameinfo','-autoboot_script',str(G/'Scripts/main.lua')],
                env=env,stdout=stream,stderr=subprocess.STDOUT))
    acceptor.join(25);assert not acceptor.is_alive()
    for thread in threads:thread.join(15);assert not thread.is_alive()
    exits=[child.wait(timeout=10)for child in children]
    assert not errors,errors
    assert exits==[0,0],exits
    assert set(stats)=={0,1}
    (D/"startup-evidence.json").write_text(json.dumps(dict(startup_evidence=stats),indent=2))
    assert all(x["known_start_observed"]for x in stats.values()),stats
    assert stats[0]['preview_frames']>=30 and 28<=stats[0]['measured_preview_FPS']<=31.5,stats
    assert stats[1]['preview_frames']==stats[1]['preview_bytes']==0,stats
    report=dict(schema='robotron-production-round-and-selected-preview-real-MAME-integration-v1',
        unit_tests=result.testsRun,unit_tests_passed=True,real_MAME_exits=exits,clients=stats,
        selected_capture_target_FPS=30,unselected_preview_bytes=0,
        durable_receipts_preceded_exit_packet=True,normal_MAME_exit_after_new_control_bit_verified=True,
        full_game_result_fabricated=False,quality_qualified=False)
    path=D/'report.json'
    with path.open('x')as stream:json.dump(report,stream,indent=2);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(report),flush=True)
finally:
    listener.close()
    for child in children:
        if child.poll()is None:child.kill()
        child.wait(timeout=5)
