"""Extract only short educational snippets from WordPress posts."""
from html.parser import HTMLParser
import re
import json
import os
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

def fetch_blog(number):
    path = CACHE_DIR / 'blog' / f'{int(number)}.json'
    if path.exists(): return json.loads(path.read_text(encoding='utf8'))
    if os.environ.get('AEE_OFFLINE'): return None
    try:
        r=requests.get('https://www.allearsenglish.com/wp-json/wp/v2/posts',params={'search':f'AEE {number}','_fields':'id,date,link,title,content'},timeout=5); r.raise_for_status()
        for post in r.json():
            title=post.get('title',{}).get('rendered','')
            if re.search(r'\bAEE\s*'+str(int(number))+r'\b',title,re.I):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(post, ensure_ascii=False), encoding='utf8')
                return post
    except (requests.RequestException, ValueError, TypeError): pass
    return None
