"""Build a conservative pool, rejecting synonyms and overlapping meanings."""
from .enrich import choose, clean_gloss, clean_zh, content, inflections

def build_distractors(items,lexicon,mt,limit=30):
    banned={x['text'].lower() for x in items}
    for x in items: banned.update(s.lower() for s in x['synonyms'])
    meanings=[content(x['meaningEn']) for x in items]; heads={w for x in items for w in x['text'].split() if len(w)>3}
    options=[]
    for head in sorted(heads):
        options.extend(lexicon.phrases.get(head,[]))
    # Include other words with similar ECDICT frequency and POS.
    ranks=[]
    for item in items:
        _,ec=lexicon.lookup(item['text'].split()[0]); rank=int(ec.get('frq') or 0)
        if rank: ranks.append(rank)
    if ranks:
        # Scan once, not once per item. Candidate POS is checked below.
        import json
        low=max(1,min(ranks)-500); high=max(ranks)+500
        for (data,) in lexicon.db.execute("SELECT data FROM e WHERE CAST(json_extract(data,'$.frq') AS INTEGER) BETWEEN ? AND ? LIMIT 1000",(low,high)):
            row=json.loads(data); w=row['word'].lower()
            if ' ' not in w and w.isalpha() and any(abs(int(row.get('frq') or 0)-r)<=500 for r in ranks): options.append(w)
    result=[]; seen=set()
    for w in options:
        if w in banned or w in seen: continue
        seen.add(w); e,s,ec=choose(w,lexicon); gloss=clean_gloss(s.get('g',''))
        if not gloss or e.get('pos') not in {x['pos'] for x in items}: continue
        if any(x.lower() in banned for x in e.get('syn',[])+s.get('syn',[])): continue
        tokens=content(gloss)
        if not tokens or any(m and len(tokens&m)/min(len(tokens),len(m))>0.5 for m in meanings): continue
        zh=clean_zh(ec.get('translation','')) if ' ' not in w else ''
        zh=zh or '；'.join(e.get('zh',[])[:2]) or mt.translate(gloss)
        if not zh: continue
        result.append({'text':w,'pos':e.get('pos'),'meaningEn':gloss,'meaningZh':zh,'meaningZhSource':'ecdict' if ' ' not in w and clean_zh(ec.get('translation','')) else 'kaikki' if e.get('zh') else 'mt','inflections':inflections(w,lexicon)})
        if len(result)>=limit: break
    return result
