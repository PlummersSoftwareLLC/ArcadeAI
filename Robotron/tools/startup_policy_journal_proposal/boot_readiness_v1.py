"""Raw boot/coin readiness, derived from the two original ROM diagnostics.

This prevents consuming the one START authority on RAM-test bytes. It does not
prove a game start: the separate accepted gate, setup, initialization, loaded
policy and prospective journal transaction are still required afterwards.
"""
import copy


def boot_readiness(rows,meta):
    def require(value,message):
        if not value:raise ValueError(message)
    expected=dict(status=243,score_hex='00000000',wave=0,reserves=0,player_count=2,
                  current_player=0,credit=1,first_play_sequence=-1,mode='gated',nonce='0'*64)
    if not all(type(meta.get(k))is type(v)and meta[k]==v for k,v in expected.items()):return None
    require(rows and rows[-1]['kind']=='snapshot'and rows[-1]['event']==meta['event']
            and rows[-1]['sequence']==meta['sequence']and all(rows[-1][k]==meta[k]for k in expected),
            'Ready snapshot must match the original wire frame')
    subject={k:meta[k]for k in ('session','connection','slot')}
    require(all(all(type(r.get(k))is type(v)and r[k]==v for k,v in subject.items())for r in rows),
            'Original readiness subject changed')
    writes=[r for r in rows if r['kind']=='ROM_write']
    def sites(pc):return [r for r in writes if r['address']==0x9859 and r['instruction_pc']==pc]
    clears,initializations,credits=sites(0xd137),sites(0xd184),sites(0x79c4)
    if not(len(clears)==len(initializations)==len(credits)==1):return None
    clear,initialized,credit=clears[0],initializations[0],credits[0]
    for row,values in [(clear,dict(data=0,instruction_hex='6f80')),
                       (initialized,dict(data=255,instruction_hex='0359')),
                       (credit,dict(data=243,a=243,instruction_hex='9759',credit=1))]:
        require(all(type(row.get(k))is type(v)and row[k]==v for k,v in
                    dict(values,dp=0x98,bank_entry=1,mask=255,last_start=0,
                         last_apply_ok=True,last_socket_ok=True).items()),
                'Actual boot/coin ROM write differs')
        require(row.get('nonce')=='0'*64,'Readiness must precede original START authorization')
    coins=[r for r in rows if r['kind']=='input_applied'
           and initialized['event']<r['event']<credit['event']and r.get('coin')==1]
    if not coins:return None
    require(clear['event']<initialized['event']<coins[0]['event']<credit['event']<meta['event']
            and clear['sequence']<=initialized['sequence']<=coins[0]['sequence']
            <=credit['sequence']<meta['sequence'],'Actual boot/coin order differs')
    for coin in coins:
        require(type(coin.get('coin'))is int and coin['coin']==1 and type(coin.get('start'))is int
                and coin['start']==0 and coin.get('socket_ok')is coin.get('apply_ok')is True
                and coin.get('debug_bypass')is coin.get('held_start_before_response')is False
                and coin.get('nonce')=='0'*64,'Actual original coin application differs')
        # Match the exact selected48-byte response; coin1 without a successful
        # original exchange is not evidence that a physical input was applied.
        raw=bytes.fromhex(coin['response_hex'])
        require(len(raw)==48 and raw[:4]==b'RSP1'and int.from_bytes(raw[4:8],'big')==coin['sequence']
                and raw[8:10]==b'\0\1'and raw[10:42]==bytes(32),
                'Actual original coin response differs')
    return copy.deepcopy(dict(schema='robotron-raw-boot-coin-readiness-v1',subject=subject,
        clear=clear,initialized=initialized,coin_applications=coins,accepted_coin_STATUS=credit,
        ready_snapshot_event=meta['event'],ready_sequence=meta['sequence'],game_start_proven=False))
