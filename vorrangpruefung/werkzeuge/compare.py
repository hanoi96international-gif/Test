import json, sys
J={x['id']:x for x in json.load(open(sys.argv[1]))}; X={x['id']:x for x in json.load(open(sys.argv[2]))}
bad=0
for k in J:
    j,x=J[k],X[k]; diffs=[]
    for f in ('s0','kv','wg','kiz','kw'):
        if abs((j[f] or 0)-(x[f] or 0))>0.011: diffs.append(f"{f}: Web {j[f]} / Excel {x[f]}")
    if j['st']!=x['st']: diffs.append(f"Status Web {j['st']} / Excel {x['st']}")
    for i,(a,b) in enumerate(zip(j['bud'],x['bud'])):
        if abs(a-(b or 0))>0.011: diffs.append(f"Budget{i}: Web {a} / Excel {b}")
    if x['errors']: diffs.append(f"Formelfehler {x['errors']}")
    if diffs:
        bad+=1; print('❌', k, '| Web:', j['head'], '| Excel:', x['head']); [print('     ',d) for d in diffs]
print(f'{len(J)-bad} von {len(J)} Fällen identisch')
