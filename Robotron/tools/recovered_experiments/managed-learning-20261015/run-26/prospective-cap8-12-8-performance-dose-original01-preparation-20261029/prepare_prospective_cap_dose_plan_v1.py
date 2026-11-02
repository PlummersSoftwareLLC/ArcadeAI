"""Data-only prospective plan copier. Default inert; never changes a live control or launches anything."""
import argparse,hashlib,json,os,stat
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/prospective-cap8-12-8-performance-dose-original01-preparation-20261029')
SELECTED={'performance_observation': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/live-original01/startup-repair-original02/performance-observation-original01/observational-performance-original01.json', 'sha256': 'f87a64981f95ba1d2c4c9bd6528c687fca9693ce51c87baa89482f22e375d6a1', 'bytes': 13628, 'identity': {'device': 2304, 'inode': 85228140, 'bytes': 13628, 'mtime_ns': 1793282764018635502, 'ctime_ns': 1793282764018635502, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'prior_cohort_observation': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/round10-pre-continuous-mode-observation-original01-20261029/observational-baseline-original01.json', 'sha256': '86668a0000f76b8d072221a75cbc2a71d51eda51b8fa14e985b1fa43925788f3', 'bytes': 1016, 'identity': {'device': 2304, 'inode': 85225609, 'bytes': 1016, 'mtime_ns': 1793273683928874091, 'ctime_ns': 1793273683930170701, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'config_source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/config.py', 'sha256': 'ef26db6aa19fe67ec9e1e15f8227b4e24bbc853b05d0ea00c450b290bf80b249', 'bytes': 117829, 'identity': {'device': 2304, 'inode': 79725688, 'bytes': 117829, 'mtime_ns': 1793083583998609854, 'ctime_ns': 1793083583999299168, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'learning_control_source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/learning_control.py', 'sha256': '29a74b25be391290b07373cdce4680ae7513db31596929f0bc9972aaf0ab220d', 'bytes': 4395, 'identity': {'device': 2304, 'inode': 79724935, 'bytes': 4395, 'mtime_ns': 1792112402629012954, 'ctime_ns': 1792112402629012954, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'training_source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/training.py', 'sha256': '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4', 'bytes': 35009, 'identity': {'device': 2304, 'inode': 79724954, 'bytes': 35009, 'mtime_ns': 1792239930867116846, 'ctime_ns': 1792239930867585104, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'main_source': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/main.py', 'sha256': '78178c39b281c0baf52222387f06db2d899c1bf2adfbe8c9fe2fd22729ff59c5', 'bytes': 69935, 'identity': {'device': 2304, 'inode': 79696085, 'bytes': 69935, 'mtime_ns': 1793280905240398064, 'ctime_ns': 1793280905250032427, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'prior_conditional_launcher_packet': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-cap12-full-state-continuation-source-only-original01-preparation/prepared-conditional-cap12-launcher-SOURCE-ONLY-NOT-SELECTED.json', 'sha256': '6d5c256f6ec7b342420a17c1344da83c1142c150616b21e346f89600a5a3b368', 'bytes': 4640, 'identity': {'device': 2304, 'inode': 85205519, 'bytes': 4640, 'mtime_ns': 1793266751732522304, 'ctime_ns': 1793266751732522304, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
PLAN_SHA='34b44819c62b1fc35853cdc89c765a3de269d84466c378eaee4806511b5d108e'

def pin(path):
    path=Path(path)
    if path.resolve(strict=True)!=path or path.is_symlink():raise ValueError('Canonical metadata/source required')
    before=path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size>2000000:raise ValueError('Bounded source/closed metadata only')
    raw=path.read_bytes();after=path.stat()
    identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    if identity(before)!=identity(after):raise ValueError('Input changed while reading')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(after))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-plan',action='store_true');p.add_argument('--expected-source-sha256');p.add_argument('--output',type=Path);a=p.parse_args()
    if not a.prepare_plan:print('SOURCE_ONLY_INERT_NO_READS_OR_ACTIONS');return
    if pin(Path(__file__).resolve())['sha256']!=a.expected_source_sha256:raise ValueError('Exact selected preparer required')
    for value in SELECTED.values():
        if pin(value['path'])!=value:raise ValueError('Selected source/closed observation changed')
    source=ROOT/'prospective-cap8-12-8-plan-UNSELECTED.json';raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PLAN_SHA:raise ValueError('Exact prospective plan required')
    value=json.loads(raw)
    if value['status']!='PROSPECTIVE_UNSELECTED_NO_CONTROL_OR_RESTART_AUTHORITY' or any(v is not None for v in value['future_actual'].values()):raise ValueError('No future actual facts may be invented')
    out=a.output
    if out is None or not out.is_absolute() or out.resolve(strict=False)!=out or out.exists():raise ValueError('Fresh absolute output file required')
    if not out.parent.is_dir() or out.parent.resolve(strict=True)!=out.parent:raise ValueError('Existing canonical output parent required')
    with out.open('xb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    fd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(prepared=pin(out),action_qualified=False,restart_or_control_authority=False)))

if __name__=='__main__':main()
