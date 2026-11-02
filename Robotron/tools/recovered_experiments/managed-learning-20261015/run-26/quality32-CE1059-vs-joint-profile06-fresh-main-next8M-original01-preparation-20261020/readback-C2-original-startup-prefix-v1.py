"""Passive original-C2 startup/policy prefixes; no score or cohort qualification."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
CAMPAIGN = GAME/'logs/managed-learning-20261015/quality-CE1059M-vs-joint-profile06-fresh-next8M-quality32-trial01-20261020'
OUTPUT = HERE/'C2-original-startup-prefixes'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid,
                nlink=info.st_nlink)


def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path), sha256=sha(raw), bytes=len(raw), identity=identity(path.stat()))


def archive(path, raw):
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o664)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o444)
    return pin(path)


def prefix(path, name, *, complete_lines=False):
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read()
        if complete_lines:
            raw = raw[:raw.rfind(b'\n')+1]
        stream.seek(0)
        assert stream.read(len(raw)) == raw
        after = os.fstat(stream.fileno())
        fields = ('st_dev', 'st_ino', 'st_uid', 'st_nlink', 'st_mode')
        assert all(getattr(before, key) == getattr(after, key) for key in fields)
    archived = archive(OUTPUT/name, raw)
    return raw, dict(original_path=str(path), observed_identity_before=identity(before),
                     observed_identity_after=identity(after), prefix_bytes=len(raw),
                     prefix_sha256=sha(raw), stable_prefix_reread=True, archive=archived)


def main():
    assert not OUTPUT.exists()
    OUTPUT.mkdir()
    reference_path = HERE/'R1-original32-ROM-startup-and-playing-prefix-readback.json'
    assert sha(reference_path.read_bytes()) == '9dc53b76b3ec393cd59aef4874bd7d72443b994d67ad134144f6e9ae34290915'
    reference = json.loads(reference_path.read_bytes())
    assert pin(Path(reference['ROM_binary']['path'])) == reference['ROM_binary']
    expected_chips = reference['original_actor_startup_prefixes'][0]['found_original_ROM_chips']
    aliases = reference['original_actor_startup_prefixes'][0]['installed_name_aliases']
    for entry in aliases:
        assert pin(Path(entry['installed_file']['path'])) == entry['installed_file']
    actors_path = HERE/'runtime-bindings/leg-births/leg4-actors.json'
    actors = json.loads(actors_path.read_bytes())
    assert set(actors) == {str(slot) for slot in range(4096,4128)}
    startup = []
    for slot in range(4096,4128):
        raw, captured = prefix(CAMPAIGN/f'04-candidate/actors/{slot}/console.log', f'actor-{slot}.bin')
        text = raw.decode()
        found = [dict(zip(('name','CRC32','SHA1'), values)) for values in re.findall(
            r'(?m)^(\S+) WRONG CHECKSUMS:\n[^\n]*\n\s+FOUND: CRC\(([0-9a-f]{8})\) SHA1\(([0-9a-f]{40})\)', text)]
        assert found == expected_chips
        assert text.count('[PATCH] RRCHRIS runtime ROM patch disabled.') == 1
        assert 'Robotron eval override: EVAL (greedy, wave-1)' in text
        assert '[DIFFICULTY] GA1 poked to 5' in text
        owner = actors[str(slot)]
        assert re.search(r'\[robotron-socket-wait\] pid='+str(owner['pid'])+r' fd=\d+ port=9999 interval_us=1000', text)
        assert '[SOCKET ACTION TIMEOUT]' not in text and 'Lua error' not in text
        assert not re.search(r'\bFATAL\b|Aborted', text)
        startup.append(dict(slot=slot, original_actor=owner, prefix=captured,
                            six_variant_checksums_match=True, RRCHRIS_disabled=True))
    raw, lives = prefix(CAMPAIGN/'04-candidate/journal/lives.jsonl', 'lives-complete-line-prefix.jsonl', complete_lines=True)
    rows = [json.loads(line) for line in raw.splitlines()]
    assert rows
    positive = set()
    for row in rows:
        assert row['client_slot'] in range(4096,4128) and row['eval_only'] is True
        context = row['context']
        assert context['epsilon'] == context['expert_ratio'] == 0 and context['difficulty'] == 5
        assert context['learner_frames'] == 1597432474
        assert context['training_steps'] == 6585181 and context['optimized_samples'] == 25397106688
        if row['playable_frames'] > 0:
            positive.add(row['client_slot'])
    assert positive == set(range(4096,4128))
    console_raw, console = prefix(CAMPAIGN/'04-candidate.console.log', 'evaluator-console-prefix.bin')
    assert not re.search(rb'Traceback|RuntimeError|CUDA out of memory', console_raw)
    report = dict(schema='robotron-profile06-original-C2-startup-policy-prefix-v1',
        observed_unix_s=time.time(), source=pin(Path(__file__)), reference_startup_proof=pin(reference_path),
        original_actor_registry=pin(actors_path), actor_prefixes=startup,
        six_variant_checksums_match_installed_ROM_all32=True, RRCHRIS_disabled_all32=True,
        life_journal=lives, life_rows=len(rows), all32_positive_playable_life_frames=True,
        frozen_epsilon0_expert0_difficulty5_and_candidate_clocks_all_rows=True,
        known_game_start_counts=dict(Counter(str(row['known_game_start']) for row in rows)),
        evaluator_console=console, prefix_runtime_error_markers_found=False,
        quality_qualified=False, promotion=False, full_closed_journals_and_runtime_validation_still_required=True,
        source_or_runtime_changed=False)
    result = archive(HERE/'C2-original32-ROM-startup-and-playing-prefix-readback.json',
        (json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(dict(readback=result, life_rows=len(rows),
                         known_game_start_counts=report['known_game_start_counts'],
                         all32_playing=True, quality_qualified=False)))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', action='store_true')
    args = parser.parse_args()
    if args.observe:
        main()
