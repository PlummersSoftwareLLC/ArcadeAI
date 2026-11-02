"""Independent raw-evidence replay for the unselected live health diagnostic.

No collection, threads, network, process signals, policy load or quality decision.
The caller must authenticate this source, the job and all original pins with the
source-bound immutable reader. Recompute every phase/group from original bytes;
a cached report/budget/accepted flag cannot substitute for raw replay.
"""
import json
from pathlib import Path


def require(value,message):
    if not value:raise ValueError(message)


def review(job,report,initial_cursors,read,h):
    for entry in job['sources'].values():h.checked(entry)
    p=h.load('_review_owned_cap_primitives',Path(job['sources']['primitives']['path']))
    transport=h.load('_review_owned_cap_stream',Path(job['sources']['transport']['path']))
    health=h.load('_review_owned_cap_health',Path(job['sources']['health']['path']))
    sup=h.load('_review_owned_cap_sup',Path(job['sources']['supervision']['path']))
    collector=h.load('_review_owned_cap_packing',Path(job['sources']['collector']['path']))
    main=read(job['binding']);policy=read(main['supervision_policy']);baseline=read(main['baseline_API'])
    proof=health.verify_sources(Path(job['sources']['window']['path']).read_bytes(),
        Path(job['sources']['supervision']['path']).read_bytes(),Path(job['sources']['health']['path']).read_bytes())
    require(report['status']=='ORIGINAL_LIVE_TRANSPORT_AND_FULL_HEALTH_CLOSED_NOT_SCIENTIFIC'
        and report['quality_qualified']is False and report['scientific_guard_selected']is False,
        'Original live observation did not close successfully')
    require(type(report['samples'])is list and len(report['samples'])==len(report['actual_status'])
        and report['samples'],'All original samples and actual status records required')
    stream=transport.Stream(p,main,initial_cursors,p.LUA_SHA);previous_API=None;previous_deep=None
    last_deep=None;deep_count=0;begin=end=None;pending=0;counts={}
    for index,pin in enumerate(report['samples']):
        record=read(pin);sample=collector.unpacked(record);API=p.decode(sample['raw_API'])
        require(sample['index']==index,'Original evidence skipped/reordered/duplicated')
        now=sample['observed_unix_s'];begin=now if begin is None else begin;end=now
        if record['deep']is not None:
            deep=record['deep'];health.physical(sup,policy,deep['snapshot'],previous_deep)
            health.autosave(deep['autosave'],deep['checked_unix_s'])
            require(deep['held197_checked_live']is True and deep['held_error']is None
                and deep['snapshot']['unix_s']<=deep['checked_unix_s']<=sample['API_begin_unix_s']
                and deep['autosave']['uid']==main['supervision_policy']['identity']['uid'],
                'Original physical/source/autosave census was not bracketed')
            previous_deep=deep['snapshot'];last_deep=deep;deep_count+=1
        require(last_deep is not None and 0<=now-last_deep['checked_unix_s']<=10,
                'Original sample lacks a fresh deep census')
        health.sample(p,API,baseline,main['experiment'],now,previous_API)
        phase=stream.observe(sample);status=report['actual_status'][index]
        require(status['index']==index and status['phase']==phase
            and status['learner_frames']==API['learner_frame_count']
            and status['training_steps']==API['training_steps']and status['fleet_fps']==API['fps'],
            'Original cached phase/work clocks differ from raw independent replay')
        pending+=int(phase['overlap_pending']);counts[str(API['client_count'])]=counts.get(str(API['client_count']),0)+1
        previous_API=API
    summary=stream.close()
    require(summary==report['transport']and deep_count==report['deep_samples']and deep_count>=3,
            'Original raw replay does not reproduce the complete transport/deep record')
    require(job['duration_s']==120 and 119<=end-begin<=121 and 120<=report['duration_s']<=125,
            'Original fixed120-second diagnostic coverage differs')
    require(report['writer']['all_original_samples_persisted']is report['writer']['thread_stopped']is True
        and type(report['writer']['max_pending'])is int and 0<=report['writer']['max_pending']<=32,
        'Original writer did not drain/close within the fixed queue bound')
    require(len(main['held_hashes'])==197 and all(h.pin(path)['sha256']==sha
        for path,sha in main['held_hashes'].items()),'Original197 held inputs differ at independent readback')
    return dict(status='ORIGINAL_LIVE_RAW_TRANSPORT_AND_FULL_HEALTH_REPLAY_VERIFIED_NOT_SCIENTIFIC',
        samples=len(report['samples']),deep_samples=deep_count,API_count_histogram=counts,
        original_capture_span_s=end-begin,pending_samples=pending,transport=summary,source_specialization=proof,
        all197_held_inputs_independently_hashed=True,quality_qualified=False,
        scientific_guard_selected=False,original_native_evaluator_integration_still_required=True)
