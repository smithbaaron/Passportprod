import json,subprocess,os,sys,concurrent.futures as cf,time
D="/tmp/claude-0/-home-user-Passportprod/6492453e-d707-5a6e-b62e-7229034b9640/scratchpad/datalib"
objs=json.load(open(D+"/raw/profile_objects.json"))
counts=json.load(open(D+"/raw/record_counts.json"))
SKIP_TYPES={'textarea','base64','address','location','anyType','complexvalue','json'}
def soql(q):
    for attempt in range(2):
        r=subprocess.run(["sf","data","query","-o","prod","-q",q,"--json"],capture_output=True,text=True)
        try:
            d=json.loads(r.stdout)
            if 'result' in d: return d['result']['records'],None
            return None,d.get('message','')[:300]
        except Exception as e:
            time.sleep(2)
    return None,(r.stdout or r.stderr)[:300]
def profile(o):
    out=f"{D}/profile/{o}.json"
    if os.path.exists(out): return o,"cached"
    d=json.load(open(f"{D}/describe/{o}.json"))
    n=counts.get(o,0); big=n>400000
    where=" WHERE CreatedDate = LAST_N_DAYS:365" if big else ""
    res={"object":o,"rows":n,"sampled_last_365d":big,"fill":{},"bool_true":{},"picklist_values":{},"errors":[]}
    fields=[f for f in d['fields'] if f['name']!='Id']
    countable=[f['name'] for f in fields if f['type'] not in SKIP_TYPES and f['type']!='boolean' and not f.get('compoundFieldName')]
    # total
    recs,err=soql(f"SELECT COUNT(Id) total FROM {o}{where}")
    total=recs[0]['total'] if recs else None
    if err: res['errors'].append(err)
    res['total_in_scope']=total
    for i in range(0,len(countable),35):
        chunk=countable[i:i+35]
        q="SELECT "+", ".join(f"COUNT({f}) c{j}" for j,f in enumerate(chunk))+f" FROM {o}{where}"
        recs,err=soql(q)
        if recs:
            for j,f in enumerate(chunk): res['fill'][f]=recs[0].get(f"c{j}")
        else:
            res['errors'].append(f"chunk {i}: {err}")
            # retry one by one
            for f in chunk:
                r2,e2=soql(f"SELECT COUNT({f}) c FROM {o}{where}")
                res['fill'][f]=r2[0]['c'] if r2 else None
                if e2: res['errors'].append(f"{f}: {e2[:120]}")
    if n<=400000:
        for f in fields:
            if f['type']=='boolean' and f['filterable']:
                recs,err=soql(f"SELECT COUNT(Id) c FROM {o} WHERE {f['name']} = true")
                res['bool_true'][f['name']]=recs[0]['c'] if recs else None
            if f['type'] in ('picklist','multipicklist') and f['filterable'] and f['groupable'] and n<=300000:
                recs,err=soql(f"SELECT {f['name']} v, COUNT(Id) c FROM {o} GROUP BY {f['name']} ORDER BY COUNT(Id) DESC LIMIT 60")
                if recs: res['picklist_values'][f['name']]={str(r['v']):r['c'] for r in recs}
    json.dump(res,open(out,"w"))
    return o,f"ok fill={len(res['fill'])} errs={len(res['errors'])}"
order=sorted(objs,key=lambda o:counts.get(o,0))
with cf.ThreadPoolExecutor(5) as ex:
    for o,s in ex.map(profile,order): print(o,s,flush=True)
print("DONE",flush=True)
