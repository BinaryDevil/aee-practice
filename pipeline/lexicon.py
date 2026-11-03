"""Lazy SQLite index of the source dictionaries; source files remain untouched."""
import csv, hashlib, json, os, re, sqlite3, tempfile
from pathlib import Path
from .paths import KAIKKI_PATH, ECDICT_PATH, LEXICON_DIR
from .config import IDIO, PLACE, STOP

PARTICLES = set('up down out off on over away back in through around along apart aside together'.split())

def valid_pattern(word):
    t = word.lower().split()
    return (len(t) >= 2 and len(t) <= 7 and len(word) <= 60 and bool(re.fullmatch(r"[a-zA-Z' -]+", word)) and t[0] not in PLACE and t[-1] not in PLACE and sum(x not in PLACE for x in t) >= 2 and word not in STOP)

def _cache_path():
    signature = '|'.join(f'{p.resolve()}:{p.stat().st_size}:{p.stat().st_mtime_ns}' for p in (KAIKKI_PATH,ECDICT_PATH))
    key = hashlib.sha256(('v4:'+signature).encode()).hexdigest()[:16]
    # AEE_DERIVED_CACHE permits read-only resource caches.
    root = Path(os.environ.get('AEE_DERIVED_CACHE', str(LEXICON_DIR)))
    return root / f'index-{key}.sqlite3'

class Lexicon:
    def __init__(self):
        path = _cache_path(); path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists(): self._build(path)
        self.db = sqlite3.connect(str(path))
        self._phrases = None
    def _build(self, path):
        tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
        db = sqlite3.connect(str(tmp))
        try:
            db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; CREATE TABLE k(w TEXT, data TEXT); CREATE TABLE e(w TEXT PRIMARY KEY, data TEXT); CREATE TABLE p(w TEXT PRIMARY KEY);')
            with KAIKKI_PATH.open(encoding='utf8') as f:
                batch=[]; phrases=set()
                for line in f:
                    try: e=json.loads(line); w=e['w'].lower()
                    except (ValueError,KeyError): continue
                    batch.append((w,line.strip()))
                    if valid_pattern(w) and (e.get('pos') in {'verb','phrase','prep_phrase','proverb','intj'} or any(IDIO.intersection(s.get('t',[])) for s in e.get('s',[]))): phrases.add(w)
                    if len(batch)>=10000: db.executemany('INSERT INTO k VALUES (?,?)',batch); batch=[]
                db.executemany('INSERT INTO k VALUES (?,?)',batch)
            with ECDICT_PATH.open(encoding='utf8',newline='') as f:
                batch=[]
                for row in csv.DictReader(f):
                    w=row['word'].lower()
                    if not w: continue
                    batch.append((w,json.dumps(row,ensure_ascii=False)))
                    if valid_pattern(w): phrases.add(w)
                    if len(batch)>=10000: db.executemany('INSERT OR IGNORE INTO e VALUES (?,?)',batch); batch=[]
                db.executemany('INSERT OR IGNORE INTO e VALUES (?,?)',batch)
            db.executemany('INSERT INTO p VALUES (?)',((w,) for w in phrases))
            db.execute('CREATE INDEX k_word ON k(w)'); db.commit(); db.close(); os.replace(tmp,path)
        finally:
            db.close()
            if tmp.exists(): tmp.unlink()
    def lookup(self, word):
        word=word.lower(); k=[json.loads(r[0]) for r in self.db.execute('SELECT data FROM k WHERE w=?',(word,))]
        e=self.db.execute('SELECT data FROM e WHERE w=?',(word,)).fetchone()
        return k, json.loads(e[0]) if e else {}
    @property
    def phrases(self):
        if self._phrases is None:
            self._phrases={}
            for (w,) in self.db.execute('SELECT w FROM p'):
                self._phrases.setdefault(w.split()[0],[]).append(w)
        return self._phrases
