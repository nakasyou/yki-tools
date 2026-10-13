"""Test one universal special-code ordering without fixed block bases.
F5 B-prefix catalogue joins anchor ranks0..11 at base241; three V-only
positions remain unspecified. Every other first-nibble block has a free base.
Evidence consists of named-pattern/catalogue joins, not same-object photos.
"""
import itertools,json
from pathlib import Path
ROOT=Path(__file__).parent
lookup=json.loads((ROOT/'bump_confirmed_lookup.json').read_text())
fixed={n-241:int(code[2],16) for code,n in lookup.items() if code.startswith('F5')}
assert len(fixed)==9
symbols=set(range(1,16))-{5,10,15}
slots=[i for i in range(12) if i not in fixed]
remaining=sorted(symbols-set(fixed.values()))
groups={a:[(code,n) for code,n in lookup.items() if code[0]==a and code[1]=='5'] for a in '781EC3'}
results=[]
for tail in itertools.permutations(remaining):
 order=[fixed.get(i) for i in range(12)]
 for i,c in zip(slots,tail):order[i]=c
 for fpos in range(13):
  shared=order[:fpos]+[15]+order[fpos:]
  inferred={}
  for a,obs in groups.items():
   reduced=[x for x in shared if x!=int(a,16)]
   inferred[a]={code:n-reduced.index(int(code[2],16)) for code,n in obs}
  consistent={a:len(set(bases.values()))<=1 for a,bases in inferred.items()}
  results.append({'shared_order':shared,'consistent_blocks':consistent,'inferred_bases':inferred})
fits=[r for r in results if all(r['consistent_blocks'].values())]
counts={a:sum(r['consistent_blocks'][a] for r in results) for a in groups}
minimal=[]
for size in range(1,len(groups)+1):
 for subset in itertools.combinations(groups,size):
  if any(set(s).issubset(subset) for s in minimal):continue
  if not any(all(r['consistent_blocks'][a] for a in subset) for r in results):minimal.append(subset)
audit={'assumptions':['one shared permutation of13 symbols1..F excluding5,A','remove first nibble from shared order to get each12-entry block','each block has an arbitrary additive base','F block base241 from B-prefix catalogue joins'], 'not_assumed':['bases of other blocks','V prefix equivalent to B prefix','global boundary B241+12*k'], 'fixed_F_ranks':fixed,'unfixed_F_symbols':remaining,'tested_permutations':len(results),'joint_fits':len(fits),'individual_block_fits':counts,'minimal_conflicting_block_sets':minimal,'observations':groups,'conclusion':'Shared permutation rejected under named-pair evidence' if not fits else 'Possible shared permutations remain','limitation':'Rejection can reflect mistaken catalogue/name joins; does not prove a ROM lookup implementation or a new conversion formula.','candidates':results}
(ROOT/'bump_special_free_base_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in audit.items() if k not in ['candidates','observations']},ensure_ascii=False,indent=2))
