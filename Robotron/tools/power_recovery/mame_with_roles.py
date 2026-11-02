"""Exec the owned MAME actor with its preserved role and readiness shim."""
import hashlib,json,os,sys
from pathlib import Path

def checked(pin):
    p=Path(pin['path']);assert p.resolve(strict=True)==p and not p.is_symlink()
    b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==pin['sha256'];return b

p=Path(os.environ['ROBOTRON_RECOVERY_CONFIG']);raw=p.read_bytes()
assert hashlib.sha256(raw).hexdigest()==os.environ['ROBOTRON_RECOVERY_CONFIG_SHA256']
cfg=json.loads(raw);roles=json.loads(checked(cfg['rolemap']))
checked(cfg['wait_library']);checked(cfg['canonical_lua'])
args=sys.argv[1:];env=dict(os.environ);slot=env.get('ROBOTRON_CLIENT_SLOT')
if slot is not None:
    assert slot in roles['slot_eval']and args[0]=='robotron'
    env['ROBOTRON_EVAL_MODE']='1'if roles['slot_eval'][slot]else'2'
    env['ROBOTRON_PREVIEW_CLIENT']='1'if slot=='0'else'0'
else:
    assert args==['-showusage']or '-verifyroms'in args
assert env.get('ROBOTRON_SOCKET_ADDRESS','dell:9998')=='dell:9998'
env.update(LD_PRELOAD=cfg['wait_library']['path'],ROBOTRON_SOCKET_WAIT_PORT='9998',ROBOTRON_SOCKET_WAIT_US=roles['socket_wait_us'])
os.execve('/usr/games/mame',['/usr/games/mame',*args],env)
