import json,subprocess,pathlib,time,sys
J=pathlib.Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/recomputed-capture-private-CPU20-reviewed2-20261017')
commands=[['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B', '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/revision2/test_recomputed_capture.py', '-v'], ['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B', '-c', "import importlib.util,sys,unittest; p=sys.argv[1]; s=importlib.util.spec_from_file_location('private_recomputed_whole_selected',p); m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); suite=unittest.defaultTestLoader.loadTestsFromTestCase(m.WholeRecomputedCaptureTests); assert suite.countTestCases()==6; result=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(0 if result.wasSuccessful() else 1)", '/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/revision2/test_whole_training_capture.py']]
results=[]
for index,argv in enumerate(commands):
 with (J/(str(index)+".stdout")).open("x") as out,(J/(str(index)+".stderr")).open("x") as err:
  started=time.monotonic(); q=subprocess.run(argv,stdout=out,stderr=err,timeout=110)
 result=dict(index=index,argv=argv,returncode=q.returncode,elapsed_s=time.monotonic()-started); results.append(result)
 with (J/(str(index)+".completion.json")).open("x") as f: json.dump(result,f,indent=2)
 if q.returncode: sys.exit(q.returncode)
with (J/"children-completion.json").open("x") as f:json.dump(dict(status="PASS",results=results),f,indent=2)
