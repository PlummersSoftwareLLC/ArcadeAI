"""Vendor typed socket evidence into new unselected IO/primitives sources."""
import ast,copy,importlib.util,json,os
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');P=G/'tools/training_connection_lifecycle_proposal_20261023';R=G/'logs/managed-learning-20261015/run-26'
D=R/'inet-diag-capture-family-contracts-CPU-original01-preparation-20261024'
spec=importlib.util.spec_from_file_location('_inet_family_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
helper=P/'inet_diag_snapshot_v2.py';compile(helper.read_text(),str(helper),'exec');helper.chmod(0o444)
original_job=json.loads((R/'native32-serialized-free314-observer-load600-original01-preparation-20261024/diagnostic-main-health-protocol.json').read_bytes())['health_job']
tree=ast.parse(helper.read_text());renames={n.name:'_inet_'+n.name for n in tree.body if isinstance(n,ast.FunctionDef)}
renames.update({name:'_INET_'+name for name in ('SCHEMA','MAX_BYTES','DATAGRAM_BYTES','MAX_DATAGRAMS','SNAPSHOT_KEYS','DATAGRAM_KEYS')})
class Rename(ast.NodeTransformer):
    def visit_Name(self,node):
        node.id=renames.get(node.id,node.id);return node
    def visit_FunctionDef(self,node):
        node.name=renames.get(node.name,node.name);return self.generic_visit(node)
embedded=Rename().visit(copy.deepcopy(tree));ast.fix_missing_locations(embedded)
definitions=[n for n in embedded.body if not isinstance(n,(ast.Import,ast.ImportFrom,ast.Expr))]
vendor=ast.unparse(ast.Module(body=definitions,type_ignores=[]))+'\n'
records=[]
def create(key,target,wrapper):
    oldpin=original_job['sources'][key];old=Path(oldpin['path']).read_text();oldtree=ast.parse(old)
    assert old.count('def tcp():'if key=='io'else'def tcp(raw):')==1
    source=old.replace('def tcp():','def _original_proc_tcp():')if key=='io'else old.replace('def tcp(raw):','def _original_proc_tcp(raw):')
    insertion=oldtree.body[0].end_lineno
    # Insert imports after the module docstring, before the existing imports.
    lines=source.splitlines(keepends=True);lines[insertion:insertion]=['import base64,hashlib,math,secrets,socket,struct,time\n']
    source=''.join(lines)+'\n'+vendor+'\n'+wrapper+'\n';compile(source,str(target),'exec')
    nodes={n.name:n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)};unchanged=[]
    for node in oldtree.body:
        if isinstance(node,ast.FunctionDef):
            current=copy.deepcopy(nodes['_original_proc_tcp'if node.name=='tcp'else node.name]);current.name=node.name
            assert ast.dump(current)==ast.dump(node),node.name;unchanged.append(node.name)
    for node in definitions:
        if isinstance(node,ast.FunctionDef):assert ast.dump(nodes[node.name])==ast.dump(node),node.name
    with target.open('xb')as f:f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    result=h.pin(target);records.append(dict(original=oldpin,prospective=result,original_functions_AST_unchanged=unchanged,
        original_tcp_only_renamed_and_retained=True,helper_functions_AST_equal_after_declared_renames=True));return result
io=create('io',P/'observe_socket_cap_inet_diag_v1.py', '''def tcp():
    snapshot=_inet_capture()
    raw=json.dumps(snapshot,separators=(',',':'),allow_nan=False).encode()+b'\\n'
    # Return even failed/truncated dumps. The collector persists their actual
    # bytes before the strict parser rejects the original observation.
    return dict(begin_unix_s=snapshot['begin_unix_s'],end_unix_s=snapshot['end_unix_s'],
        original_format=_INET_SCHEMA,original_capture_error=snapshot['error']),raw
''')
primitives=create('primitives',P/'certify_owned_inet_diag_overlap_v2.py', '''def tcp(raw):
    require(type(raw)is bytes and 0<len(raw)<=2<<20 and raw.endswith(b'\\n'),
        'Complete bounded original socket-dump envelope bytes required')
    return _inet_parse(decode(raw))[0]
''')
D.mkdir(mode=0o700)
family=copy.deepcopy(original_job);family['sources'].update(io=io,primitives=primitives)
fp=h.put(D/'unselected-health-job.json',family)
h.put(D/'source-family-provenance.json',dict(schema='robotron-inet-diag-unselected-capture-family-provenance-v1',helper=h.pin(helper),source_changes=records,
    original_health_job=original_job,prospective_health_job=fp,embedded_renames=renames,
    all_other10_health_sources_unchanged=True,all_nonTCP_primitive_and_IO_functions_AST_unchanged=True,
    original_collector_Writer_engine_raw_timing_and_all_health_game_limits_unchanged=True,
    complete_original_kernel_messages_retained=True,no_proc_row_reformat_filter_retry_or_normalization=True,
    original_failed_jobs_and_source_families_not_reinterpreted=True,scientific_selection=False,quality_qualified=False))
print(json.dumps(dict(health_job=fp,io=io,primitives=primitives)))
