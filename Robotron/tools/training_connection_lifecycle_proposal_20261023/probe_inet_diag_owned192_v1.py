"""Forty original kernel dumps joined to fresh complete192 FD ownership views."""
import argparse,hashlib,importlib.util,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
def load(pin,name):
    path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-prototype-inet-diag-owned192-probe-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    h=load(job['helpers'],'_diag_probe_h');diag=load(job['prototype'],'_diag_probe_parser');io=load(job['io'],'_diag_probe_io');p=load(job['primitives'],'_diag_probe_p');indexed=load(job['indexed_join'],'_diag_probe_indexed');transport=load(job['transport'],'_diag_probe_transport')
    for pin in job['inputs']:h.checked(pin)
    p=indexed.bind(p);binding=json.loads(h.checked(job['binding']).read_bytes());root=Path(job['output']);root.mkdir(mode=0o700)
    def monitor():return json.loads(subprocess.check_output(['/usr/bin/python3.12','-I','-B',job['monitor']['path']],text=True,timeout=25))
    before=monitor();records=[]
    for index in range(40):
        started=time.monotonic()
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=.4)as response:api_bytes=response.read((1<<20)+1)
        api=p.decode(api_bytes);snapshot=diag.capture();pin=h.put(root/('%03d-original-netlink.json'%index),snapshot)
        table,summary=diag.parse(snapshot)
        begin=time.time();fds=dict(trainer=io.fd_inodes(binding['owner']['pid']),actors={str(actor['slot']):io.fd_inodes(actor['pid'])for actor in binding['actors']})
        fds.update(begin_unix_s=begin,end_unix_s=time.time());fdpin=h.put(root/('%03d-original-fds.json'%index),fds)
        view=p.fd_view(json.dumps(fds,separators=(',',':')).encode(),binding,time.time());joined=transport.full_owned_join(p,table,view)
        assert len(joined)==192 and api['client_count']==192 and len(p.rows(api))==192
        records.append(dict(index=index,original_netlink=pin,original_FD_view=fdpin,API=h.put(root/('%03d-original-API.json'%index),api),parsed_summary=summary,actual_owned_pairs=192,wall_s=time.monotonic()-started))
        time.sleep(max(0.,.2-(time.monotonic()-started)))
    after=monitor();assert before['owner']==after['owner']and after['client_count']==192 and after['held_inputs']==197
    for pin in job['inputs']:h.checked(pin)
    assert 'torch'not in sys.modules
    report=h.put(root/'report.json',dict(schema='robotron-prototype-inet-diag-owned192-probe-report-v1',prototype=job['prototype'],records=records,
        actual_original_kernel_dumps=40,all192_owned_pairs_joined_in_each=True,main_before=before,main_after=after,
        not_a_full_health_stream_or_native_load_proof=True,no_collector_or_scientific_selection=True,old_proc_copy_limit_unchanged=2,production_changed=False,quality_qualified=False,created_unix_s=time.time()))
    print(json.dumps(dict(report=report,snapshots=40)),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
