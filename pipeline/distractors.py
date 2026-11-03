"""Build a conservative pool, rejecting synonyms and overlapping meanings."""
import re
from .config import PLACE
from .enrich import choose, clean_gloss, clean_zh, content, inflections, valid_gloss

# Inflection / spelling-variant / meta glosses make useless (and give-away) distractors.
FORM_OF=re.compile(r'(?i)\b(?:spelling|form|plural|past|participle|gerund|synonym|abbreviation|initialism|misspelling) of\b|\bintensive form\b')
UNSUITABLE=re.compile(r'(?i)\b(?:sex\w*|ejaculat\w*|masturbat\w*|genital\w*|semen|orgasm|drugs?|cocaine|kill\w*|suicide)\b')

def build_distractors(items,lexicon,mt,limit=30):
    banned={x['text'].lower() for x in items}
    for x in items: banned.update(s.lower() for s in x['synonyms'])
    meanings=[content(x['meaningEn']) for x in items]; heads={w for x in items for w in x['text'].split() if len(w)>3}
    options=[]
    def common(word):
        _,ec=lexicon.lookup(word); ranks=[int(ec[k]) for k in ('frq','bnc') if str(ec.get(k,'')).isdigit() and int(ec[k])>0] if ec else []
        return bool(ranks) and min(ranks)<15000
    def familiarity(phrase):
        # Well-known phrases have many dictionary senses; one-off coinages ("back titrate") have one.
        entries,_=lexicon.lookup(phrase); return sum(len(e.get('s',[])) for e in entries)
    for head in sorted(heads):
        pool=[w for w in lexicon.phrases.get(head,[]) if all(common(x) or x in PLACE for x in w.split()) and len(w.split())<=4]
        pool.sort(key=lambda w:(-familiarity(w),w))
        options.extend(pool[:15])
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
        if not valid_gloss(gloss) or FORM_OF.search(gloss) or UNSUITABLE.search(gloss+' '+w) or set(s.get('t',[]))&{'alt-of','form-of','obsolete','archaic','rare','vulgar','offensive','derogatory','slur','euphemistic','dated'}: continue
        if any(r['meaningEn']==gloss for r in result): continue
        if any(x.lower() in banned for x in e.get('syn',[])+s.get('syn',[])): continue
        tokens=content(gloss)
        if not tokens or any(m and len(tokens&m)/min(len(tokens),len(m))>0.5 for m in meanings): continue
        zh=clean_zh(ec.get('translation','')) if ' ' not in w else ''
        zh=zh or '；'.join(e.get('zh',[])[:2]) or mt.translate(gloss)
        if not zh: continue
        result.append({'text':w,'pos':e.get('pos'),'meaningEn':gloss,'meaningZh':zh,'meaningZhSource':'ecdict' if ' ' not in w and clean_zh(ec.get('translation','')) else 'kaikki' if e.get('zh') else 'mt','inflections':inflections(w,lexicon)})
        if len(result)>=limit: break
    return result
