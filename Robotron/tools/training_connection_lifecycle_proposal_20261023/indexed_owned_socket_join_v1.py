"""Unselected indexed equivalent of the pinned v1 full192 owned-socket join.

Only lookup order changes: preserve exact rows, ownership, count assertions,
reverse-pair cardinality and inode uniqueness. All other primitives are delegated
unchanged. No I/O, module-import actions, normalization or health exception.
"""


def full_join(original,table,view):
    owners={};by_slot={slot:[]for slot in view['actors']}
    for slot,actor in view['actors'].items():
        for inode in set(actor['socket_fds'].values()):owners.setdefault(inode,[]).append(slot)
    server=[];reverse={};server_inodes=set(view['trainer']['socket_fds'].values())
    for row in table:
        if row['state']!='01':continue
        if int(row['peer'][9:],16)==9998:
            for slot in owners.get(row['inode'],()):by_slot[slot].append(row)
        if int(row['local'][9:],16)==9998:
            server.append(row)
            if row['inode']in server_inodes:reverse.setdefault((row['local'],row['peer']),[]).append(row)
    original.require(len(server)==192 and all(len(value)==1 for value in by_slot.values()),
                     'Before/after must have exactly192 owned socket pairs')
    joined={}
    for slot,connections in by_slot.items():
        client=connections[0];peers=reverse.get((client['peer'],client['local']),[])
        original.require(len(peers)==1,'Trainer reverse socket ownership missing')
        joined[slot]=dict(client=client,server=peers[0])
    original.require(len({entry['client']['inode']for entry in joined.values()})==192,
                     'Actor socket inode reused across slots')
    return joined


def bind(original):
    class Indexed:
        def __getattr__(self,name):return getattr(original,name)
        def full_join(self,table,view):return full_join(original,table,view)
    return Indexed()
