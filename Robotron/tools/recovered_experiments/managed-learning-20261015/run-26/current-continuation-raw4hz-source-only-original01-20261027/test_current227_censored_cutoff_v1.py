"""One NEW bounded pure-source cutoff test; no live API or model access."""
import ast
import copy
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parent/'stop-sources/current227_linux_stop_v1.py'


def require(value, message):
    if not value: raise RuntimeError(message)


class Tests(unittest.TestCase):
    def test_exact_192_unwrapped_scores_censored_denominator_and_identity_guards(self):
        tree = ast.parse(SOURCE.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'summarize_restart_censored_live_games')
        scope = dict(require=require)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(SOURCE),'exec'),scope)
        summarize = scope[fn.name]
        rows = [dict(client_slot=i, client_id=1000+i, eval=i<37, score=(i+1)*2311) for i in range(192)]
        high = {4:100_000_001, 49:200_000_123, 163:350_000_999, 191:1_000_000_011}
        for slot, score in high.items(): rows[slot]['score'] = score
        originals = {r['client_slot']:dict(cid=r['client_id'], evaluation=r['eval'])for r in rows}
        api = dict(ts=123.5,client_rows=[*rows,dict(client_slot=8191,client_id=9999,eval=True,score=0)])
        main = dict(owner={'pid':3615927,'starttime_ticks':78856521},experiment='CPU-fixture-exact-current-recipe',actors={})
        rawpin = dict(path='CPU-fixture-no-read',sha256='a'*64)
        result = summarize(api,originals,rawpin,main)
        scores = sorted(r['score'] for r in rows)
        self.assertEqual(result['n_scored'],192);self.assertEqual(result['n_restart_censored'],192)
        self.assertEqual(result['n_natural_completed_counted'],0)
        self.assertIs(type(result['score_sum']),int);self.assertEqual(result['score_sum'],sum(scores))
        self.assertEqual(result['mean_score'],sum(scores)/192)
        self.assertEqual(result['median_twice'],scores[95]+scores[96])
        self.assertEqual(result['over100M_slots'],list(high))
        self.assertEqual({r['client_slot']:r['score_at_snapshot']for r in result['rows']if r['client_slot']in high},high)
        self.assertTrue(all(r['status']=='restart_censored_snapshot'and r['natural_completion_confirmed_by_this_capture']is False
                            for r in result['rows']))
        self.assertTrue(result['API_does_not_export_game_UID_or_last_score_accept_time'])
        self.assertEqual(result['raw_API'],rawpin)
        for damage in ('duplicateCID','duplicateSlot','role','fractionalScore','booleanScore','negativeScore'):
            changed=copy.deepcopy(api)
            if damage=='duplicateCID':changed['client_rows'][0]['client_id']=changed['client_rows'][1]['client_id']
            if damage=='duplicateSlot':changed['client_rows'][0]['client_slot']=1
            if damage=='role':changed['client_rows'][0]['eval']=False
            if damage=='fractionalScore':changed['client_rows'][0]['score']=12.5
            if damage=='booleanScore':changed['client_rows'][0]['score']=True
            if damage=='negativeScore':changed['client_rows'][0]['score']=-1
            with self.assertRaises(RuntimeError,msg=damage):summarize(changed,originals,rawpin,main)


if __name__=='__main__':unittest.main()
