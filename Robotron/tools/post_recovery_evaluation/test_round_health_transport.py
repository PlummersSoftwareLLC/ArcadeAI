import copy
import os
import socket
import unittest

from . import round_health_transport as transport
from .test_round_main_health import fixture, retire


HEADER = 'sl local_address rem_address st tx_queue rx_queue tr uid timeout inode\n'


def line(local, remote, inode, state='01', uid=None):
    def address(value):
        host, port = value
        return socket.inet_aton(host)[::-1].hex().upper() + ':%04X' % port
    return '0: %s %s %s 0:0 00:0 0 %d 0 %s\n' % (
        address(local), address(remote), state, os.getuid() if uid is None else uid, inode)


def joined_fixture():
    case, sample = fixture()
    sample['api'].update(epsilon=.1, expert_ratio=.1)
    for row in sample['api']['client_rows']:
        row['eval'] = False
    exposure = sample['api']['host_pipeline']['learning_exposure']
    exposure['optimizer'].update(enabled=True, total=dict(
        attempts_started=10, outcomes_recorded=10, applied=9, amp_skipped=1, unavailable=0))
    exposure['replay'].update(enabled=True, accepted_total=2, accepted_learner_total=2,
        accepted_by_source_total=dict(dqn=1, epsilon=1, expert=0, eval=0, unattributed=0))
    raw = HEADER + line(('0.0.0.0', 9998), ('0.0.0.0', 0), '1', state='0A')
    for slot in (0, 1):
        actor, server = ('192.168.1.131', 30000+slot), ('192.168.1.131', 9998)
        raw += line(actor, server, str(10+slot)) + line(server, actor, str(20+slot))
    sample['transport'] = dict(raw_tables=dict(tcp=raw, tcp6=HEADER),
        socket_inodes={'trainer': ['1', '20', '21'], '0': ['10'], '1': ['11']},
        namespaces={'trainer': 'net:[1]', '0': 'net:[1]', '1': 'net:[1]'}, collector_namespace='net:[1]')
    return case, sample


class RoundTransportTests(unittest.TestCase):
    def test_kernel_endpoint_parser_and_valid_owned_census(self):
        case, sample = joined_fixture()
        rows = transport.tcp_rows(sample['transport']['raw_tables']['tcp'])
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[1]['local'], ['192.168.1.131', 30000])
        transport.validate(case, sample)

    def test_foreign_peer_missing_fd_wrong_uid_and_namespace_rejected(self):
        for mutation in ('foreign_peer', 'listener', 'actor_fd', 'uid', 'namespace', 'extra_actor_fd'):
            with self.subTest(mutation=mutation):
                case, sample = joined_fixture()
                evidence = sample['transport']
                if mutation == 'foreign_peer':
                    evidence['raw_tables']['tcp'] += line(('192.168.1.131', 9998), ('192.168.1.13', 45000), '50')
                    evidence['socket_inodes']['trainer'].append('50')
                elif mutation == 'listener':
                    evidence['socket_inodes']['trainer'].remove('1')
                elif mutation == 'actor_fd':
                    evidence['socket_inodes']['0'] = []
                elif mutation == 'uid':
                    evidence['raw_tables']['tcp'] += line(('192.168.1.131', 9998), ('192.168.1.13', 45000), '50', uid=os.getuid()+1)
                elif mutation == 'namespace':
                    evidence['namespaces']['0'] = 'net:[2]'
                else:
                    evidence['socket_inodes']['0'].append('11')
                with self.assertRaises(ValueError):
                    transport.validate(case, sample)

    def test_durable_frozen_retirement_keeps_owned_socket_valid(self):
        case, previous = joined_fixture()
        current = copy.deepcopy(previous)
        current['monotonic_s'] = 2
        retire(current, frozen=True)
        transport.validate(case, current, previous=previous)
        current['actors']['0']['state'] = 'S'
        with self.assertRaises(ValueError):
            transport.validate(case, current, previous=previous)

    def test_durable_exit_requires_corresponding_socket_departure(self):
        case, previous = joined_fixture()
        current = copy.deepcopy(previous)
        current['monotonic_s'] = 2
        retire(current)
        current['api']['client_rows'][0]['eval'] = False
        del current['transport']['socket_inodes']['0']
        del current['transport']['namespaces']['0']
        with self.assertRaises(ValueError):
            transport.validate(case, current, previous=previous)
        current['transport']['raw_tables']['tcp'] = HEADER + ''.join(
            raw for raw in previous['transport']['raw_tables']['tcp'].splitlines(keepends=True)[1:]
            if raw.split()[9] not in ('10', '20'))
        transport.validate(case, current, previous=previous)

    def test_changed_live_controls_role_and_exposure_rejected(self):
        for mutation in ('epsilon', 'expert', 'role', 'disabled', 'pending', 'unavailable', 'attribution'):
            with self.subTest(mutation=mutation):
                case, sample = joined_fixture()
                api = sample['api']
                exposure = api['host_pipeline']['learning_exposure']
                if mutation == 'epsilon':
                    api['epsilon'] = 0
                elif mutation == 'expert':
                    api['expert_ratio'] = 0
                elif mutation == 'role':
                    api['client_rows'][0]['eval'] = True
                elif mutation == 'disabled':
                    exposure['replay']['enabled'] = False
                elif mutation == 'pending':
                    exposure['optimizer']['total']['attempts_started'] += 1
                elif mutation == 'unavailable':
                    exposure['optimizer']['total']['unavailable'] = 1
                else:
                    exposure['replay']['accepted_learner_total'] += 1
                with self.assertRaises(ValueError):
                    transport.validate(case, sample)

    def test_balanced_exposure_rollback_rejected(self):
        case, previous = joined_fixture()
        current = copy.deepcopy(previous)
        current['monotonic_s'] = 2
        old_replay = previous['api']['host_pipeline']['learning_exposure']['replay']
        old_replay['accepted_total'] = old_replay['accepted_learner_total'] = 3
        old_replay['accepted_by_source_total']['dqn'] = 2
        with self.assertRaisesRegex(ValueError, 'rolled back'):
            transport.validate(case, current, previous=previous)


if __name__ == '__main__':
    unittest.main()
