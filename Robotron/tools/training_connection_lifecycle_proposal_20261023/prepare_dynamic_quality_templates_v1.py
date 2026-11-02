"""One prospective unselected source preparation; never launch a scientific case."""
import ast
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
B=G/'tools/startup_policy_journal_proposal'
P=G/'tools/training_connection_lifecycle_proposal_20261023'
D=R/'dynamic-proc-quality-family-renderer-CPU-original01-preparation-20261023'

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def replace_once(source,old,new):
    assert source.count(old)==1,(old,source.count(old))
    return source.replace(old,new)

def write(path,source):
    ast.parse(source)
    with path.open('xb')as f:
        f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return h.pin(path)

if __name__=='__main__':
    h=load(B/'run_full_policy_startup_v3.py','_dynfamily_h')
    assert h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    oldrender=load(P/'render_owned_quality_family_v1.py','_dynfamily_oldrenderer')
    oldpair='7c74a3f8e27b3401404fe5d69bfbabd243f5cd57984b4f8f33087ba05a9a9f51'
    failedpair='7862f46a6d42c51ef05fe8be2e97cdf29ad13717412b32451bc94417267bdba6'
    failedpolicy='ee28fd761aa30536a5ff3e6fd2bfd3e0b4a1bd7b0f3354a2614a15481a240c32'
    oldjob=json.loads((R/'owned-quality-family-renderer-CPU-original01-preparation-20261023/job.json').read_text())
    templates={k:h.checked(v).read_text()for k,v in oldjob['templates'].items()}
    D.mkdir(mode=0o700)
    names=dict(runtime='run_compiled_full_tail32_quality_owned_health_template_v3.py',
        native_controller='control_compiled_full_tail32_quality_owned_health_template_v2.py',
        leg_reviewer='read_compiled_quality32_owned_health_template_v3.py',
        leg_preparer='prepare_quality32_owned_health_leg_template_v2.py',
        campaign_assessor='assess_quality32_owned_health_campaign_template_v2.py')
    guard="PAIR_SHA!='"+oldpair+"'"
    newguard="PAIR_SHA not in ('"+oldpair+"','"+failedpair+"')"
    new={}
    for k in ['runtime','leg_reviewer','leg_preparer','campaign_assessor']:
        source=replace_once(templates[k],guard,newguard)
        if k!='campaign_assessor':source=replace_once(source,">2630798737",">2690731936")
        if k=='runtime':
            values=ast.literal_eval(next(n.value for n in ast.parse(source).body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name)and t.id=='HEALTH_DEPENDENCIES'for t in n.targets)))
            values['proc_repeat']=h.pin(P/'certify_owned_proc_repeat_v3.py')['sha256']
            source=oldrender.assignment(source,'HEALTH_DEPENDENCIES',values)
            source=replace_once(source,
                "not in ('afadb86810b77fc73d2d3c0b89b9da3618163cde24b220389f5e877a6769452c',)",
                "not in ('afadb86810b77fc73d2d3c0b89b9da3618163cde24b220389f5e877a6769452c','"+failedpolicy+"')")
        new[k]=source
    oldname='run_compiled_full_tail32_quality_owned_health_template_v2.py'
    newname=names['runtime']
    new['native_controller']=replace_once(templates['native_controller'],oldname,newname)
    new['leg_reviewer']=oldrender.assignment(replace_once(new['leg_reviewer'],oldname,newname),
        'RUNTIME_SHA',hashlib.sha256(new['runtime'].encode()).hexdigest())
    pins={key:write(B/names[key],source)for key,source in new.items()}
    for key in ['sequence','display_source']:pins[key]=oldjob['templates'][key]
    source=(P/'render_owned_quality_family_v1.py').read_text()
    source=replace_once(source,"KINDS=('runtime'",
        "FAILED2690_PAIR='"+failedpair+"'\nFAILED2690_POLICY='"+failedpolicy+"'\n"
        "FAILED2690_CLOCKS=dict(learner_frame_count=2690731936,training_steps=10685811,"
        "optimized_samples=42193287168,frame_count=5256046621)\nKINDS=('runtime'")
    source=replace_once(source,'pair_sha!=OLD_PAIR','pair_sha not in (OLD_PAIR,FAILED2690_PAIR)')
    source=replace_once(source,"clocks['learner_frame_count']>2630798737 and sha not in (REFERENCE,OLD_POLICY)",
        "all(clocks[key]>value for key,value in FAILED2690_CLOCKS.items()) and sha not in (REFERENCE,OLD_POLICY,FAILED2690_POLICY)")
    source=replace_once(source,oldname,newname)
    renderer=write(P/'render_owned_quality_family_v2.py',source)
    provenance=h.put(D/'unselected-template-and-renderer-source-provenance.json',dict(
        schema='robotron-dynamic-proc-future-native-family-source-provenance-v1',
        prior_templates=oldjob['templates'],new_templates=pins,prior_renderer=oldjob['subject'],
        renderer=renderer,new_proc_certificate=h.pin(P/'certify_owned_proc_repeat_v3.py'),
        scope='New unselected templates: proc pin, runtime/reviewer path+SHA bindings and exclusion of both failed pairs/policies. Original game/runtime helpers and confirmation math unchanged.',
        new_source_family_published=False,candidate_selected=False,scientific_guard_selected=False,
        quality_qualified=False,created_unix_s=time.time()))
    test=(P/'validate_owned_quality_family_v1.py').read_text()
    start=test.index("    pair=dict(reference=")
    end=test.index("    rendered=subject.render",start)
    test=test[:start]+"""    pair=dict(reference=dict(policy=dict(sha256=subject.REFERENCE),saved_clocks=subject.REF_CLOCKS),
        candidate=dict(policy=dict(sha256='c'*64),saved_clocks={key:value+1 for key,value in subject.FAILED2690_CLOCKS.items()}))
"""+test[end:]
    test=replace_once(test,
        'self.assertIn("PAIR_SHA!=\'"+subject.OLD_PAIR+"\'",rendered[\'runtime\'][\'source\'])',
        'self.assertIn("PAIR_SHA not in (\'"+subject.OLD_PAIR+"\',\'"+subject.FAILED2690_PAIR+"\')",rendered[\'runtime\'][\'source\'])')
    needle="            negative.extend(['old_pair_digest','unsafe_case_slug'])"
    addition=needle+"""
            with self.assertRaises(ValueError):subject.render(templates,pair,subject.FAILED2690_PAIR,'synthetic')
            negative.append('closed2690_pair_forbidden')
            data=copy.deepcopy(pair);data['candidate']['policy']['sha256']=subject.FAILED2690_POLICY
            with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
            negative.append('closed2690_policy_forbidden')
            for key,floor in subject.FAILED2690_CLOCKS.items():
                data=copy.deepcopy(pair);data['candidate']['saved_clocks'][key]=floor
                with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
                negative.append('closed2690_nonlater_'+key)"""
    test=replace_once(test,needle,addition)
    test=replace_once(test,'no_source_family_published=True','no_source_family_published=True,old2690_original_retried=False')
    tests=write(P/'validate_owned_quality_family_v2.py',test)
    job=oldjob.copy();job.update(templates=pins,subject=renderer,output=str(D/'output-original01'))
    jp=h.put(D/'job.json',job)
    cpu=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_dynfamily_cpu')
    entries=[*pins.values(),jp,tests,provenance,*[v for v in job.values()if isinstance(v,dict)and 'path'in v]]
    cfg=dict(unit='robotron-dynamic-proc-future-quality-family-CPU-original01-20261023.service',
        output=str(D/'execution-original01'),
        argv=['/usr/bin/python3.12','-I','-B',tests['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',tests['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
            'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[cpu.pin(v['path'])for v in entries],observation_s=240)
    h.put(D/'controller-config.json',cfg)
    print(str(D/'controller-config.json'))
