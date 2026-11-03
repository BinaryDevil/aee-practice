"""Select dictionary senses, translations and short timed cloze contexts."""
import json, re
from .config import IDIO, FUNC, PROMO
from .paths import OVERRIDES_DIR
from spacy.lang.en.stop_words import STOP_WORDS

def content(s): return {w for w in re.findall(r"[a-z]+",s.lower()) if w not in FUNC and w not in STOP_WORDS and len(w)>2}
def clean_gloss(s):
    s=re.sub(r'\([^)]*\)', '',s); s=re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]',lambda m:m.group(2) or m.group(1),s)
    return re.sub(r'\s+([.,;:])', r'\1', re.sub(r'\s+',' ',s)).strip(' ;,')
def clean_zh(s):
    lines=s.replace('\\n','\n').splitlines(); parts=[]
    for line in lines:
        if re.match(r'\s*\[',line): continue
        line=re.sub(r'^\s*(?:n|v|vi|vt|adj|adv|a|prep|pron|conj|int|pl)\.\s*','',line,flags=re.I)
        parts += [x.strip() for x in re.split('[,，;；]',line) if x.strip()]
    return '；'.join(parts[:3])
def inflections(text,lexicon):
    head,*rest=text.split(); _,ec=lexicon.lookup(head); forms={'base':text}
    names={'p':'past','d':'pp','i':'ing','3':'s3','s':'plural'}
    for item in ec.get('exchange','').split('/'):
        if ':' in item:
            key,value=item.split(':',1)
            if key in names and value: forms[names[key]]=' '.join([value.split(',')[0]]+rest)
    return forms

def valid_gloss(gloss):
    """Reject unresolved dictionary templates and inflection-only entries."""
    return bool(gloss and not re.search(
        r'\(\s*\)|\b(?:of|in|to|with|for|from)\s+[.,;:]|'
        r'(?i:^(?:alternative form|form|plural|simple past|past tense|present participle) of)\b', gloss))


def choose(text, lexicon, context='', pos=None, follow=True, note=''):
    entries, ec = lexicon.lookup(text)
    options = []
    ctx = content(context) - content(text)
    for e in entries:
        if pos and e.get('pos') != pos:
            continue
        for index, sense in enumerate(e.get('s', [])):
            gloss = sense.get('g', '')
            if not valid_gloss(gloss) or 'used other than' in gloss.lower():
                continue
            tags = set(sense.get('t', []))
            overlap = len(content(gloss) & ctx)
            points = min(overlap, 3) * 1.5 - index * 1.2 + 6 * len(content(gloss) & content(note))
            information = {'information', 'knowledge', 'known', 'tell', 'communicate'}
            if content(note) & information and content(gloss) & information:
                points += 5
            points -= 12 * bool(tags & {'dated', 'obsolete', 'archaic', 'rare', 'regional'})
            points -= 3 * bool(tags & {'UK', 'US'})
            points -= 3 * bool(tags - IDIO - {'transitive', 'intransitive', 'countable', 'uncountable', 'comparative', 'superlative'})
            points += bool(' ' in text and tags & IDIO)
            options.append((points, e, sense))
    if not options and pos:
        return choose(text, lexicon, context, follow=follow, note=note)
    if not options:
        return {}, {}, ec
    _, entry, sense = max(options, key=lambda x: x[0])
    target = sense.get('alt')
    if not target:
        match = re.match(r'(?i)^synonym of\s+([^.(]+)', sense.get('g', ''))
        target = match.group(1).strip() if match else None
    if follow and target and target.lower() != text.lower():
        _, linked, _ = choose(target, lexicon, context, follow=False)
        if linked and not re.match(r'(?i)^synonym of\b', linked.get('g', '')):
            sense = dict(linked, syn=list(set(sense.get('syn', []) + [target])))
    return entry, sense, ec

def enrich(candidate, ss, lexicon, mt):
    text=candidate['text']; occ=candidate.get('occ',[])
    indices={j for i,_,_ in occ for j in (range(max(0,i-2),min(len(ss),i+3)) if candidate['kind']=='expression' or candidate.get('focus') else [i])}
    context=candidate.get('teacherNote','')+' '+candidate.get('context','')+' '+' '.join(ss[i]['text'] for i in sorted(indices))
    e,s,ec=choose(text,lexicon,context,candidate.get('pos'),note=candidate.get('teacherNote',''))
    gloss=clean_gloss(s.get('g','')) or clean_gloss(ec.get('definition','').split('\n')[0])
    if not valid_gloss(gloss): gloss=''
    source='kaikki' if s else 'ecdict'
    if not gloss and ' ' in text:
        for i, _, _ in occ:
            nearby=' '.join(ss[j]['text'] for j in range(max(0,i-2),i+1))
            for match in re.finditer(r'\bmeans? (to [^.!?]{3,90})', nearby, re.I):
                explanation=match.group(1).strip()
                if content(explanation) & content(text):
                    gloss=explanation.capitalize()+'.'; source='transcript'; break
            if gloss: break
    if not gloss: return None
    overrides=json.loads((OVERRIDES_DIR/'zh.json').read_text())
    override=overrides.get(candidate.get('display',text)) or overrides.get(text)
    ec_zh=clean_zh(ec.get('translation','')); kz='；'.join(e.get('zh',[])[:2]); multi=' ' in text
    zh=override or (ec_zh if not multi else '') or kz or mt.translate(gloss) or ec_zh
    if not zh: return None
    zsource='override' if override else 'ecdict' if not multi and ec_zh else 'kaikki' if kz else 'mt' if multi and zh!=ec_zh else 'ecdict'
    forms=inflections(text,lexicon); occurrences=[]
    # Prefer actual examples to discussion of the expression.
    ordered=sorted(occ,key=lambda x: bool(re.search(r'\b(?:means?|meaning|idiom|phrase|expression|adjective|the next one)\b',ss[x[0]]['text'],re.I)))
    for i,a,b in ordered:
        if ss[i]['start'] < 20: continue
        st=ss[i]; sentence=st['text']; left=max(0, a-70); right=min(len(sentence), left+158)
        if left:
            left=sentence.find(' ', left, a)+1 or left
        if right < len(sentence):
            right=sentence.rfind(' ', b, right) or right
        prefix='…' if left else ''; suffix='…' if right<len(sentence) else ''
        sentence=prefix+sentence[left:right].strip()+suffix; a=a-left+len(prefix); b=b-left+len(prefix)
        if a<0 or b>len(sentence) or PROMO.search(sentence): continue
        if any(o['sentence']==sentence and o['answerStart']==a for o in occurrences): continue
        answer=sentence[a:b]; form=next((k for k,v in forms.items() if answer.lower()==v.lower()),'other')
        trans=mt.translate(sentence)
        occurrences.append({'start':st['start'],'end':st['end'],'sentence':sentence,'sentenceZh':trans,'sentenceZhSource':'mt' if trans else None,'answer':answer,'answerStart':a,'answerEnd':b,'answerForm':form})
        if len(occurrences)==2: break
    synonyms=list(dict.fromkeys(e.get('syn',[])+s.get('syn',[])))
    return {'id':re.sub(r'[^a-z0-9]+','-',candidate.get('display',text).lower()).strip('-'),'text':text,'display':candidate.get('display',text),'kind':candidate['kind'],'origin':candidate['origin'],'score':candidate['score'],'pos':candidate.get('pos') or e.get('pos') or ('phrase' if multi else 'noun'),'ipa':e.get('ipa') or ec.get('phonetic') or None,'tags':s.get('t',[]),'meaningEn':gloss,'meaningEnSource':source,'meaningZh':zh,'meaningZhSource':zsource,'meaningZhAlt':ec_zh if multi and ec_zh and zh!=ec_zh and set(re.findall(r'[\u4e00-\u9fff]',ec_zh)) & set(re.findall(r'[\u4e00-\u9fff]',zh)) else None,'teacherNote':candidate.get('teacherNote') or None,'occurrences':occurrences,'inflections':forms,'examples':(candidate.get('examples') or s.get('ex',[]))[:2],'synonyms':synonyms,'concept':bool(candidate.get('concept'))}
