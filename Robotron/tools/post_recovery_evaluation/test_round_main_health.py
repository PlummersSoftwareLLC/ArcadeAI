import copy
import os
import unittest

from .round_main_health import validate


def fixture():
    def process(pid, slot=None):
        env = {} if slot is None else dict(ROBOTRON_CLIENT_SLOT=str(slot),
            ROBOTRON_ACTOR_ROUND='4', ROBOTRON_SOCKET_ADDRESS='dell:9998',
            ROBOTRON_EVAL_MODE='2', ROBOTRON_RETIRE_AFTER_GAME='1',
            ROBOTRON_PREVIEW_CLIENT='1' if slot == 0 else '0')
        return dict(pid=pid, starttime_ticks=pid+100, parent_pid=2,
            cgroup='/fleet', command=['/usr/games/mame'], environment=env,
            affinity=[0], uids=[os.getuid()]*4, executable=dict(path='/usr/games/mame'), state='S')
    owners = {role: dict(unit=role, invocation=role, process=process(pid))
              for role, pid in [('trainer', 1), ('fleet', 2)]}
    lineage = dict(process_id=1, instance_monotonic_ns=10, epoch=1, epoch_reason='restore')
    case = dict(owners=owners, initial_round=4, slot_eval={str(x): False for x in range(192)},
        actor_environment=dict(ROBOTRON_SOCKET_ADDRESS='dell:9998',ROBOTRON_RETIRE_AFTER_GAME='1'),
        actor_command=['/usr/games/mame'],actor_affinity=[0],actor_executable=dict(path='/usr/games/mame'),
        exposure={key:dict(lineage) for key in ['optimizer','replay']})
    results = {str(x): dict(pid=1000+x) for x in range(2,192)}
    sample = dict(owners=copy.deepcopy(owners), monotonic_s=1, unix_s=100,
        actors={str(x):process(1000+x,x)for x in [0,1]},results=results,
        receipt_hashes={slot:slot for slot in results},
        status=dict(total=192,round=4,completed=190,retired=190,active=2),
        api=dict(client_count=2,client_rows=[dict(client_slot=x)for x in [0,1]],
            training_enabled=True,measurement_active=False,lr=3.125e-6,ts=100,pipeline_snapshot_age_s=0,
            training_steps=10,learner_frame_count=10,optimized_samples=10,frame_count=10,
            host_pipeline=dict(learning_exposure={key:dict(lineage,available=True)
                                                for key in ['optimizer','replay']})))
    return case, sample


def retire(sample, slot='0', frozen=False):
    actor = sample['actors'][slot]
    sample['results'][slot] = dict(pid=actor['pid'])
    sample['receipt_hashes'][slot] = slot
    sample['status'].update(completed=191,retired=191,active=1)
    if frozen:
        actor['state'] = 'T'
    else:
        del sample['actors'][slot]
        sample['api']['client_rows'] = [dict(client_slot=1)]
        sample['api']['client_count'] = 1


class RoundMainHealthTests(unittest.TestCase):
    def test_durable_retirement_accepted_without_refilling_slot(self):
        case, original = fixture()
        validate(case, original)
        current = copy.deepcopy(original);current['monotonic_s'] = 2
        retire(current)
        validate(case,current,previous=original)

    def test_disappearance_without_score_or_same_round_respawn_rejected(self):
        for kind in ['missing','replaced','completed_still_running']:
            case, original = fixture();current = copy.deepcopy(original);current['monotonic_s'] = 2
            if kind == 'missing':del current['actors']['0']
            elif kind == 'replaced':current['actors']['0']['pid'] += 100
            else:retire(current,frozen=True);current['actors']['0']['state']='S'
            with self.assertRaises(ValueError):validate(case,current,previous=original)

    def test_frozen_actor_requires_durable_score(self):
        case, original = fixture();current=copy.deepcopy(original);current['monotonic_s']=2
        retire(current,frozen=True);validate(case,current,previous=original)
        del current['results']['0']
        with self.assertRaises(ValueError):validate(case,current,previous=original)

    def test_unknown_API_client_changed_role_and_lineage_rejected(self):
        for kind in ['guest','role','lineage','recipe']:
            case,current=fixture()
            if kind=='guest':current['api']['client_rows'][0]['client_slot']=191
            elif kind=='role':current['actors']['0']['environment']['ROBOTRON_EVAL_MODE']='1'
            elif kind=='lineage':current['api']['host_pipeline']['learning_exposure']['replay']['epoch']=2
            else:current['owners']['trainer']['process']['environment']['DQN_BATCH_SIZE']='2048'
            with self.assertRaises(ValueError):validate(case,current)

    def test_round_turnover_needs_all192_scores_and_stopped_old_births(self):
        case,original=fixture();current=copy.deepcopy(original);current['monotonic_s']=2
        closed={str(x):dict(pid=1000+x)for x in range(192)}
        current['previous_complete']=dict(results=closed,receipts={slot:slot for slot in closed},
            summary=dict(complete=True,completed=192,retired=192,updated_unix_s=101))
        current['started']=dict(started_unix_s=102);current['status']['round']=5
        for actor in current['actors'].values():
            actor['pid']+=10000;actor['starttime_ticks']+=10000
            actor['environment']['ROBOTRON_ACTOR_ROUND']='5'
        validate(case,current,previous=original)
        for kind in ['missing_score','early_start','old_birth']:
            bad=copy.deepcopy(current)
            if kind=='missing_score':del bad['previous_complete']['results']['0']
            elif kind=='early_start':bad['started']['started_unix_s']=100
            else:
                bad['actors']['0']['pid']=original['actors']['0']['pid']
                bad['actors']['0']['starttime_ticks']=original['actors']['0']['starttime_ticks']
            with self.assertRaises(ValueError):validate(case,bad,previous=original)

    def test_changed_receipt_long_observation_gap_and_clock_rollback_rejected(self):
        for kind in ['receipt','gap','clock']:
            case,original=fixture();current=copy.deepcopy(original);current['monotonic_s']=2
            if kind=='receipt':current['receipt_hashes']['2']='changed'
            elif kind=='gap':current['monotonic_s']=32
            else:current['api']['training_steps']=9
            with self.assertRaises(ValueError):validate(case,current,previous=original)


if __name__=='__main__':
    unittest.main()
