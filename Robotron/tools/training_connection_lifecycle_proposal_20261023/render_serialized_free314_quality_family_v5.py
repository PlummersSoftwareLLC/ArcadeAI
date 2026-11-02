"""Pure prospective source-family renderer; no file/network/process actions.

Change only top-level pair/policy/runtime bindings. Historical forbidden-pair
literals and all scientific predicates stay intact. Publishing, CPU provenance,
current main preflight and one original launch remain separate obligations.
"""
import ast
import hashlib
import re

B='/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/'
REFERENCE='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
REF_CLOCKS=dict(learner_frame_count=1741229950,training_steps=7128160,optimized_samples=27621148672,frame_count=3434514217)
OLD_PAIR='7c74a3f8e27b3401404fe5d69bfbabd243f5cd57984b4f8f33087ba05a9a9f51'
OLD_POLICY='afadb86810b77fc73d2d3c0b89b9da3618163cde24b220389f5e877a6769452c'
FAILED2690_PAIR='7862f46a6d42c51ef05fe8be2e97cdf29ad13717412b32451bc94417267bdba6'
FAILED2690_POLICY='ee28fd761aa30536a5ff3e6fd2bfd3e0b4a1bd7b0f3354a2614a15481a240c32'
FAILED2690_CLOCKS=dict(learner_frame_count=2690731936,training_steps=10685811,optimized_samples=42193287168,frame_count=5256046621)
FAILED2700_PAIR='399f029598471553677c730b97c2ecc174b6fc1c8e295f72e1b319840926890a'
FAILED2700_POLICY='ea53b8a0495a9c4788ae2c1e0deb9a379bb1ca962d383110eaed148f8dda013c'
FAILED2700_CLOCKS=dict(learner_frame_count=2700401151,training_steps=10721482,optimized_samples=42339395584,frame_count=5274310141)
FAILED2715_PAIR='24829cde7c4153795a335b9883a57e6c58ef4974879035245c8fbdff7ae16089'
FAILED2715_POLICY='3928b61f6262819236876c23d3503aed8d2286e1b1d9857eedc3c1d3905a1efc'
FAILED2715_CLOCKS={'learner_frame_count': 2715929502, 'training_steps': 10778819, 'optimized_samples': 42574247936, 'frame_count': 5303666777}
FAILED2739_PAIR='a8d442fb60bd5d4859e2c3683f9e91e410c71d33d6b0de3e3b25d87f17d05cb2'
FAILED2739_POLICY='95726b361f01bceab95bd5deaf6f5534dd1e8d4e7335e38904ae5ca3ee49987d'
FAILED2739_CLOCKS={'learner_frame_count': 2739279553, 'training_steps': 10864951, 'optimized_samples': 42927044608, 'frame_count': 5347766313}
KINDS=('runtime','native_controller','leg_reviewer','leg_preparer','sequence','campaign_assessor','display_source')


def require(value,message):
    if not value:raise ValueError(message)


def assignment(source,name,value):
    tree=ast.parse(source);nodes=[node for node in tree.body if isinstance(node,ast.Assign)
        and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)and node.targets[0].id==name]
    require(len(nodes)==1,'Exactly one source binding required: '+name)
    node=nodes[0];lines=source.splitlines(keepends=True)
    lines[node.lineno-1:node.end_lineno]=[name+'='+repr(value)+'\n'];return ''.join(lines)


def render(templates,pair,pair_sha,case_slug):
    require(set(templates)==set(KINDS)and re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}',case_slug)is not None,
            'Exact source template set and safe unique case slug required')
    require(re.fullmatch('[0-9a-f]{64}',pair_sha)is not None and pair_sha not in (OLD_PAIR,FAILED2690_PAIR,FAILED2700_PAIR,FAILED2715_PAIR,FAILED2739_PAIR),
            'New immutable fixed-pair hash required; never adopt the failed old pair')
    require(pair['reference']['policy']['sha256']==REFERENCE and pair['reference']['saved_clocks']==REF_CLOCKS,
            'Original protected1741 reference and exact saved clocks required')
    clocks=pair['candidate']['saved_clocks'];sha=pair['candidate']['policy']['sha256']
    require(set(clocks)==set(REF_CLOCKS)and all(type(value)is int and value>0 for value in clocks.values())
        and all(clocks[key]>value for key,value in FAILED2739_CLOCKS.items()) and sha not in (REFERENCE,OLD_POLICY,FAILED2690_POLICY,FAILED2700_POLICY,FAILED2715_POLICY,FAILED2739_POLICY)
        and re.fullmatch('[0-9a-f]{64}',sha)is not None,'Genuinely later distinct candidate with exact integer saved clocks required')
    policies={role:dict(sha256=pair[role]['policy']['sha256'],clocks=dict(pair[role]['saved_clocks']))
        for role in ('reference','candidate')}
    stems=dict(runtime='run_quality32_',native_controller='control_quality32_',leg_reviewer='read_quality32_',
        leg_preparer='prepare_quality32_',sequence='sequence_quality32_',campaign_assessor='assess_quality32_',display_source='display_quality32_')
    names={key:stems[key]+case_slug+'_owned_v1.py'for key in KINDS};output={}
    runtime=assignment(assignment(templates['runtime'],'PAIR_SHA',pair_sha),'POLICIES',policies)
    output['runtime']=runtime;runtime_sha=hashlib.sha256(runtime.encode()).hexdigest()
    old_name='run_compiled_full_tail32_quality_serialized_free314_template_v2.py'
    control=templates['native_controller'];require(control.count(old_name)==1,'Exact runtime controller binding site required')
    output['native_controller']=control.replace(old_name,names['runtime'])
    reviewer=assignment(assignment(assignment(templates['leg_reviewer'],'PAIR_SHA',pair_sha),'POLICIES',policies),'RUNTIME_SHA',runtime_sha)
    require(reviewer.count(old_name)==1,'Exact independent runtime path binding required')
    output['leg_reviewer']=reviewer.replace(old_name,names['runtime'])
    for key in ('leg_preparer','campaign_assessor'):output[key]=assignment(templates[key],'PAIR_SHA',pair_sha)
    for key in ('sequence','display_source'):output[key]=templates[key]
    for key,source in output.items():
        ast.parse(source)
        require('__file__'in source,'Every original executable must keep its own source identity')
    return {key:dict(path=B+names[key],source=output[key],sha256=hashlib.sha256(output[key].encode()).hexdigest())for key in KINDS}
