"""Fresh original05 capture and readiness120 quiescence cap8 CPU profiles. Default inert.

Root-only explicit modes prepare metadata or reuse the unchanged original CPU
closer. No mode launches a CPU/service/game/scientific job or changes learning.
Unknown current case/engineering/cap evidence is supplied by immutable Root
selection after its real qualifications; no old profile/score is adopted.
"""
import argparse,hashlib,importlib.util,json,os,re,sys
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CANDIDATE='4ab677004e8a178f69d4438583a07d00a76f3b90e09eb08870ad0528fc08f871'
REFERENCE='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
FIXED={'profile_api': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/prepare_and_close_profile_cpu_v2.py', 'sha256': 'dc4b811b57b05e0a439ef2345d0dc73f6db42578b672511d13ec08ddda65ff8c', 'bytes': 10053, 'identity': {'device': 2304, 'inode': 84708521, 'bytes': 10053, 'mtime_ns': 1793221310159594380, 'ctime_ns': 1793221310159594380, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'benchmark': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/benchmark_sidecar_inference.py', 'sha256': '39d90c6dc70d69a4fef4c7244868819ddd06f7cc4283998d821632cf0ce2bde5', 'bytes': 16421, 'identity': {'device': 2304, 'inode': 79965881, 'bytes': 16421, 'mtime_ns': 1792122331445724145, 'ctime_ns': 1792122331445724145, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'frozen_driver': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/check_frozen_profile_cpu_v2.py', 'sha256': '941333f31ec4a1f4e83a9c4ebc7cc639459b0654057e3237daf52f424bf7ae7d', 'bytes': 3034, 'identity': {'device': 2304, 'inode': 84702870, 'bytes': 3034, 'mtime_ns': 1793160670301732716, 'ctime_ns': 1793160670301732716, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'adopter': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/adopt_profile_scope_v2.py', 'sha256': '30d6fb41599a6eb2977421dd1cb2a5638bc6b148c349cfea2b10d7ab7372f8bb', 'bytes': 7225, 'identity': {'device': 2304, 'inode': 84704201, 'bytes': 7225, 'mtime_ns': 1793171634710878615, 'ctime_ns': 1793171634710878615, 'mode': '0o664', 'uid': 1001, 'nlink': 1}}, 'controller': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/control_quality32_review_v1.py', 'sha256': '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'bytes': 17290, 'identity': {'device': 2304, 'inode': 81930188, 'bytes': 17290, 'mtime_ns': 1792424008109022468, 'ctime_ns': 1792424257834393599, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'observer_map': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-quiescence-readiness120-overlay-original06/prospective-current-EVAL-quiescence-readiness120-eight-role-source-map-v1.json', 'sha256': 'c8231a36c0028567a6a7da884046aa98ceeaf0fc6f0c338e4230fd305fb7e553', 'bytes': 7725, 'identity': {'device': 2304, 'inode': 85355715, 'bytes': 7725, 'mtime_ns': 1793310753661479590, 'ctime_ns': 1793310753661479590, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'protected_reference_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03/R1/job.json', 'sha256': 'f34511e9e860342887681958fadc7e465e7b49a7c115d15dd36e57a9cf0b0d33', 'bytes': 95725, 'identity': {'device': 2304, 'inode': 80763099, 'bytes': 95725, 'mtime_ns': 1793055492480886407, 'ctime_ns': 1793055492480886407, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'engineering_closer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/quiescence-readiness120-engineering-original05-preparation/close_physical192_engineering_v5.py', 'sha256': '8f812f5cefb8e4e77182062bfb73f77e48598279508dc2d8c2de5c2a8500b026', 'bytes': 11451, 'identity': {'device': 2304, 'inode': 85355802, 'bytes': 11451, 'mtime_ns': 1793310835429468528, 'ctime_ns': 1793310960502771650, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_family': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/prepared-current-EVAL-quiescence-profile-deadline13-corrected-guard-SOURCE-ONLY-v6.json', 'sha256': '997ca21fabf6fd2a1edc183ff6857ee60d97119b2ff352580632a609e7260e26', 'bytes': 31130, 'identity': {'device': 2304, 'inode': 85358608, 'bytes': 31130, 'mtime_ns': 1793312011317572079, 'ctime_ns': 1793312011317572079, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/independent-current-EVAL-quiescence-readiness120-private13-and-fresh-capture-association-source-peer-v6.json', 'sha256': 'ae3e5b6deb2c5fef092411d65e7428679ea991ee9052cc2d8b22a0dd5c79cca8', 'bytes': 25692, 'identity': {'device': 2304, 'inode': 85358806, 'bytes': 25692, 'mtime_ns': 1793312070106492592, 'ctime_ns': 1793312070106492592, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'engineering_finalizer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/quiescence-readiness120-engineering-original05-preparation/finalize_physical192_engineering_v5.py', 'sha256': '3c83509c3c7e7eab08ed6417a4c96289fef6fd4cd2dc067853db2cb2fbbc568d', 'bytes': 22687, 'identity': {'device': 2304, 'inode': 85355803, 'bytes': 22687, 'mtime_ns': 1793310960504620138, 'ctime_ns': 1793310960506771667, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'shared_domain_helper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/physical_profile_contract_v5.py', 'sha256': '182b5678948fdc3e05c234f76dfeb0dcb1298560fb4815274742dab4e159d73c', 'bytes': 16858, 'identity': {'device': 2304, 'inode': 85235757, 'bytes': 16858, 'mtime_ns': 1793311425821202483, 'ctime_ns': 1793311527249199177, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_case': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-quiescence-readiness120-overlay-original06/actual-main-case-original01/current-EVAL-quiescence-readiness120-main-case-v1.json', 'sha256': 'e40c635508121ebdc65ced786f0c058160bed000318c7a614b9154085ef4c55a', 'bytes': 1337713, 'identity': {'device': 2304, 'inode': 85355949, 'bytes': 1337713, 'mtime_ns': 1793310977681079532, 'ctime_ns': 1793310977681079532, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'physical_inventory': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-quiescence-readiness120-overlay-original06/actual-main-case-original01/exact-held-input-inventory-readiness120-v1.json', 'sha256': '98c6a33fc3ab082a85d6df60de39570bb6549930cccc9aa91c509f424ffbd01a', 'bytes': 317478, 'identity': {'device': 2304, 'inode': 85355948, 'bytes': 317478, 'mtime_ns': 1793310977633750693, 'ctime_ns': 1793310977633750693, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/window-plan-typed-Adam-adopted-v1.json', 'sha256': 'c0aecb8f555571e7f52ffd9341328b25629097ac3b3cc0816bffe72889528a5e', 'bytes': 61861, 'identity': {'device': 2304, 'inode': 81397990, 'bytes': 61861, 'mtime_ns': 1793327440360811628, 'ctime_ns': 1793327440360811628, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_result': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/result.json', 'sha256': '9c61d9c1203b88cd9ff13f94d08f775580276f90526d7d8b763af76adda0beb5', 'bytes': 2273, 'identity': {'device': 2304, 'inode': 81398037, 'bytes': 2273, 'mtime_ns': 1793331087831753210, 'ctime_ns': 1793331087831753210, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/endpoint-CPU.json', 'sha256': '2aab1aa66962b9aac21eae5d4e294d9fe55d29568215d3ee0f56c53bdcbe1e75', 'bytes': 3145, 'identity': {'device': 2304, 'inode': 81398034, 'bytes': 3145, 'mtime_ns': 1793331087042149249, 'ctime_ns': 1793331087042149249, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_anchor': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/anchor.raw.json', 'sha256': '4b8908606d860209fb330df0e74bff2487c6de9b53ff9cd1046d99707b89f70a', 'bytes': 126546, 'identity': {'device': 2304, 'inode': 81397996, 'bytes': 126546, 'mtime_ns': 1793327440519076484, 'ctime_ns': 1793327440519076484, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_threshold': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/first-threshold.raw.json', 'sha256': 'aa255b789bdd0a16a315ac71526af77775d110f483afe2aaf5feb820e44fee1e', 'bytes': 126525, 'identity': {'device': 2304, 'inode': 81398028, 'bytes': 126525, 'mtime_ns': 1793331043853164188, 'ctime_ns': 1793331043853164188, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_context': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/capture-context.raw.json', 'sha256': '480626a71be560c1b31c2c93936862b3e51a5d16f6be7835bc418b01bd0f3d7a', 'bytes': 126601, 'identity': {'device': 2304, 'inode': 81398031, 'bytes': 126601, 'mtime_ns': 1793331084228438682, 'ctime_ns': 1793331084228438682, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU_owner': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-original-owner.json', 'sha256': '4775693d5b3318d5bb50edd28d27a3caaa6967a5d2be80f089d9543c71172282', 'bytes': 12755, 'identity': {'device': 2304, 'inode': 81398033, 'bytes': 12755, 'mtime_ns': 1793331084260318856, 'ctime_ns': 1793331084260318856, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU_terminal': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-original-terminal.json', 'sha256': 'c279cc662dd7b1c061c420cc611048e75a29b6d9e2a258712249a27b80032804', 'bytes': 12008, 'identity': {'device': 2304, 'inode': 81398035, 'bytes': 12008, 'mtime_ns': 1793331087810236240, 'ctime_ns': 1793331087810236240, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_CPU_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-owned-release.json', 'sha256': '46cabf631403536a3101357204712062b18426c164296a1149b7c160ac9874b0', 'bytes': 34529, 'identity': {'device': 2304, 'inode': 81398036, 'bytes': 34529, 'mtime_ns': 1793331087824092544, 'ctime_ns': 1793331087824092544, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_observer_launch': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-typed-window-observer-actual-launch-original01.json', 'sha256': 'f1a7f317a9ab87bb30a411d085a159539da4beda6be779335531fe7576af7c0d', 'bytes': 14585, 'identity': {'device': 2304, 'inode': 81397995, 'bytes': 14585, 'mtime_ns': 1793327440426264750, 'ctime_ns': 1793327440426264750, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_observer_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-original05-observer-owned-closeout-original01/Root-original05-observer-normal0-owned-release.json', 'sha256': 'eaac2f883af9ade171ad8ae93db78c48e432882961934e86d179ae9c57ad72a7', 'bytes': 11247, 'identity': {'device': 2304, 'inode': 81398068, 'bytes': 11247, 'mtime_ns': 1793332499788233754, 'ctime_ns': 1793332499788233754, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_root_selection': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/Root-selected-fresh-continuous-window-original05.json', 'sha256': '69628f61c4fe2b16e6a322f28fe9d5704777435f67c37a43f402d4acf49f69ce', 'bytes': 35523, 'identity': {'device': 2304, 'inode': 81397835, 'bytes': 35523, 'mtime_ns': 1793323383743743878, 'ctime_ns': 1793323383743743878, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'closed_capture_validator': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/fresh-original05-typed-Adam-cap8-profile-preparation-original05/verify_closed_original05_typed_capture_v1.py', 'sha256': '111eb202f73c3457ccf589576c1c97de01a5adb18d55419108285d5f1ed02507', 'bytes': 26611, 'identity': {'device': 2304, 'inode': 85459427, 'bytes': 26611, 'mtime_ns': 1793333815369822958, 'ctime_ns': 1793334151617301345, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'capture_eligibility_overlay': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/prepare_round_study_typed_capture_v12.py', 'sha256': 'a589b99db6b38a31a68e7175263d860673ce38b6a4447e14ec3fc783af3786b4', 'bytes': 32976, 'identity': {'device': 2304, 'inode': 85393809, 'bytes': 32976, 'mtime_ns': 1793334238613920906, 'ctime_ns': 1793334238613920906, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/window-plan-typed-Adam-adopted-v1.json', 'sha256': 'c0aecb8f555571e7f52ffd9341328b25629097ac3b3cc0816bffe72889528a5e', 'bytes': 61861, 'identity': {'device': 2304, 'inode': 81397990, 'bytes': 61861, 'mtime_ns': 1793327440360811628, 'ctime_ns': 1793327440360811628, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_prior_plan': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/window-plan.json', 'sha256': '97dd5446aa9f4289f3d2ac4bbaffb9e2776847d7f736a5cce4f797e85277857a', 'bytes': 56491, 'identity': {'device': 2304, 'inode': 81397970, 'bytes': 56491, 'mtime_ns': 1793326457945642689, 'ctime_ns': 1793326457945642689, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_result': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/result.json', 'sha256': '9c61d9c1203b88cd9ff13f94d08f775580276f90526d7d8b763af76adda0beb5', 'bytes': 2273, 'identity': {'device': 2304, 'inode': 81398037, 'bytes': 2273, 'mtime_ns': 1793331087831753210, 'ctime_ns': 1793331087831753210, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/endpoint-CPU.json', 'sha256': '2aab1aa66962b9aac21eae5d4e294d9fe55d29568215d3ee0f56c53bdcbe1e75', 'bytes': 3145, 'identity': {'device': 2304, 'inode': 81398034, 'bytes': 3145, 'mtime_ns': 1793331087042149249, 'ctime_ns': 1793331087042149249, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_CPU_owner': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-original-owner.json', 'sha256': '4775693d5b3318d5bb50edd28d27a3caaa6967a5d2be80f089d9543c71172282', 'bytes': 12755, 'identity': {'device': 2304, 'inode': 81398033, 'bytes': 12755, 'mtime_ns': 1793331084260318856, 'ctime_ns': 1793331084260318856, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_CPU_terminal': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-original-terminal.json', 'sha256': 'c279cc662dd7b1c061c420cc611048e75a29b6d9e2a258712249a27b80032804', 'bytes': 12008, 'identity': {'device': 2304, 'inode': 81398035, 'bytes': 12008, 'mtime_ns': 1793331087810236240, 'ctime_ns': 1793331087810236240, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_CPU_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-owned-release.json', 'sha256': '46cabf631403536a3101357204712062b18426c164296a1149b7c160ac9874b0', 'bytes': 34529, 'identity': {'device': 2304, 'inode': 81398036, 'bytes': 34529, 'mtime_ns': 1793331087824092544, 'ctime_ns': 1793331087824092544, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_CPU_launch': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/CPU-original-launch.json', 'sha256': '82ffd6a86f31fd9b3432b083d1979400e3781181bbeff429e5e4c95dc9db172a', 'bytes': 1338, 'identity': {'device': 2304, 'inode': 81398032, 'bytes': 1338, 'mtime_ns': 1793331084253096655, 'ctime_ns': 1793331084253096655, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_anchor': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/anchor.raw.json', 'sha256': '4b8908606d860209fb330df0e74bff2487c6de9b53ff9cd1046d99707b89f70a', 'bytes': 126546, 'identity': {'device': 2304, 'inode': 81397996, 'bytes': 126546, 'mtime_ns': 1793327440519076484, 'ctime_ns': 1793327440519076484, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_threshold': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/first-threshold.raw.json', 'sha256': 'aa255b789bdd0a16a315ac71526af77775d110f483afe2aaf5feb820e44fee1e', 'bytes': 126525, 'identity': {'device': 2304, 'inode': 81398028, 'bytes': 126525, 'mtime_ns': 1793331043853164188, 'ctime_ns': 1793331043853164188, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_context': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/capture-context.raw.json', 'sha256': '480626a71be560c1b31c2c93936862b3e51a5d16f6be7835bc418b01bd0f3d7a', 'bytes': 126601, 'identity': {'device': 2304, 'inode': 81398031, 'bytes': 126601, 'mtime_ns': 1793331084228438682, 'ctime_ns': 1793331084228438682, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_entry_authority': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-CPU-authority.json', 'sha256': '42b76c1f9e54ef8a2d7a086dddc7065e81507dfcf6dff5f4061a8a7e791a18b9', 'bytes': 2246, 'identity': {'device': 2304, 'inode': 81397850, 'bytes': 2246, 'mtime_ns': 1793323469732135418, 'ctime_ns': 1793323469732135418, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_entry_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-CPU-original01/endpoint-CPU.json', 'sha256': '201d546e43ac545612d9cebee4b09f3d767b24c201c37f25ec9233b37c636aa4', 'bytes': 2117, 'identity': {'device': 2304, 'inode': 81397847, 'bytes': 2117, 'mtime_ns': 1793323468884708979, 'ctime_ns': 1793323468884708979, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_typed_entry_authority': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-same-entry-typed-Adam-CPU-authority-original01.json', 'sha256': 'c355b8ce6b93c28cb89d893adbf04cbf9be264833b4a41e894e90c68d9589b19', 'bytes': 2556, 'identity': {'device': 2304, 'inode': 81397988, 'bytes': 2556, 'mtime_ns': 1793327440356794286, 'ctime_ns': 1793327440356794286, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_typed_entry_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/endpoint-CPU.json', 'sha256': '385bc603faf2433f5b67281da66847995f4239f2910282a12b088e4c4e016eb7', 'bytes': 3163, 'identity': {'device': 2304, 'inode': 81397978, 'bytes': 3163, 'mtime_ns': 1793326460792335443, 'ctime_ns': 1793326460792335443, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_typed_entry_owner': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/CPU-original-owner.json', 'sha256': '2a1e44393d638e8a3f39813429d07a8efe817a9420918989c08365516b2bef83', 'bytes': 12945, 'identity': {'device': 2304, 'inode': 81397977, 'bytes': 12945, 'mtime_ns': 1793326458032782659, 'ctime_ns': 1793326458032782659, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_typed_entry_terminal': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/CPU-original-terminal.json', 'sha256': '9f02a2f2d1bd3d1e76f0c12776b9b00ff29e6466dac210b6ce062dd2efff6d2b', 'bytes': 12182, 'identity': {'device': 2304, 'inode': 81397979, 'bytes': 12182, 'mtime_ns': 1793326461577667214, 'ctime_ns': 1793326461577667214, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_typed_entry_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/CPU-owned-release.json', 'sha256': '738ad5df7b2239efd8a3d7adf485b2d7f7fb45093fd91d2e97cb1cdb519cbd58', 'bytes': 34925, 'identity': {'device': 2304, 'inode': 81397980, 'bytes': 34925, 'mtime_ns': 1793326461588126641, 'ctime_ns': 1793326461588126641, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_source_amendment': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-selected-typed-Adam-source-amendment-original01.json', 'sha256': '4b89655b76abd1ec655ec6a9964890b330bfbb605c3bf9b6096e98249b4b5c5b', 'bytes': 7226, 'identity': {'device': 2304, 'inode': 81397989, 'bytes': 7226, 'mtime_ns': 1793327440358537325, 'ctime_ns': 1793327440358537325, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_observer_launch': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-typed-window-observer-actual-launch-original01.json', 'sha256': 'f1a7f317a9ab87bb30a411d085a159539da4beda6be779335531fe7576af7c0d', 'bytes': 14585, 'identity': {'device': 2304, 'inode': 81397995, 'bytes': 14585, 'mtime_ns': 1793327440426264750, 'ctime_ns': 1793327440426264750, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_observer_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05/Root-original05-observer-owned-closeout-original01/Root-original05-observer-normal0-owned-release.json', 'sha256': 'eaac2f883af9ade171ad8ae93db78c48e432882961934e86d179ae9c57ad72a7', 'bytes': 11247, 'identity': {'device': 2304, 'inode': 81398068, 'bytes': 11247, 'mtime_ns': 1793332499788233754, 'ctime_ns': 1793332499788233754, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_watcher': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/typed-Adam-saturation-successor-source-original01/watch_replay_progress_typed_Adam_saturation_v3.py', 'sha256': '98ffb7eee78101b91ea29e9252b9368b011bed2befa75504fa14c240ded945a5', 'bytes': 19453, 'identity': {'device': 2304, 'inode': 81397871, 'bytes': 19453, 'mtime_ns': 1793324444286292431, 'ctime_ns': 1793324763227915708, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_library': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original04-preparation/watch_learning_window_continuous_v4.py', 'sha256': '4dc714d1677f58ebebd39002e1c9f42df4828fe0ef87795b714a2f2c210938fd', 'bytes': 18615, 'identity': {'device': 2304, 'inode': 85351385, 'bytes': 18615, 'mtime_ns': 1793306998562707000, 'ctime_ns': 1793306998562863608, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_verifier': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/typed-Adam-saturation-successor-source-original01/verify_snapshot_raw_Adam_steps_v1.py', 'sha256': '5bac4062afcf3cdf57726e13e2f1eacc37af4a819932da752452ccace93919bb', 'bytes': 5201, 'identity': {'device': 2304, 'inode': 81397870, 'bytes': 5201, 'mtime_ns': 1793324703499017045, 'ctime_ns': 1793324763227915708, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_source_family': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/typed-Adam-saturation-successor-source-original01/prepared-original05-typed-Adam-saturation-capture-successor-SOURCE-ONLY-UNSELECTED-v1.json', 'sha256': 'e376bbebbdf0ad9fbfa9c6b68c19f9323dca665aca63094595933664e83e4798', 'bytes': 14277, 'identity': {'device': 2304, 'inode': 81397937, 'bytes': 14277, 'mtime_ns': 1793324776630808634, 'ctime_ns': 1793324776630808634, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_source_peer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/typed-Adam-saturation-successor-source-original01/independent-original05-typed-Adam-saturation-verifier-and-watcher-source-peer-v1.json', 'sha256': 'd7c60a03b43db89ff03aba7fc39035788adb4153b23638a58205e12f1d684e56', 'bytes': 11286, 'identity': {'device': 2304, 'inode': 81397938, 'bytes': 11286, 'mtime_ns': 1793324931731027397, 'ctime_ns': 1793324931731027397, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_root_selection': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation/Root-selected-fresh-continuous-window-original05.json', 'sha256': '69628f61c4fe2b16e6a322f28fe9d5704777435f67c37a43f402d4acf49f69ce', 'bytes': 35523, 'identity': {'device': 2304, 'inode': 81397835, 'bytes': 35523, 'mtime_ns': 1793323383743743878, 'ctime_ns': 1793323383743743878, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'original05_evidence_domain_helper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/physical_profile_contract_v5.py', 'sha256': '182b5678948fdc3e05c234f76dfeb0dcb1298560fb4815274742dab4e159d73c', 'bytes': 16858, 'identity': {'device': 2304, 'inode': 85235757, 'bytes': 16858, 'mtime_ns': 1793311425821202483, 'ctime_ns': 1793311527249199177, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
PRIVATE_ENV={'ROBOTRON_CONTINUOUS_TRAINING_MODE':'0','ROBOTRON_ROLLING_TRAINING_CLEANUP':'0','ROBOTRON_CONTINUOUS_STARTUP_HOLD':'0','DQN_MAX_SAMPLES_PER_FRAME':'8'}

def require(ok,reason):
    if not ok:raise ValueError(reason)

def load(name,entry):
    p=Path(entry['path']);require(hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'],'Selected existing source changed')
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def dependencies():
    h=load('_physical192_profile_helpers',FIXED['helpers'])
    for entry in FIXED.values():h.checked(entry)
    return h,load('_physical192_original_profile_API',FIXED['profile_api'])

def read(entry,h):
    require(entry['identity']['mode']=='0o444' and entry['identity']['uid']==os.getuid() and entry['identity']['nlink']==1,'Immutable owned metadata required')
    return json.loads(h.checked(entry).read_bytes())

def capture_input_pins(plan,h):
    # Window inputs are exactly thin3 pins, not the full8 source/control domain.
    values=[]
    for value in plan['inputs']:
        require(type(value)is dict and set(value)=={'path','sha256','bytes'},'Exact thin3 original window input required')
        path=Path(value['path']);require(path.is_absolute() and not path.is_symlink() and path.is_file(),'Regular selected capture input required')
        actual=h.pin(path)
        require(all(actual[key]==value[key] for key in value),'Original window input changed')
        values.append(actual)
    require(values and len({v['path'] for v in values})==len(values),'Distinct original window inputs required')
    return values

def normal_terminal(terminal,live,pid,invocation,expected):
    require(terminal['Id']==live['Id'] and terminal['MainPID']=='0'
        and terminal['ExecMainPID']==str(pid) and terminal['InvocationID']==invocation
        and terminal['ExecMainCode']=='1' and terminal['ExecMainStatus']=='0'
        and all(terminal[key]==value and live[key]==value for key,value in expected.items()),
        'Exact original normal0 terminal and unchanged resources required')

def capture(h):
    verifier=load('_profile_exact_closed_original05',FIXED['closed_capture_validator'])
    value=verifier.verify_closed_capture(h)
    require(value['capture_plan']==FIXED['capture_plan'] and value['capture_result']==FIXED['capture_result']
        and value['result']['endpoint']['sha256']==CANDIDATE,'Only exact closed original05 capture is eligible')
    return value['result'],value['CPU']


def capture_qualification_payload(h):
    result,cpu=capture(h)
    return dict(schema='robotron-root-original-valid-capture-qualification-v1',
        status='CAPTURE_CPU_VERIFIED_AND_ORIGINAL_SCOPE_CLOSED',source=h.pin(Path(__file__).resolve()),
        capture_plan=FIXED['capture_plan'],capture_result=FIXED['capture_result'],actual_original_exit=0,original_scope_released=True,
        numerical_CPU=FIXED['capture_CPU'],original_CPU_owner=FIXED['capture_CPU_owner'],original_CPU_terminal=FIXED['capture_CPU_terminal'],
        original_CPU_release=FIXED['capture_CPU_release'],original_observer_launch=FIXED['capture_observer_launch'],
        original_observer_release=FIXED['capture_observer_release'],capture_root_selection=FIXED['capture_root_selection'],
        typed_progress_verifier=FIXED['closed_capture_validator'],typed_progress_proof=result['progress_proof'],
        capture_source_amendment=FIXED['original05_evidence_source_amendment'],
        typed_entry_CPU=FIXED['original05_evidence_typed_entry_CPU'],typed_entry_authority=FIXED['original05_evidence_typed_entry_authority'],
        policy_checkpoint_sha256=CANDIDATE,new_exposure_credited=False,quality_qualified=False)

def qualify_capture(output):
    h,api=dependencies();payload=capture_qualification_payload(h)
    output=Path(output).absolute();require(output.resolve()==output and not output.exists()and output.parent.is_dir(),
        'Fresh capture-qualification metadata directory required')
    output.mkdir(mode=0o700)
    return h.put(output/'original-valid-capture-qualification.json',payload)

def case_input_pins(case,h):
    require(isinstance(case['inputs'],dict) and case['inputs'],'Exact typed-case input map required')
    result=[]
    for path,row in case['inputs'].items():
        entry=dict(path=path,sha256=row['sha256'],bytes=row['identity']['bytes'],identity=row['identity'])
        h.checked(entry)
        result.append(entry)
    return result

def selection(path,sha,h):
    sp=h.pin(Path(path).resolve());require(sp['sha256']==sha,'Exact fresh Root selection required');s=read(sp,h)
    require(s['schema']=='robotron-root-current-quiescence-cap8-fresh-window-profile-selection-v5'
        and s['status']=='ACTUAL_TYPED_CONTEXT_SELECTED_FOR_FRESH_CPU_PROFILES'
        and s['source_family']==FIXED['physical_family'] and s['source_peer']==FIXED['physical_peer']
        and re.fullmatch('[0-9a-f]{32}',s['study_uuid']or'')and s['study_uuid']!='0'*32
        and s['all_four_profiles_are_fresh']is True and s['no_old_scores_or_jobs_reused']is True
        and s['candidate_policy_sha256']==CANDIDATE and s['reference_policy_sha256']==REFERENCE
        and s['capture_eligibility_overlay']==FIXED['capture_eligibility_overlay'],
        'Actual fresh original05 physical context and explicit eligibility-source selection required')
    case=read(s['main_case'],h);c=case['continuous']
    require(case['schema']=='robotron-original192-live-pidfd-current-eval-quiescence-case-v5'
        and c['mode']=='CONTINUOUS_TRAIN155_EVAL37_ONCE' and c['accepted_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
        and set(case['slot_eval'])==set(map(str,range(192))) and all(type(v)is bool for v in case['slot_eval'].values())
        and sum(case['slot_eval'].values())==37,'Actual original192 physical context required')
    case_input_pins(case,h)
    require(s['main_case']==FIXED['physical_case']
        and case['input_inventory_authority']==FIXED['physical_inventory'],
        'Exact newly prepared physical case/inventory required, never old static authority')
    shared=load('_physical192_profile_domain',FIXED['shared_domain_helper'])
    shared.validate_inventory(case,h)
    for entry in (c['source_authority'],c['original_membership'],c['initial_barrier'],case['input_inventory_authority']):read(entry,h)
    cap=read(s['cap8_runtime_authority'],h)
    require(cap['schema']=='robotron-root-current-physical192-cap8-profile-context-v2'
        and cap['main_case']==s['main_case'] and cap['trainer']==c['trainer'] and cap['source_authority']==c['source_authority']
        and cap['environment']['DQN_MAX_SAMPLES_PER_FRAME']=='8'
        and cap['environment']['ROBOTRON_CONTINUOUS_TRAINING_MODE']=='1'
        and cap['retained_original_unit_environment_verified']is True,'Actual retained current cap8 owner/environment evidence required')
    retained=read(cap['retained_unit_environment'],h)['trainer'];proc=retained['process'];env=proc['environment']
    require(retained['unit']==c['trainer']['unit'] and retained['invocation']==c['trainer']['invocation_id']
        and proc['pid']==c['trainer']['pid'] and proc['starttime_ticks']==c['trainer']['birth']
        and proc['cgroup']==c['trainer']['cgroup']
        and all(env.get(k)==v for k,v in {'DQN_MAX_SAMPLES_PER_FRAME':'8','DQN_BATCH_SIZE':'4096','DQN_N_STEP':'3','DQN_PER_PRIORITY_METRIC':'ce','ROBOTRON_CONTINUOUS_TRAINING_MODE':'1'}.items())
        and all(env.get(k)==v for k,v in cap['environment'].items()),'Retained actual owner/environment does not prove this cap8 recipe')
    engineering_association(s['main_qualification'],s,case,h)
    capture(h)
    require(read(s['original_capture_qualification'],h)==capture_qualification_payload(h),'Exact independently qualified and closed fresh capture required')
    association=shared.validate_fresh_capture_association(s['fresh_capture_context_association'],
        plan_pin=FIXED['capture_plan'],result_pin=FIXED['capture_result'],plan=read(FIXED['capture_plan'],h),
        case=case,case_pin=s['main_case'],engineering_joint_pin=s['main_qualification'],h=h)
    require(association['original_capture_qualification']==s['original_capture_qualification'],
        'Current context must associate the same actual capture qualification')
    return s,sp,case

def engineering_association(joint_pin,s,case,h):
    joint=read(joint_pin,h);family=read(FIXED['physical_family'],h)
    mapped=read(FIXED['observer_map'],h);mapping=mapped['observer_sources']
    require(joint['schema']=='robotron-original192-immutable-bootstrap-live-pidfd-joint-engineering-readiness-v4'
        and joint['status']=='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY'
        and joint['source']==FIXED['engineering_finalizer']
        and joint['case']==s['main_case']==FIXED['physical_case']
        and joint['input_inventory_authority']==case['input_inventory_authority']==FIXED['physical_inventory']
        and joint['source_family']==family['typed_health_packet']
        and joint['observer_sources']==mapping and joint['observer_reviewer']==mapped['observer_reviewer']
        and joint['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'
        and joint['maximum_gap_s']==2.0 and joint['interval_s']==.2
        and joint['main_health_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
        and joint['current_once_only_EVAL_quiescence_with_historical_error_and_ready_false_preserved_verified']is True
        and joint['original_cleanup_deadline_handoff_CID_reuse_or_refill_success_from_exception_claimed']is False
        and joint['admission_basis']=='EVER_BOUND_ORIGINAL192_NOT_SIMULTANEOUS'
        and joint['simultaneous192_actors_claimed']is False
        and joint['all_original_engineering_scopes_closed_at_recorded_closer']is True
        and joint['all_three_modes_are_fresh_originals_for_this_physical_case']is True
        and joint['old_static_or_countbounded_failures_reused_or_requalified']is False
        and joint['long_work_contract']=='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S',
        'Actual fresh physical three-scope engineering joint required before any CPU profile')
    require(set(joint['engineering'])=={'warmup','long','abort'},'Exact fresh physical engineering modes required')
    for mode,row in joint['engineering'].items():
        closed=read(row['closeout'],h)
        require(closed['schema']=='robotron-original192-immutable-bootstrap-live-pidfd-original-engineering-closeout-v4'
            and closed['status']=='PASS_ENGINEERING_ONLY' and closed['kind']=='main-current-once-EVAL-quiescence192'
            and closed['mode']==mode and closed['source']==FIXED['engineering_closer']
            and closed['original_parent_actual_exit']==0
            and closed['worker_actual_exit']==(1 if mode=='abort' else 0)
            and closed['actual_parent_CPU_cores']==2 and closed['actual_parent_memory_bytes']==4<<30
            and closed['actual_parent_runtime_s']==(1800 if mode=='long' else 780)
            and closed['all_original_births_units_cgroups_and_tmpfs_control_absent']is True,
            'Actual fresh physical engineering original closure differs')
        probe=read(closed['actual_probe_result'],h);native=read(probe['original_job'],h)
        life=read(closed['worker_lifecycle'],h);worker=read(life['worker_job'],h)
        require(row['lifecycle']==closed['worker_lifecycle']
            and native['main_binding']==s['main_case'] and worker['case']==s['main_case']
            and worker['sources']==probe['sources']==mapping
            and probe['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'
            and probe['maximum_gap_s']==2.0
            and probe['main_health_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5',
            'Engineering is not this exact physical context/source family')
        if mode=='long':
            require(closed['long_work_contract']==probe['long_work_contract']
                        =='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S'
                and 600<=closed['actual_long_work_s']==probe['actual_long_work_s']<=1200
                and closed['last_validated_long_count']==probe['last_validated_long_count']>=3000,
                'Sustained600s and validated3000 samples are both required')
    raw=read(joint['independent_raw_review'],h)
    require(joint['lifecycle']==joint['engineering']['long']['lifecycle']
        and joint['independent_raw_review']==joint['engineering']['long']['independent_raw_review']
        and raw['status']=='PASS' and raw['lifecycle']==joint['lifecycle']
        and raw['original_sources']==mapping and raw['accepted_samples']>=3000
        and raw['full_main_input_count']==len(case['inputs'])
        and raw['main_health_profile']=='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
        and all(raw[key]is True for key in ('source_bound_original192_physical_bootstrap_verified',
            'TRAIN155_original_physical_and_current_TCP_verified',
            'EVAL37_original_connection_and_strict_retirement_evidence_verified',
            'EVAL_closed_slots_have_positive_normal0_reap_and_cleanup_verified',
            'prior_completed_EVAL_prefix_and_current_suffix_verified',
            'immutable_original192_bootstrap_certificate_verified','fresh_original_keeper_pidfd_census_verified',
            'authentic_published_normal0_exit_facts_and_monotone_coverage_verified',
            'current_once_only_EVAL_quiescence_with_historical_error_and_ready_false_preserved_verified'))
        and raw['original_cleanup_deadline_handoff_CID_reuse_or_refill_success_from_exception_claimed']is False,
        'Exact already-completed physical raw review required; no old raw replay is substituted')
    return joint

def prepare(path,sha,role,output,canonical_closeout=None):
    require(role in ('candidate','reference'),'Exact selected role required')
    h,api=dependencies();s,sp,case=selection(path,sha,h);result,cpu=capture(h)
    old=read(FIXED['protected_reference_job'],h)
    policy=dict(checkpoint=result['endpoint'],expected_policy_clocks=cpu['clocks'],authority=FIXED['capture_CPU']) if role=='candidate' else dict(checkpoint=old['checkpoint'],expected_policy_clocks=old['expected_policy_clocks'],authority=old['policy_authority'])
    require(policy['checkpoint']['sha256']==(CANDIDATE if role=='candidate' else REFERENCE),'Exact selected policy differs')
    checkpoint=h.pin(policy['checkpoint']['path']);require(all(checkpoint[k]==v for k,v in policy['checkpoint'].items()) and checkpoint['identity']['mode']=='0o444','Actual immutable checkpoint changed')
    mode='canonical'if canonical_closeout is None else'frozen'
    directory=Path(output).absolute();profile_root=Path(s['profile_root'])
    require(profile_root.is_absolute() and profile_root.resolve()==profile_root and profile_root.is_dir()
        and str(profile_root).startswith(str(ROOT/'logs/managed-learning-20261015/run-26')+'/')
        and directory==profile_root/(role+'-'+mode+'-CPU-original01')
        and directory.resolve()==directory and not directory.exists(),'Exact fresh selected profile directory required')
    require(profile_root!=Path(FIXED['capture_result']['path']).parent and Path(FIXED['capture_result']['path']).parent not in profile_root.parents,'New context must not write inside historical capture')
    job=dict(checkpoint=checkpoint,benchmark=FIXED['benchmark'],output=str(directory/'runtime'))
    inputs=[checkpoint,FIXED['benchmark'],sp,s['main_case'],s['main_qualification'],s['cap8_runtime_authority'],read(s['cap8_runtime_authority'],h)['retained_unit_environment'],*case_input_pins(case,h),case['input_inventory_authority'],case['continuous']['source_authority'],policy['authority'],s['original_capture_qualification'],s['fresh_capture_context_association'],
        *capture_input_pins(read(FIXED['capture_plan'],h),h),h.pin(Path(__file__).resolve()),*FIXED.values()]
    if mode=='canonical':argv=[FIXED['benchmark']['path'],'--cpu-facts','--checkpoint',checkpoint['path'],'--directory',job['output']]
    else:
        authority=h.pin(Path(canonical_closeout).resolve());closed=read(authority,h)
        require(closed['schema']=='robotron-original-canonical-CPU-profile-closeout-v1'and closed['status']=='PASS'
            and closed['checkpoint']==checkpoint and closed['actual_exit']==0,'Fresh same-policy canonical original closure required')
        prepared=read(h.pin(Path(canonical_closeout).parent/'prepared-NOT-LAUNCHED.json'),h)
        require(prepared['profile_selection']==sp and prepared['role']==role and prepared['mode']=='canonical'
            and prepared['source']==h.pin(Path(__file__).resolve()),'No old canonical profile adoption')
        job.update(driver=FIXED['frozen_driver'],package=old['source_package'],canonical_CPU_facts=closed['immutable_facts'])
        inputs += [authority,*[v for v in job.values()if isinstance(v,dict)]]
    for value in {v['path']:v for v in inputs}.values():h.checked(value)
    directory.mkdir(mode=0o700);jp=h.put(directory/'job.json',job)
    if mode=='frozen':argv=[job['driver']['path'],'--job',jp['path'],'--job-sha256',jp['sha256']]
    control=load('_physical192_profile_controller',FIXED['controller'])
    config=dict(unit='robotron-physical192-'+s['study_uuid']+'-'+role+'-'+mode+'-CPU-original01.service',output=str(directory/'execution-original01'),argv=['/usr/bin/env',*[k+'='+v for k,v in PRIVATE_ENV.items()],str(ROOT.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',*argv],properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],observation_s=240,pins=[control.pin(v['path'])for v in {v['path']:v for v in [jp,*inputs]}.values()])
    cp=h.put(directory/'controller-config.json',config);require(control.checked_config(cp['path'])==config,'Existing CPU controller ABI differs')
    return h.put(directory/'prepared-NOT-LAUNCHED.json',dict(mode=mode,role=role,job=jp,config=cp,profile_selection=sp,source=h.pin(Path(__file__).resolve()),controller=FIXED['controller'],Root_controller_argv=['/usr/bin/python3.12','-I','-B',FIXED['controller']['path'],'--execute','--config',cp['path'],'--expected-source-sha256',FIXED['controller']['sha256']],strict_existing_numerical_driver_unchanged=True,recorded_physical_engineering_qualified=True,fresh_runtime_or_resource_probe_performed=False,actual_physical_engineering=s['main_qualification'],scientific_launch_qualified=False,CPU_or_study_launched=False,quality_qualified=False,promotion=False))


def prepare_comparison_selection(path,sha,output,engineering_joint,engineering_sha):
    h,api=dependencies();s,sp,case=selection(path,sha,h);result,cpu=capture(h)
    joint_pin=h.pin(Path(engineering_joint).resolve());require(joint_pin['sha256']==engineering_sha,'Exact actual engineering joint selected')
    require(joint_pin==s['main_qualification'],'Comparison must use the same actual joint that gated fresh profiles')
    engineering_association(joint_pin,s,case,h)
    root=Path(s['profile_root']);adoptions={};closed_inputs=[]
    for role in ('reference','candidate'):
        for mode in ('canonical','frozen'):
            directory=root/(role+'-'+mode+'-CPU-original01')
            packet=read(h.pin(directory/'prepared-NOT-LAUNCHED.json'),h)
            require(packet['profile_selection']==sp and packet['role']==role and packet['mode']==mode
                and packet['source']==h.pin(Path(__file__).resolve()),'Every profile must be from this exact fresh physical selection/source')
            name='independent-original-canonical-CPU-closeout.json'if mode=='canonical'else'independent-original-profile-scope-closeout.json'
            cp=h.pin(directory/name);closed=read(cp,h)
            require(closed['status']=='PASS' and closed['actual_exit']==0
                and closed['all_six_descriptors_resources_argv_birth_unit_timer_cgroup_and_release_verified']is True
                and closed['preparer_source']==packet['source'],'Actual independently closed fresh original CPU required')
            job=read(packet['job'],h)
            require(job['checkpoint']['sha256']==(CANDIDATE if role=='candidate'else REFERENCE),'Profile policy binding differs')
            if mode=='frozen':
                ap=closed['profile_adoption'];adopted=read(ap,h)
                require(adopted['schema']=='robotron-frozen-profile-CPU-independent-adoption-v1'
                    and adopted['status']=='PASS' and adopted['original_job']==packet['job']
                    and adopted['actual_exit']==0 and adopted['original_scope_released']is True
                    and adopted['all_Q_bytes_and_actions_match']is True,'Fresh exact frozen adoption differs')
                adoptions[role]=ap
            closed_inputs.append(cp)
    output=Path(output).absolute();require(output.resolve()==output and not output.exists()and output.parent.is_dir(),'Fresh comparison metadata directory required')
    output.mkdir(mode=0o700)
    qualification=s['original_capture_qualification']
    selected=h.put(output/'Root-physical192-comparison-selection.json',dict(
        schema='robotron-root-current-eval-quiescence-fresh-comparison-selection-v5',status='ACTUAL_POST_MODE_CONTEXT_SELECTED',
        mode='CONTINUOUS_TRAIN155_EVAL37_ONCE',main_case=s['main_case'],candidate_selection_mode='FRESH_POST_MODE_CAPTURE',
        capture_root=str(Path(FIXED['capture_result']['path']).parent),capture_plan=FIXED['capture_plan'],capture_result=FIXED['capture_result'],
        capture_eligibility_overlay=FIXED['capture_eligibility_overlay'],
        fresh_capture_context_association=s['fresh_capture_context_association'],current_runtime_profiles=dict(main_source_authority=case['continuous']['source_authority'],
        reference_profile=adoptions['reference'],candidate_profile=adoptions['candidate']),source_family=FIXED['physical_family'],source_peer=FIXED['physical_peer'],
        fresh_profile_closeouts=closed_inputs,Root_profile_selection=sp,actual_physical_engineering=joint_pin,launch_qualified=False,quality_qualified=False))
    return h.put(output/'prepared-physical192-prerequisites-NOT-LAUNCH-QUALIFIED.json',dict(
        selection=selected,reference_profile=adoptions['reference'],candidate_profile=adoptions['candidate'],
        original_capture_qualification=qualification,fresh_capture_context_association=s['fresh_capture_context_association'],source=h.pin(Path(__file__).resolve()),
        actual_four_native_jobs=None,actual_metadata_CPU=None,actual_exact_job_guards=None,actual_review_precommit_CPU=None,
        scientific_launch_qualified=False,quality_qualified=False,CPU_or_scientific_job_launched=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--prepare-canonical',action='store_true');g.add_argument('--prepare-frozen',action='store_true');g.add_argument('--close',action='store_true');g.add_argument('--prepare-comparison-selection',action='store_true');g.add_argument('--qualify-capture',action='store_true')
    p.add_argument('--selection');p.add_argument('--selection-sha256');p.add_argument('--role',choices=('candidate','reference'));p.add_argument('--directory',type=Path);p.add_argument('--canonical-closeout',type=Path);p.add_argument('--engineering-joint',type=Path);p.add_argument('--engineering-joint-sha256');p.add_argument('--expected-source-sha256');a=p.parse_args()
    if not(a.prepare_canonical or a.prepare_frozen or a.close or a.prepare_comparison_selection or a.qualify_capture):print('SOURCE_ONLY_INERT_NO_READS_OR_ACTIONS');return
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.expected_source_sha256,'Exact selected constructor required')
    if a.qualify_capture:
        require(a.directory,'Fresh capture qualification output required')
        answer=qualify_capture(a.directory)
    elif a.close:
        h,api=dependencies();answer=api.close(a.directory)
    elif a.prepare_comparison_selection:
        require(a.selection and a.selection_sha256 and a.directory and a.engineering_joint and a.engineering_joint_sha256,'Exact selection/engineering joint and fresh metadata output required')
        answer=prepare_comparison_selection(a.selection,a.selection_sha256,a.directory,a.engineering_joint,a.engineering_joint_sha256)
    else:
        require(a.selection and a.selection_sha256 and a.role and a.directory,'Explicit actual Root selection/role/output required')
        require(bool(a.canonical_closeout)==bool(a.prepare_frozen),'Only frozen mode takes its actual canonical closeout')
        answer=prepare(a.selection,a.selection_sha256,a.role,a.directory,a.canonical_closeout)
    print(json.dumps(dict(prepared_or_closed=answer,CPU_or_scientific_job_launched=False,Root_only_controller_source=FIXED['controller'])),flush=True)

if __name__=='__main__':main()
