import json,subprocess,pathlib,time,sys
J=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/warmup-repeatability-independent-cpu-numerical-reviewed2-20261017')
commands=[['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/warmup-repeatability-independent-cpu-auditor-reviewed2-preparation-20261017/test_audit_payloads.py', '-v'], ['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/warmup-repeatability-independent-cpu-auditor-reviewed2-preparation-20261017/audit_payloads.py', '--execute', '--job', 'warmup-repeatability-reviewed1-20261017', '--source-sha256', '910644d642ac5c47304af36e2e5976050b5d4efb6d24fa528b80e477e0329d85', '--pins-sha256', 'a84373e54bdd60817931f565decbbf9cc5b92aa3a40756b62f32de50018bb280', '--output', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/warmup-repeatability-independent-cpu-numerical-reviewed2-20261017/analysis']]
results=[]
for index,argv in enumerate(commands):
 with (J/(str(index)+".stdout")).open("x") as out,(J/(str(index)+".stderr")).open("x") as err:
  started=time.monotonic(); q=subprocess.run(argv,stdout=out,stderr=err,timeout=110)
 result=dict(index=index,argv=argv,returncode=q.returncode,elapsed_s=time.monotonic()-started); results.append(result)
 with (J/(str(index)+".completion.json")).open("x") as f: json.dump(result,f,indent=2)
 if q.returncode: sys.exit(q.returncode)
with (J/"children-completion.json").open("x") as f:json.dump(dict(status="PASS",results=results),f,indent=2)
