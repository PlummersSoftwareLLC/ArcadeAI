"""One fixed CPU validation; brief startup delay permits live owner observation."""
import os
import time

time.sleep(2)
argv = [
    '/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B',
    '-m', 'unittest', 'discover', '-s',
    '/home/dave/source/repos/ArcadeAI/Robotron/tools/continuous_zero_dip_wave2_proposal',
    '-p', 'test_continuous_zero_dip_reviewed2.py', '-v',
]
os.execv(argv[0], argv)
