"""Generate future observer/reviewer sources; never edit the failed campaign."""
import argparse
import ast
import hashlib
import os
from pathlib import Path

HEALTH_SHA = 'f5f95732dd0577c2eb61c2fbcc25b57df8f22ffef5d7e35f062190d31c570a5c'
REVIEW_SHA = '9403715e79fa506f7d0eda362c30877e2ad8382ebaabacc96a0b6fef1dd349bd'
OWNED_SHA = 'c10b6a2e752b61aa345e648c26ee9bf7b82a711ab73f1351138ee31dcdb2a879'
METHOD = '''    def pending_metadata(self,index,phase,fleet,connections,*,now):
        try:
            try:
                pending=validate_metadata(fleet,connections,self.expected,self.membership,self.roles,now=now)
                return dict(pending_slots=pending,overlaps={},census_qualified=False)
            except ValueError as error:
                if str(error)!='Duplicate/foreign live Main connection':raise
            return self.owned_overlap.capture_pending(fleet,connections,self.expected,self.membership,self.roles,
                now=now,strict_validator=validate_metadata,read_pin=self.read,
                physical_actor=self.physical.actor,tcp_binding=self.physical.tcp_binding)
        except Exception as error:
            self.h.put(self.output/f'{index:05d}-v6-{phase}-owned-metadata-rejected.json',dict(
                schema='robotron-current-v6-rejected-owned-metadata-v1',phase=phase,
                sample_index=index,observed_unix_s=now,error=repr(error),
                fleet=fleet,connections=connections,expected=self.expected,
                membership=self.membership,roles=self.roles,accepted=False,quality_qualified=False))
            raise

'''


def replace_once(text, old, new, changes):
    assert text.count(old) == 1, old
    changes.append((old, new))
    return text.replace(old, new)


def observer(raw):
    assert hashlib.sha256(raw).hexdigest() == HEALTH_SHA
    text, changes = raw.decode(), []
    anchor = "        self.supervisor=load('_future_v6_original_supervisor_definitions',self.expected['supervisor']['source'],h)"
    text = replace_once(text, anchor, anchor +
        f"\n        require(job['owned_TRAIN_overlap_source']['sha256']=='{OWNED_SHA}','Exact future owned-TRAIN overlap helper required')" +
        "\n        self.owned_overlap=load('_future_owned_TRAIN_overlap',job['owned_TRAIN_overlap_source'],h)", changes)
    text = replace_once(text, '    def observe(self):', METHOD + '    def observe(self):', changes)
    text = replace_once(text,
        "        pending=retained_metadata_validation(self.h,self.output,index,'before',before,connections,self.expected,self.membership,self.roles,now=now)",
        "        metadata_before=self.pending_metadata(index,'before',before,connections,now=now)\n        pending=metadata_before['pending_slots']", changes)
    text = replace_once(text,
        "        after_connections=self.get_connections();after=self.status();after_pending=retained_metadata_validation(self.h,self.output,index,'after',after,after_connections,\n            self.expected,self.membership,self.roles,now=time.time())",
        "        after_connections=self.get_connections();after=self.status()\n        metadata_after=self.pending_metadata(index,'after',after,after_connections,now=time.time())\n        after_pending=metadata_after['pending_slots']", changes)
    text = replace_once(text,
        '            self.pending_since=None\n        # Keep complete physical environments',
        "            self.pending_since=None\n            for slot,event in bindings.items():\n                self.owned_overlap.validate_binding_cleanup(before,slot,event,read_pin=self.read,\n                    closed_connection=self.supervisor.closed_connection)\n        # Keep complete physical environments", changes)
    text = replace_once(text,
        "dict(schema='robotron-current-v6-bounded-physical-observation-v1',\n            started_monotonic_s=begin,",
        "dict(schema='robotron-current-v6-owned-overlap-observation-v2',\n            owned_TRAIN_metadata_before=metadata_before,owned_TRAIN_metadata_after=metadata_after,\n            started_monotonic_s=begin,", changes)
    restored = text
    for old, new in reversed(changes):
        restored = restored.replace(new, old, 1)
    assert restored.encode() == raw
    before, after = ast.parse(raw), ast.parse(text)
    for name in ('validate_metadata', 'validate_join', 'stable_projection', 'retained_metadata_validation'):
        a = next(n for n in before.body if getattr(n, 'name', None) == name)
        b = next(n for n in after.body if getattr(n, 'name', None) == name)
        assert ast.dump(a) == ast.dump(b)
    compile(text, '<future-owned-overlap-observer>', 'exec')
    return text.encode()


def reviewer(raw):
    assert hashlib.sha256(raw).hexdigest() == REVIEW_SHA
    text, changes = raw.decode(), []
    text = replace_once(text,
        "        and family['current_Main_health']==job['current_v6_health_source']",
        "        and family['current_Main_health']==job['current_v6_health_source']\n        and family['current_Main_owned_overlap']==job['owned_TRAIN_overlap_source']\n        and job['owned_TRAIN_overlap_source']['sha256']=='" + OWNED_SHA + "'", changes)
    anchor = "    source=load('_eng_review_actual_v6_health',h.checked(job['current_v6_health_source']))"
    text = replace_once(text, anchor, anchor +
        "\n    owned=load('_eng_review_owned_TRAIN_overlap',h.checked(job['owned_TRAIN_overlap_source']))", changes)
    text = replace_once(text,
        "        before_pending=source.validate_metadata(before,connections,expected_fleet,membership,roles,now=now)\n        after_pending=source.validate_metadata(raw['fleet_after'],raw['connections_after'],expected_fleet,membership,roles,\n            now=max(raw['fleet_after']['updated_unix_s'],raw['connections_after']['observed_unix_s']))",
        "        require(raw['schema']=='robotron-current-v6-owned-overlap-observation-v2','Exact owned-overlap raw schema required')\n        before_metadata=owned.replay_pending(before,connections,expected_fleet,membership,roles,\n            raw['owned_TRAIN_metadata_before'],now=now,strict_validator=source.validate_metadata,read_pin=read)\n        after_metadata=owned.replay_pending(raw['fleet_after'],raw['connections_after'],expected_fleet,membership,roles,\n            raw['owned_TRAIN_metadata_after'],now=max(raw['fleet_after']['updated_unix_s'],raw['connections_after']['observed_unix_s']),\n            strict_validator=source.validate_metadata,read_pin=read)\n        before_pending=before_metadata['pending_slots'];after_pending=after_metadata['pending_slots']", changes)
    text = replace_once(text,
        "            require(joined==raw['joined']==sample['current_v6_join'],'Original physical result differs');accepted+=1",
        "            require(joined==raw['joined']==sample['current_v6_join'],'Original physical result differs')\n            for key,event in raw['bindings'].items():\n                owned.validate_binding_cleanup(before,int(key),event,read_pin=read,\n                    closed_connection=original_supervisor.closed_connection)\n            accepted+=1", changes)
    restored = text
    for old, new in reversed(changes):
        restored = restored.replace(new, old, 1)
    assert restored.encode() == raw
    # This is an inert template until a fresh pair is bound. It cannot review or
    # rescue the failed b231-versus1c case using a replacement reviewer.
    import re
    matches = re.findall(r"PAIR_SHA='([0-9a-f]{64})'", text)
    assert len(matches) == 1
    text = text.replace("PAIR_SHA='" + matches[0] + "'", "PAIR_SHA='" + '0'*64 + "'", 1)
    compile(text, '<future-owned-overlap-reviewer-unbound>', 'exec')
    return text.encode()


def put(path, data):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('health-parent', 'review-parent', 'owned-source', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    owned = args.owned_source.read_bytes()
    assert hashlib.sha256(owned).hexdigest() == OWNED_SHA
    args.output.mkdir(mode=0o700)
    put(args.output / 'owned_train_connection_overlap_v2.py', owned)
    put(args.output / 'current_v6_owned_overlap_health_v4.py', observer(args.health_parent.read_bytes()))
    put(args.output / 'review_owned_overlap_fullgame_UNBOUND_v1.py', reviewer(args.review_parent.read_bytes()))


if __name__ == '__main__':
    main()
