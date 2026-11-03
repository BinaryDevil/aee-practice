"""Build static episode files from the official feed and cached transcripts."""
import argparse, datetime, json, sys
from . import rss, transcribe
from .blog import fetch_blog,parse_post
from .distractors import build_distractors
from .enrich import enrich
from .extract import extract
from .lexicon import Lexicon
from .mt import Translator
from .paths import EPISODE_DIR, DATA_DIR, FEED_CACHE

class _NoMT:
    failed=False
    def translate(self,_): return '-'  # first pass only needs the English gloss
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def indexes(eps):
    prepared=[]
    for f in EPISODE_DIR.glob('[0-9]*.json'):
        try:
            x=json.loads(f.read_text()); prepared.append({k:x.get(k) for k in ('number','guid','title','pubDate','durationSec')}|{'itemCount':len(x['items']),'hasBlog':bool(x.get('blogUrl')),'file':f'episodes/{x["number"]}.json'})
        except (OSError,ValueError,KeyError): continue
    prepared.sort(key=lambda x:x['number'],reverse=True)
    write(EPISODE_DIR/'index.json',{'schemaVersion':1,'generatedAt':now(),'episodes':prepared})
    write(DATA_DIR/'catalog.json',{'generatedAt':now(),'episodes':[{k:e.get(k) for k in ('number','title','pubDate','durationSec')} for e in eps[:60]]})
def build_one(ep,args,lex,mt):
    path=EPISODE_DIR/f"{ep['number']}.json"
    if path.exists() and args.skip_existing and not args.force: print(f"{ep['number']}: skipped"); return
    transcript=json.loads(open(args.transcript_file,encoding='utf8').read()) if args.transcript_file else transcribe.transcribe(ep,force=False)
    segs=transcript if isinstance(transcript,list) else transcript['segments']
    post=fetch_blog(ep['number']); blog=parse_post(post,lex) if post else []
    candidates,ss=extract(segs,ep['title'],lex,ep.get('subtitle',''),blog)
    # Sense hint: when two items are discussed in the same sentence ("hang on versus hold on"),
    # the hosts are contrasting near-synonyms, so prefer senses that overlap the partner's gloss.
    first={}
    for c in candidates:
        item=enrich(c,ss,lex,_NoMT())
        if item: first[c['text']]=item['meaningEn']
    for c in candidates:
        if c.get('teacherNote'): continue
        mine={i for i,*_ in c.get('occ',[])}
        c['senseHint']=' '.join(first[o['text']] for o in candidates if o is not c and o['text'] in first and mine & {i for i,*_ in o.get('occ',[])})
    items=[]
    budget=int(sum(len(s.get('text','').split()) for s in segs)*0.12)
    for c in candidates:
        item=enrich(c,ss,lex,mt)
        if item:
            kept=[]
            for occurrence in item['occurrences']:
                cost=len(occurrence['sentence'].split())
                if cost <= budget:
                    kept.append(occurrence); budget-=cost
            item['occurrences']=kept
            item['rank']=len(items)+1; items.append(item)
    result={'schemaVersion':1,**{k:ep.get(k) for k in ('number','guid','title','subtitle','pubDate','durationSec','audioUrl')},'episodeUrl':ep.get('link'),'blogUrl':post.get('link') if post else None,'transcriptSource':transcript.get('source','whisper:small.en') if isinstance(transcript,dict) else 'whisper:small.en','items':items,'distractors':build_distractors(items,lex,mt),'generator':{'version':'1.0.0','builtAt':now(),'lexicons':{'kaikki':'kaikki_en_mini.jsonl','ecdict':'ecdict.csv'},'mt':'opus-mt-en-zh (CTranslate2, offline)' if not args.no_mt else 'disabled'}}
    if mt.failed:
        # A corrupt or incompatible model can fail after earlier translations.
        for item in result['items']:
            for occurrence in item['occurrences']:
                occurrence['sentenceZh']=None; occurrence['sentenceZhSource']=None
        result['distractors']=[d for d in result['distractors'] if d['meaningZhSource']!='mt']
    write(path,result); print(f"\n{ep['number']}: {ep['title']} ({len(items)} items)")
    for x in items: print(f"{x['rank']:2}. {x['display']} [{x['score']}] — {x['meaningEn']}")
def main(argv=None):
    p=argparse.ArgumentParser(); group=p.add_mutually_exclusive_group(); group.add_argument('--number',nargs='+',type=int); group.add_argument('--latest',type=int,default=10)
    p.add_argument('--skip-existing',action='store_true'); p.add_argument('--force',action='store_true'); p.add_argument('--transcript-file'); p.add_argument('--no-mt',action='store_true'); args=p.parse_args(argv)
    if args.transcript_file and (not args.number or len(args.number)!=1): p.error('--transcript-file requires exactly one --number')
    # Prefer the available cache when offline; rss.fetch_feed refreshes it when absent.
    try: eps=rss.parse_feed(FEED_CACHE.read_bytes() if FEED_CACHE.exists() else rss.fetch_feed())
    except Exception as ex: print(f'Feed error: {ex}',file=sys.stderr); return 1
    selected=[rss.find_episode(n,eps) for n in args.number] if args.number else eps[:args.latest]
    missing=[n for n,e in zip(args.number or [],selected) if e is None]
    if missing: print(f'Episode numbers not in feed: {missing}',file=sys.stderr); return 1
    lex=Lexicon(); mt=Translator(not args.no_mt)
    failed=[]
    for ep in selected:
        try: build_one(ep,args,lex,mt)
        except Exception as e:  # one bad episode must not abort a --latest run
            print(f"{ep['number']}: FAILED: {e}",file=sys.stderr); failed.append(ep['number'])
    indexes(eps)
    if failed: print(f"Failed episodes: {failed}",file=sys.stderr)
    return 1 if failed and len(failed)==len(selected) else 0
if __name__=='__main__': sys.exit(main())
