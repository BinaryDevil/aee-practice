"""Episode-specific phrase and word detection."""
import collections, re, json
from .paths import TRANSCRIPT_DIR
import spacy
from .config import PROMO, CUE, FUNC, IDIO, META, PLACE, STOP, WEAK
from .lexicon import PARTICLES, valid_pattern

_nlp=None
def nlp():
    global _nlp
    if _nlp is None: _nlp=spacy.load('en_core_web_sm')
    return _nlp

def match_pattern(tokens, pattern):
    """Return exclusive token end; tokens are (surface, lemma), within one sentence."""
    p=pattern.split()
    if not valid_pattern(pattern): return None
    def go(i,j):
        if j==len(p): return i
        if i>=len(tokens): return None
        if p[j] in PLACE:
            for n in (1,2,3):
                if i+n<=len(tokens):
                    end=go(i+n,j+1)
                    if end is not None: return end
            return None
        if p[j] in tokens[i]:
            end=go(i+1,j+1)
            if end is not None: return end
        if len(p)==2 and j==1 and p[j] in PARTICLES:
            for n in (1,2):
                if i+n<len(tokens) and p[j] in tokens[i+n] and not any(pair[0] in PARTICLES for pair in tokens[i:i+n]): return i+n+1
        return None
    return go(0,0)

def sentences(segments):
    # Process segments independently so rejected material never gets rejoined to a sentence.
    out=[]
    for seg in segments:
        text=seg.get('text','').strip()
        if not text or PROMO.search(text) or seg.get('avg_logprob',0)<-1 or seg.get('no_speech_prob',0)>0.6: continue
        words=seg.get('words') or []
        spans=[]
        if words:
            # Rebuild the text from word tokens so sentence boundaries map to word timestamps.
            joined=''.join(w[2] for w in words); lead=len(joined)-len(joined.lstrip()); pos=0
            for w0,w1,word in words:
                spans.append((pos-lead,pos-lead+len(word),w0,w1)); pos+=len(word)
            text=joined.strip()
        for sent in nlp()(text).sents:
            if not sent.text.strip(): continue
            start,end=seg.get('start',0),seg.get('end',0)
            inside=[(w0,w1) for a,b,w0,w1 in spans if b>sent.start_char and a<sent.end_char]
            if inside: start,end=inside[0][0],inside[-1][1]
            out.append({'text':sent.text.strip(),'start':round(start,2),'end':round(end,2),'doc':sent.as_doc()})
    return out

def extract(segments, title, lexicon, subtitle='', blog_items=None):
    ss=sentences(segments); cues={j for i,s in enumerate(ss) if CUE.search(s['text']) for j in range(max(0,i-2),min(len(ss),i+3))}
    title_words={t.lemma_.lower() for t in nlp()(title) if t.is_alpha and not t.is_stop and t.lemma_.lower() not in FUNC|META}
    if len(subtitle.split()) <= 18 and not PROMO.search(subtitle):
        title_words |= {t.lemma_.lower() for t in nlp()(subtitle) if t.is_alpha and not t.is_stop and t.lemma_.lower() not in FUNC|META|{'learn','mean','other'}}
    documents=[]
    for path in TRANSCRIPT_DIR.glob('*.json'):
        try:
            data=json.loads(path.read_text())
            documents.append(' '.join(x.get('text','') for x in (data if isinstance(data,list) else data['segments'])).lower())
        except (OSError, ValueError, KeyError, TypeError):
            continue
    found=collections.defaultdict(list); words=collections.defaultdict(list)
    for si,s in enumerate(ss):
        tokens=[t for t in s['doc'] if not t.is_punct and not t.is_space]
        pairs=[(t.text.lower(),t.lemma_.lower()) for t in tokens]
        for i,t in enumerate(tokens):
            for key in set(pairs[i]):
                for w in lexicon.phrases.get(key,[]):
                    end=match_pattern(pairs[i:],w)
                    if end:
                        a=t.idx; b=tokens[i+end-1].idx+len(tokens[i+end-1]); found[w].append((si,a,b))
            if t.pos_ in {'NOUN','VERB','ADJ','ADV'} and not t.ent_type_ and t.lemma_.isalpha(): words[t.lemma_.lower()].append((si,t.idx,t.idx+len(t),t.pos_.lower()))
    heading=' '.join([title, subtitle if len(subtitle.split())<=18 and not PROMO.search(subtitle) else '']).lower()
    min_freq=max(1,len(documents)//3)
    candidates=[]; secondary=[]
    for w,occ in found.items():
        occ=list(dict.fromkeys(occ)); real=[x for x in w.split() if x not in PLACE]
        if w in STOP or all(x in FUNC for x in real): continue
        head=nlp()(real[0])[0]
        if head.lemma_.lower()!=real[0] and head.pos_ in {'VERB','AUX'}: continue
        entries,ec=lexicon.lookup(w); senses=[s for e in entries for s in e.get('s',[])]
        if senses and all('used other than' in s.get('g','').lower() for s in senses): continue
        tags={t for s in senses for t in s.get('t',[])}
        # A phrase quoted verbatim in the title/subtitle is the episode's topic even if made of stop words ("what now").
        title_phrase=len(occ)>=3 and not set(w.split())&PLACE and bool(re.search(r'\b'+re.escape(w)+r'\b',heading))
        title_hit=bool(set(real)&title_words) or title_phrase; cue=sum(si in cues for si,_,_ in occ)
        frequency=sum(bool(re.search(r'\b'+re.escape(w)+r'\b',doc)) for doc in documents)
        direct=sum(bool(CUE.search(ss[si]['text'])) for si,_,_ in occ)
        if frequency>=3 and direct<3: continue
        score=min(len(occ),8)+4*min(cue,3)+8*title_hit+6*title_phrase+3*bool(tags&IDIO)
        # Tier 1: a direct episode signal (title, or repeated near teaching cues).
        tier1=(title_hit or (tags&IDIO and cue>=2 and len(occ)>=3)) and score >= (8 if title_hit and blog_items else 16 if title_hit else 20)
        if tier1:
            candidates.append(dict(text=w,kind='expression',origin='transcript',score=score,occ=occ)); continue
        # Tier 2 ("also in this episode"): repeated, rare across episodes, near a teaching cue, tagged idiomatic,
        # and either a 3+ token idiom or a frequently repeated two-word one. Needs a content word.
        content=[x for x in real if x not in FUNC|WEAK]
        if (len(occ)>=2 and frequency<=min_freq and content and not w.startswith('be ') and w not in STOP
                and cue>=1 and tags&IDIO and (len(w.split())>=3 or len(occ)>=4)):
            secondary.append(dict(text=w,kind='expression',origin='transcript',score=min(len(occ),8)+2*min(cue,3)+3*bool(tags&IDIO),occ=occ))
    candidates.sort(key=lambda c:(-c['score'],-len(c['text']),c['text']))
    dedup=[]
    for c in candidates:
        real=set(c['text'].split())-PLACE
        if any(real <= set(x['text'].split())-PLACE or (set(x['text'].split())-PLACE <= real and len(real-(set(x['text'].split())-PLACE))<=1) for x in dedup): continue
        dedup.append(c)
    secondary.sort(key=lambda c:(-c['score'],-len(c['text']),c['text']))
    for c in secondary:
        real=set(c['text'].split())-PLACE
        if any(real & (set(x['text'].split())-PLACE) - FUNC - WEAK for x in dedup): continue
        c['secondary']=True; dedup.append(c)
        if sum(x.get('secondary',False) for x in dedup)>=4: break
    # Title words discussed explicitly as a part of speech get a focused sense.
    focus_title={t.lemma_.lower() for t in nlp()(title) if t.is_alpha and not t.is_stop and t.lemma_.lower() not in FUNC|META}
    focus_title |= {t.text.lower() for t in nlp()(title) if t.is_alpha and not t.is_stop}
    for w in focus_title:
        exact=[]
        for i, sentence in enumerate(ss):
            exact.extend((i, t.idx, t.idx+len(t), t.pos_.lower()) for t in sentence['doc'] if t.text.lower()==w)
        if exact: words[w]=exact
    for w in focus_title & words.keys():
        contexts=[]
        for i, a, b, _ in words[w]:
            window=' '.join(ss[j]['text'] for j in range(max(0,i-2),min(len(ss),i+3)))
            if re.search(r'\b(?:adjective|noun|adverb|(?<!phrasal )verb)\b',window,re.I):
                contexts.append(window)
        if not contexts: continue
        explicit=any(re.search(r'\b(?:word|adjective|noun|verb|adverb)\s+(?:is\s+)?[\"\']?'+re.escape(w)+r'\b|\b'+re.escape(w)+r'\b\s+(?:is|as)\s+(?:an?\s+)?(?:adjective|noun|verb|adverb)', s['text'], re.I) for s in ss)
        nearby_definition=any(re.search(r'\badjective\s+(?:meaning|means)\b', ss[j]['text'], re.I) for i,_,_,_ in words[w] for j in range(i,min(len(ss),i+4)))
        if not explicit and not nearby_definition: continue
        context=' '.join(contexts)
        for pos,pattern in [('adj','adjective')]:
            if not re.search(r'\b'+pattern+r'\b',context,re.I): continue
            entries,_=lexicon.lookup(w)
            if any(e.get('pos')==pos for e in entries):
                dedup.append(dict(text=w,display=f'{w} ({pos}.)',pos=pos,kind='word',origin='transcript',score=32,occ=[x[:3] for x in words[w] if ss[x[0]]['text'][x[1]:x[2]].lower()==w and any(t.idx==x[1] and t.i+1<len(ss[x[0]]['doc']) and ss[x[0]]['doc'][t.i+1].pos_ in {'NOUN','PROPN'} for t in ss[x[0]]['doc'])],context=context,focus=True)); break
    dedup.sort(key=lambda c:(c.get('secondary',False),-c['score']))
    advanced=[]
    for w,occ in words.items():
        if w in META|FUNC or w in title_words or w in focus_title or len(w)<4: continue
        if any(w in c['text'].split() for c in dedup): continue
        entries,ec=lexicon.lookup(w)
        if not ec or not entries: continue
        ranks=[int(ec[k]) for k in ('frq','bnc') if ec.get(k,'').isdigit() and int(ec[k])>0]
        if not ranks or not 4000 < min(ranks) < 30000: continue
        count=len(occ); cue=sum(x[0] in cues for x in occ)
        score=min(count,8)+min(cue,3)*0.5
        if count < 3 or cue < 2 or score < 6: continue
        if not any(CUE.search(ss[x[0]]['text']) for x in occ): continue
        if occ[0][3] not in {'adj', 'verb', 'noun'}: continue
        advanced.append(dict(text=w,kind='word',origin='transcript',score=score,occ=[x[:3] for x in occ],pos=occ[0][3]))
    advanced.sort(key=lambda c:(-c['score'],c['text']))
    result=[]
    for b in blog_items or []:
        w=b['text']; entries,_=lexicon.lookup(w); blog_pos='verb' if any(e.get('pos')=='verb' for e in entries) else None; b=dict(b,pos=blog_pos,kind='word' if ' ' not in w else 'expression',origin='blog',score=100,occ=[x[:3] for x in words.get(w,[])] if ' ' not in w else found.get(w,[])); result.append(b)
    seen={x['text'] for x in result}
    seen.update(w for x in result for w in x['text'].split())
    for c in dedup[:12]+advanced[:5]:
        if c['text'] not in seen and not (c['kind']=='word' and any(c['text'].startswith(x) or x.startswith(c['text']) for x in seen if ' ' not in x and len(x)>=5)) and not (c['origin']=='transcript' and set(c['text'].split()) & seen and any(x['origin']=='blog' for x in result)): result.append(c); seen.add(c['text'])
        if len(result)>=15: break
    return result,ss
