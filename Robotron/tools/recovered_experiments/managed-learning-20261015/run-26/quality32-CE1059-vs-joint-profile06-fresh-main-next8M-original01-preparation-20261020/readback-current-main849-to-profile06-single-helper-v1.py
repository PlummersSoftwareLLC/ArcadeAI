"""Read-only current main/profile06 full-module single-helper comparison."""
from pathlib import Path
import ast,hashlib,json,os,stat,sys,time
GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
SELECTED='_continuous_play_score_dip'
def identity(s):
 return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
def pin(p):
 before=identity(p.stat());raw=p.read_bytes();assert identity(p.stat())==before
 return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)
def birth(pid):
 p=Path('/proc')/str(pid)/'stat'
 if not p.exists():return None
 raw=p.read_text();return int(raw[raw.rfind(')')+2:].split()[19])
def stripped(tree):
 matches=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==SELECTED];assert len(matches)==1
 helper=ast.dump(matches[0],include_attributes=False)
 tree.body=[x for x in tree.body if x is not matches[0]]
 return ast.dump(tree,include_attributes=False),helper

def main():
 out=HERE/'current-main849-to-private-profile06-single-helper-static-readback.json';assert not out.exists()
 bp=pin(HERE/'runtime-bindings/main-binding.json');assert bp['sha256']=='494b2784effaed217d842e51e81d9340f43df2d1548e440ded34a6951758d1ac'
 binding=json.loads(Path(bp['path']).read_bytes());owner=binding['owner'];assert owner['pid']==3170722 and owner['starttime_ticks']==52892579 and birth(owner['pid'])==owner['starttime_ticks']
 installed=GAME/'Scripts/dqn/socket_server.py';private=GAME/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/socket_server.py'
 a=pin(installed);b=pin(private)
 assert a['sha256']=='84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40' and binding['held_hashes'][str(installed)]==a['sha256']
 assert b['sha256']=='b552b2e83a9cc10cf7e4125cef22f571abe9189bd2ad3e63c6f48aa7df0e4516'
 assert a['identity']['uid']==b['identity']['uid']==1001 and a['identity']['nlink']==b['identity']['nlink']==1 and b['identity']['mode']=='0o444'
 manifest_path=GAME/'tools/quality_capacity_proposal/profile06/runtime-source-package.json';mp=pin(manifest_path);assert mp['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
 ta,ha=stripped(ast.parse(installed.read_text()));tb,hb=stripped(ast.parse(private.read_text()));assert ta==tb and ha!=hb
 # Main intentionally uses stratified training starts; the private inference
 # evaluator controls wave1 separately. This comparison is socket code only,
 # and does not select the private journal or runtime configuration for main.
 method=next(n for n in ast.walk(ast.parse(installed.read_text())) if isinstance(n,ast.FunctionDef) and n.name=='_pack_action')
 text=ast.unparse(method);assert 'STRATIFIED_TRAINING_STARTS' in text and 'stratified_auto' in text
 for v in [bp,a,b,mp]:assert pin(Path(v['path']))==v
 assert birth(owner['pid'])==owner['starttime_ticks']
 report=dict(schema='profile06-current-main849-single-helper-static-comparison-v1',observed_unix_s=time.time(),source=pin(Path(__file__)),original_main_owner=owner,original_main_birth_live_before_and_after=True,current_main_binding=bp,installed_socket=a,selected_private_socket=b,selected_private_package=mp,selected_function=SELECTED,full_module_AST_identical_after_removing_only_selected_helper=True,selected_helper_AST_differs=True,imports_classes_and_all_other_functions_AST_unchanged=True,training_stratified_start_action_logic_AST_preserved=True,production_main_source_changed=False,production_handoff_selected=False,private_journal_or_runtime_config_selected_for_main=False,model_replay_optimizer_or_banks_touched=False,quality_campaign_changed=False,quality_qualified=False,promotion=False,learning_speed_gain_verified=False,scope='Current installed socket versus selected private socket static code identity only. Actual handoff requires completed current quality disposition/freeze release, fresh current-owner acquisition, newest full model/replay/optimizer/banks and supported192-actor lifecycle. Existing private component test proofs remain their original executions.')
 with out.open('xb') as f:f.write((json.dumps(report,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 print(json.dumps(dict(readback=pin(out),full_module_single_helper_comparison_passed=True,production_source_changed=False,production_handoff_selected=False)))
if __name__=='__main__':
 if sys.argv[1:]==['--observe']:main()
 else:print('PLAN_ONLY: static comparison requires --observe; no production or evaluation mutations')
