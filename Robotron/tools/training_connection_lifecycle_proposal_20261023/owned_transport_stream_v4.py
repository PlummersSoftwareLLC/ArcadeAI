"""Pure unselected complete stream with immutable accepted-baseline parse caching.

Preserves original raw API/TCP/log/FD evidence and strict192 actor ownership.
Every exception requires a completed <=2s before/after window. The two kinds
share one four-leg frequency/time budget. Caller-authenticated raw replay and
all physical/source/recipe/pipeline/bank/autosave checks remain mandatory.
"""
import copy

SCHEMA='robotron-owned-transport-stream-summary-v3'
LIMITS=dict(max_case_groups=8192,max_case_exception_groups=1024,max_case_charged_s=600.)


def closed_budget(p,cap,proc,groups):
    p.require(type(groups)is list and len(groups)<=LIMITS['max_case_groups'],'Whole-case transport group budget exceeded')
    cap_groups=[];proc_groups=[];previous_end=None
    for group in groups:
        if group['schema']==cap.SCHEMA:cap_groups.append(group)
        elif group['schema']==proc.SCHEMA:proc_groups.append(group)
        else:raise ValueError('Unknown source-bound transport proof schema')
        p.require(previous_end is None or group['begin_unix_s']>=previous_end,
                  'Mixed transport evidence windows overlap or regress')
        previous_end=group['end_unix_s']
    caps=cap.closed_budget(p,cap_groups);repeats=proc.closed_budget(p,proc_groups)
    exceptions=caps['overlap_groups']+repeats['events']
    charged=caps['total_overlap_charged_s']+repeats['total_charged_s']
    p.require(exceptions<=LIMITS['max_case_exception_groups']and charged<=LIMITS['max_case_charged_s'],
              'Shared four-leg transport exception count/time budget exceeded')
    return dict(groups=len(groups),normal_reconnects=caps['normal_reconnects'],
        cap_overlap_groups=caps['overlap_groups'],proc_repeat_groups=repeats['events'],
        total_exception_groups=exceptions,total_charged_s=charged,all_closed=True,
        all_nontransport_main_checks_still_required=True,quality_qualified=False)


class Stream:
    """One unfiltered original stream. A rejection/unfinished close is sticky."""
    def __init__(self,p,cap,proc,binding,cursors,lua_sha,prior_groups=()):
        p.require(lua_sha==p.LUA_SHA and set(cursors)==p.SLOTS,'Exact source-bound registry/cursors required')
        self.p=p;self.cap=cap;self.proc=proc;self.binding=copy.deepcopy(binding)
        self.cursors=copy.deepcopy(cursors);self.lua_sha=lua_sha;self.groups=copy.deepcopy(list(prior_groups))
        closed_budget(p,cap,proc,self.groups);self.prior_group_count=len(self.groups)
        self.used={cap.cap_key(value)for group in self.groups for value in group.get('caps',[])}
        self.previous=None;self.baseline=None;self.baseline_cursors=None;self.pending=None;self.pending_cursors=None
        self.failed=None;self.samples=0;self.closed=False
        self._baseline_decoded=None;self._baseline_joined=None
        class OriginalRows:
            def __getattr__(inner,name):return getattr(p,name)
            def tcp(inner,raw):return proc.original_tcp(p,raw)[0]
        self.original_rows=OriginalRows()

    def observe(self,source_sample):
        self.p.require(self.failed is None and not self.closed,'Original stream rejected/closed; no recovery/retry')
        try:return self._observe(copy.deepcopy(source_sample))
        except Exception as error:self.failed=repr(error);raise

    def _observe(self,sample):
        p=self.p;cap=self.cap;before_cursors=copy.deepcopy(self.cursors)
        item=cap.decode_sample(self.original_rows,self.binding,sample,self.previous)
        cap.append_logs(p,self.binding,self.cursors,sample)
        self.previous=sample;self.samples+=1;stable=False;joined=None
        if item['API']['client_count']==192:
            try:joined=cap.full_owned_join(p,item['table'],item['view']);stable=True
            except ValueError:pass
        if self.baseline is None:
            p.require(stable and not sample['log_chunks'],'Stream must begin at a full stable192 baseline')
            self.baseline=sample;self.baseline_cursors=before_cursors
            self._baseline_decoded=item;self._baseline_joined=joined
            return dict(phase='full192',accepted=True,overlap_pending=False)
        if self.pending is None:
            old=self._baseline_decoded;old_join=self._baseline_joined
            unchanged=stable and all(item['rows'][slot][0]['client_id']==old['rows'][slot][0]['client_id']
                and joined[slot]['client']==old_join[slot]['client']for slot in p.SLOTS)
            if unchanged and not sample['log_chunks']:
                p.require(all(abs((item['API']['ts']-item['rows'][slot][0]['connected_seconds'])-
                    (old['API']['ts']-old['rows'][slot][0]['connected_seconds']))
                    <=cap.LIMITS['max_epoch_skew_s']for slot in p.SLOTS),
                    'Unexplained connection epoch change on an unchanged owned socket')
                self.baseline=sample;self.baseline_cursors=before_cursors
                self._baseline_decoded=item;self._baseline_joined=joined
                return dict(phase='full192',accepted=True,overlap_pending=False)
            self.pending=[self.baseline];self.pending_cursors=copy.deepcopy(self.baseline_cursors)
        self.pending.append(sample)
        p.require(len(self.pending)<=32 and
            sample['observed_unix_s']-self.pending[0]['observed_unix_s']<=cap.LIMITS['max_window_s'],
            'Original pending transport proof exceeded its fixed window')
        if stable:
            repeats=any(self.proc.original_tcp(p,entry['raw_tcp'])[1]for entry in self.pending)
            try:
                if repeats:
                    group=self.proc.certify(p,cap,self.binding,self.lua_sha,self.pending)
                else:
                    group=cap.certify_window(p,self.binding,self.pending_cursors,self.lua_sha,self.pending,self.used)
            except cap.AwaitEvidence:
                return dict(phase='awaiting_original_evidence',accepted=False,overlap_pending=True)
            self.groups.append(group);closed_budget(p,cap,self.proc,self.groups)
            self.used.update(cap.cap_key(value)for value in group.get('caps',[]))
            self.pending=None;self.pending_cursors=None;self.baseline=sample;self.baseline_cursors=before_cursors
            self._baseline_decoded=item;self._baseline_joined=joined
            return dict(phase='full192',accepted=True,overlap_pending=False,closed_group=group)
        return dict(phase='awaiting_original_evidence',accepted=False,overlap_pending=True)

    def close(self):
        try:
            self.p.require(self.failed is None and not self.closed and self.baseline is not None and self.pending is None,
                'Rejected/uninitialized/incomplete original stream cannot close valid')
            self.p.require(self.previous['index']==self.baseline['index'],'Final full192 mapping missing')
            result=dict(schema=SCHEMA,samples=self.samples,groups=copy.deepcopy(self.groups[self.prior_group_count:]),
                case_groups=copy.deepcopy(self.groups),budget=closed_budget(self.p,self.cap,self.proc,self.groups),
                final_full192=True,all_nontransport_main_checks_still_required=True,quality_qualified=False)
            self.closed=True;return result
        except Exception as error:self.failed=repr(error);self.closed=True;raise
