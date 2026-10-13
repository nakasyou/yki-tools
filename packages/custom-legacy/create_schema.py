"""Generate the editor/runtime JSON Schema from shared small definitions."""
import json
from pathlib import Path

number = {'type':'integer','minimum':1,'maximum':988}
resource = {'type':'integer','minimum':2,'maximum':65534}
builtin = {'type':'integer','minimum':0,'maximum':65533}
fields=['summonSound','tribeSound','nameSound','introSound','postSound','callSound','songSound']
def obj(properties, required=()):
 return {'type':'object','additionalProperties':False,'properties':properties,'required':list(required)}
def ref(name):return {'$ref':f'#/$defs/{name}'}
rows={'type':'array','minItems':4,'maxItems':4,'items':{'type':'string','pattern':'^[01]{4}$'}}
hex_bits={'type':'string','pattern':'^(0[xX])?[0-9a-fA-F]{4}$'}
options=obj({'frameAlignment':{'enum':['trim','pad','error'],'default':'trim'},'volume':{'enum':['preserve','peak','match'],'default':'preserve'},'allowClipping':{'type':'boolean','default':False},'referenceResource':resource})
media=obj({'file':{'type':'string','minLength':1},**options['properties']},['file'])
sound={'oneOf':[{'type':'null'},{'type':'string','minLength':1},media,obj({'builtin':builtin},['builtin']),obj({'resource':resource},['resource'])]}
medal_text={'type':'string','pattern':'^[Bb][0-9]{1,3}$'}
# Bare B-prefixed decimal strings are medal IDs, matching resolve_id precedence.
id_hex={**hex_bits,'not':medal_text}
id_={'oneOf':[number,medal_text,id_hex,rows,
 obj({'medal':number},['medal']),obj({'bumpsHex':hex_bits},['bumpsHex']),obj({'bumps':rows},['bumps']),
 obj({'sound':builtin,'namespace':{'enum':['builtin','resource'],'default':'builtin'},'field':{'enum':fields,'default':'nameSound'},'medal':number},['sound'])]}
frame={'type':'array','minItems':3,'maxItems':3,'items':{'type':'integer','minimum':0,'maximum':255}}
frames={'type':'array','minItems':1,'maxItems':100000,'items':frame}
led={'oneOf':[{'type':'null'},{'type':'string','minLength':1},obj({'frames':frames,'repeat':{'type':'integer','minimum':1,'maximum':1024,'default':1}},['frames']),obj({'resource':resource,'repeat':{'type':'integer','minimum':1,'maximum':1024,'default':1}},['resource'])]}
override=obj({'id':ref('id'),'type':{'enum':['normal','song']},'template':{'oneOf':[number,{'type':'string','pattern':'^[Bb][0-9]{1,3}$'}]},'led':ref('led'),**{f:ref('sound') for f in fields}},['id'])
override['allOf']=[{'if':{'required':['type'],'properties':{'type':{'const':'normal'}}},'then':{'not':{'required':['songSound']}}}]
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://yki.local/schema/v1.json','title':'Yo-kai Watch U YKI build configuration',
 'description':'Paths are relative to this JSON file. IDs select existing 1..988 table rows; unknown physical-code conversion is never invented.',
 **obj({'$schema':{'type':'string'},'extends':{'oneOf':[{'type':'integer','enum':[2,3,4,5,6,7]},{'type':'string','minLength':1,'pattern':'\\.[yY][kK][iI]$'}]},'version':{'type':'integer','minimum':0,'maximum':10,'description':'Selects built-in spoken-version ID 0x40 + version. Not a proven firmware identity.'},'output':{'type':'string','minLength':1},'mappingPolicy':{'enum':['warn','strict'],'default':'warn'},'audio':ref('audioOptions'),'overrides':{'type':'array','items':ref('override')}},['extends','overrides']),
 '$defs':{'id':id_,'sound':sound,'led':led,'override':override,'audioOptions':options}}
Path(__file__).with_name('yki.schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')
