import json, struct, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
vs=json.loads((ROOT/'research/data/bump_yki_resource_classification.json').read_text())['versions']
names=[Path(v['file']).name for v in vs]
ds=[(ROOT/'yki'/n).read_bytes() for n in names]
def blob(j,r):
 return ds[j][r['offset']:r['offset']+r['size']]
def group(j,kind):
 return [blob(j,r) for r in vs[j]['resources'] if r['structural_kind']==kind]
def digest(b): return hashlib.sha256(b).hexdigest()
report={'versions':names,'comparison_note':'Medal rows aligned by row index; asset equality uses full raw bytes. Unknown command semantics are not inferred from equality.'}
report['header_u16']=[{'offset':hex(o),'values':[struct.unpack_from('<H',d,o)[0] for d in ds]} for o in range(0x20,0x40,2)]
report['header_40_1ff']=[{'version':n,'byte_counts':{'00':d[64:512].count(0),'ff':d[64:512].count(255)},'sha256':digest(d[64:512])} for n,d in zip(names,ds)]
roots=[group(j,'120-byte root command pairs')[0] for j in range(6)]
report['root_changed_u16']=[{'relative_offset':hex(o),'absolute_offsets':[hex(v['resources'][0]['offset']+o) for v in vs],'values':[struct.unpack_from('<H',b,o)[0] for b in roots]} for o in range(0,120,2) if len({b[o:o+2] for b in roots})>1]
medals=[group(j,'988 medal records,36 bytes each')[0] for j in range(6)]
report['medal_common_rows']=sum(len({b[i*36:(i+1)*36] for b in medals})==1 for i in range(988))
report['medal_word_comparison']=[{'record_relative_offset':hex(o),'rows_equal_all_versions':sum(len({b[i*36+o:i*36+o+2] for b in medals})==1 for i in range(988)),'unique_values_each_version':[sorted({struct.unpack_from('<H',b,i*36+o)[0] for i in range(988)}) for b in medals]} for o in range(0,36,2)]
report['assets']={}
for kind in ['RGB-like triples, framed by FFFF','two command/reference pairs','AU audio']:
 gs=[group(j,kind) for j in range(6)];sets=[set(map(digest,g)) for g in gs]
 report['assets'][kind]={'counts':list(map(len,gs)),'unique_counts':list(map(len,sets)),'common_unique_blobs_all_versions':len(set.intersection(*sets)),'adjacent':[{'from':names[j-1],'to':names[j],'identical_at_same_group_index':sum(a==b for a,b in zip(gs[j-1],gs[j])),'shared_unique_blobs':len(sets[j-1]&sets[j]),'new_unique_blobs':len(sets[j]-sets[j-1]),'removed_unique_blobs':len(sets[j-1]-sets[j])} for j in range(1,6)]}
 if kind=='two command/reference pairs':
  report['assets'][kind]['pairs']=[[list(struct.unpack('<4H',b)) for b in g] for g in gs]
 if kind=='AU audio':
  report['audio_header_words']=[{'offset':hex(o),'unique_values_each_version':[sorted({struct.unpack_from('<H',b,o)[0] for b in g}) for g in gs]} for o in range(0,32,2)]
  report['audio_tail_8']=[{'version':names[j],'most_common':__import__('collections').Counter(b[-8:].hex() for b in g).most_common(5)} for j,g in enumerate(gs)]
(ROOT/'outputs/yki_unknown_cross_version_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('common medal rows',report['medal_common_rows'])
for w in report['medal_word_comparison']: print(w['record_relative_offset'],w['rows_equal_all_versions'],[len(v) for v in w['unique_values_each_version']])
for k,v in report['assets'].items(): print(k,{a:b for a,b in v.items() if a!='pairs'})
print('command samples',[v[:3] for v in report['assets']['two command/reference pairs']['pairs']])
print('audio headers',report['audio_header_words'])
