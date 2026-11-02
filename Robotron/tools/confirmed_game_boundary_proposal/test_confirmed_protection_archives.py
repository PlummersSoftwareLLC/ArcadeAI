"""Real archived controller ABI joins; no future-campaign review/publication."""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import protect_confirmed_winner_reviewed2 as protect


class ActualArchiveTests(unittest.TestCase):
    def setUp(self):
        base=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
        self.prep=base/'post-confirmed-scoring-next8M-original01-root-preparation-20261018'
        self.closure=json.loads((self.prep/'native-terminal-archive/root-original-result-and-owned-release.json').read_bytes())
        self.owner=json.loads((self.prep/'root-original-live-owner.json').read_bytes())
        self.entry=self.closure['native_archives'][0]['stdout']

    def test_actual_short_controller_and_full_snapshot_pins_read_identical_bytes(self):
        expected=Path(self.entry['path']).read_bytes()
        self.assertEqual(protect.read_pin(self.entry,as_json=False),expected)
        self.assertEqual(protect.read_pin(protect.pin(self.entry['path']),as_json=False),expected)

    def test_actual_original_exit0_and_owned_release_archive_validate(self):
        evidence={}
        protect.original_terminal_archive(self.closure,self.owner,evidence)
        self.assertEqual(evidence,{self.entry['path']:self.entry['sha256']})

    def test_selected_publication_body_is_exact_existing_reviewed_algorithm(self):
        original=(HERE/'quality_integration_reviewed4/Robotron/tools/protect_quality_winner.py').read_text()
        body=original[original.index('def _fsync_directory'):original.index('def main(')]
        self.assertIn(body,Path(protect.__file__).read_text())

    def test_unrecognized_partial_identity_or_changed_inode_hash_and_mode_rejected(self):
        for change in ('omit_inode','hash','inode','mode','owner'):
            entry=copy.deepcopy(self.entry)
            if change=='omit_inode':entry['identity'].pop('inode')
            if change=='hash':entry['sha256']='0'*64
            if change=='inode':entry['identity']['inode']+=1
            if change=='mode':entry['identity']['mode']='0o664'
            if change=='owner':entry['identity']['uid']+=1
            with self.subTest(change=change),self.assertRaises(ValueError):
                protect.read_pin(entry,as_json=False)


if __name__=='__main__':unittest.main()
