"""Extract only short educational snippets from WordPress posts."""
from html.parser import HTMLParser
import re
import json
import os
import sys
import time
from .paths import CACHE_DIR
import requests

class Blocks(HTMLParser):
    def __init__(self): super().__init__(); self.blocks=[]; self.tag=None; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('h2','h3','h4','p','li') and self.tag is None: self.tag=tag; self.parts=[]
    def handle_data(self,data):
        if self.tag: self.parts.append(data)
    def handle_endtag(self,tag):
        if tag==self.tag:
            text=' '.join(''.join(self.parts).split())
            if text: self.blocks.append((tag,text))
            self.tag=None

def parse_post(post, lexicon=None):
    html=post.get('content',{}).get('rendered','') if isinstance(post,dict) else post
    p=Blocks(); p.feed(html); items=[]; current=None; examples=False; roleplay=False
    for tag,text in p.blocks:
        if tag in ('h2','h3','h4'):
            m=re.match(r'^(?:#\s*\d+|Tip\s+\d+)\s*:\s*(.+)',text,re.I)
            if m:
                w=m.group(1).strip(' \"\'“”‘’').lower(); known=bool(lexicon.lookup(w)[0] or lexicon.lookup(w)[1]) if lexicon else len(w.split())<=6
                current={'text':w,'teacherNote':'','examples':[],'concept':len(w.split())>6 or not known}; items.append(current); examples=False; roleplay=False
            else: current=None; roleplay='roleplay' in text.lower()
            continue
        if roleplay:
            for item in items:
                if re.search(r'\b'+re.escape(item['text'])+r'\b',text,re.I) and len(item['examples'])<2: item['examples'].append(text)
        if current is None: continue
        if re.match(r'^examples?\s*:',text,re.I): examples=True; continue
        if examples:
            if tag=='li' and len(current['examples'])<2: current['examples'].append(text)
        elif tag=='p' and len(re.split(r'(?<=[.!?])\s+',current['teacherNote'].strip()))<2:
            current['teacherNote']=(current['teacherNote']+' '+text).strip()
    for item in items: item['teacherNote']=' '.join(re.split(r'(?<=[.!?])\s+',item['teacherNote'])[:2])
    return items

API_URL = 'https://www.allearsenglish.com/wp-json/wp/v2/posts'
USER_AGENT = 'aee-practice/1.0 (fan study app; +https://github.com/BinaryDevil/aee-practice)'
ATTEMPTS = 3

def _warn(msg): print(f'blog: {msg}', file=sys.stderr)

def fetch_blog(number):
    """Return the episode's WordPress post, or None. Hits are cached; misses are not, so a later run can find a new post."""
    number = int(number)
    path = CACHE_DIR / 'blog' / f'{number}.json'
    if path.exists(): return json.loads(path.read_text(encoding='utf8'))
    if os.environ.get('AEE_OFFLINE'): return None
    params = {'search': f'AEE {number}', '_fields': 'id,date,link,title,content'}
    for attempt in range(1, ATTEMPTS + 1):
        try:
            r = requests.get(API_URL, params=params, headers={'User-Agent': USER_AGENT}, timeout=20)
            r.raise_for_status()
            posts = r.json()
            break
        except (requests.RequestException, ValueError) as e:
            _warn(f'AEE {number}: attempt {attempt}/{ATTEMPTS} failed: {e}')
            if attempt < ATTEMPTS: time.sleep(2 * attempt)
    else:
        _warn(f'AEE {number}: giving up; building without blog items')
        return None
    if not isinstance(posts, list):
        _warn(f'AEE {number}: unexpected API response ({type(posts).__name__})'); return None
    for post in posts:
        title = (post.get('title') or {}).get('rendered', '') if isinstance(post, dict) else ''
        if re.search(r'\bAEE\s*' + str(number) + r'\b', title, re.I):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(post, ensure_ascii=False), encoding='utf8')
            return post
    return None
