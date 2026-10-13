"""Optional reference comparison. Python is used ONLY for tests, not by yki-core."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'packages/custom-legacy'))
from yki_cli.builder import build
from yki_cli.format import Image
from yki_cli.audio import AudioEncoder, BIT_REVERSE

cases=[
    ('unchanged', {'extends':2,'overrides':[]}),
    ('version-zero', {'extends':2,'version':0,'overrides':[]}),
    ('LED-copy-on-write', {'extends':2,'overrides':[{'id':'7ED5','songSound':{'builtin':107},'led':{'frames':[[255,0,0],[0,0,255]],'repeat':3}}]}),
    ('LED-repeat', {'extends':2,'overrides':[{'id':655,'led':{'resource':5,'repeat':12}}]}),
    ('new-medals', {'extends':2,'overrides':[{'id':900,'type':'song','template':655,'songSound':{'resource':31}},{'id':901,'type':'normal','nameSound':{'resource':40},'summonSound':{'builtin':37},'led':{'frames':[[1,2,3]]}}]}),
    ('conversion-sequential', {'extends':2,'overrides':[{'id':1,'type':'song','songSound':{'resource':31}},{'id':1,'introSound':None},{'id':1,'songSound':{'builtin':107}}]}),
    ('sound-namespace', {'extends':2,'overrides':[{'id':{'sound':31,'namespace':'resource','field':'songSound','medal':655},'songSound':{'builtin':107}}]}),
    ('clear-song', {'extends':2,'overrides':[{'id':655,'songSound':None}]}),
    ('clear-normal-LED', {'extends':2,'overrides':[{'id':1,'led':{'frames':[[1,2,3]]}},{'id':1,'led':None}]}),
    ('low-confidence', {'extends':2,'overrides':[{'id':'F12A'}]}),
]
for version in range(3,8):
    cases.append((f'unchanged-Ver{version}',{'extends':version,'overrides':[]}))
media=ROOT/'third_party/media/yarimasunesugi.mp3'
if media.is_file():
    for alignment in ['trim','pad']:
        for volume in ['preserve','peak','match']:
            cases.append((f'audio-{alignment}-{volume}',{'extends':2,'audio':{'frameAlignment':alignment,'volume':volume,'allowClipping':True},'overrides':[{'id':655,'songSound':str(media)}]}))
requests=[{'directory':str(ROOT),'config':config} for _,config in cases]
result=subprocess.run(['node',str(Path(__file__).with_name('parity-driver.mjs'))],input=json.dumps(requests),capture_output=True,text=True,check=True)
outputs=json.loads(result.stdout)
for (name,config),out in zip(cases,outputs,strict=True):
    assert 'error' not in out,(name,out)
    expected,manifest,_=build(config,ROOT,lambda _:None)
    actual=bytes.fromhex(out['hex'])
    assert actual==expected,f'{name}: binary differs; first difference {next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),None)}'
    for key in ['source_sha256','output_sha256','size','version_spoken_id','version','resource_count','handle_to_output_resource','overrides']:
        reference=json.loads(json.dumps(manifest[key]))
        assert out['manifest'][key]==reference,(name,key,out['manifest'][key],reference)
    for a,b in zip(out['manifest']['audio'],manifest['audio'],strict=True):
        for key in ['input_sha256','frames','duration_seconds','source_samples','added_padding_samples','trimmed_samples','volume_mode','gain_db','reference','decoded','trials','resource']:
            assert a[key]==b[key],(name,key,a[key],b[key])
    print(f'{name}: identical binary and manifest',flush=True)
print(f'{len(cases)} parity cases passed')
