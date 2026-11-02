import hashlib,importlib.util,json,pathlib,sys,time
job=json.loads(pathlib.Path(sys.argv[1]).read_text())
def mod(name,p):
 q=pathlib.Path(p['path']);assert hashlib.sha256(q.read_bytes()).hexdigest()==p['sha256'];s=importlib.util.spec_from_file_location(name,q);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
l=mod('startup_thaw_linux',job['linux']);p=mod('startup_thaw_poststop',job['poststop']);o=job['owner'];l.live_owner(o);result=p.thaw_startup_save(l,o);out=pathlib.Path(job['result']);out.write_text(json.dumps(dict(result=result,owner=o,completed_unix_s=time.time()))+'\n');out.chmod(0o444)
