import json
from pipeline.paths import EPISODE_DIR, TRANSCRIPT_DIR
from pipeline.config import PROMO

def test_published():
    for path in EPISODE_DIR.glob('[0-9]*.json'):
        data=json.loads(path.read_text()); assert 'segments' not in json.dumps(data)
        assert data['audioUrl'].startswith('https://traffic.megaphone.fm/')
        for item in data['items']:
            assert item['meaningEn'] and item['meaningZh']
            assert len(item['occurrences'])<=2
            for o in item['occurrences']:
                assert len(o['sentence'])<=160 and not PROMO.search(o['sentence'])
                assert o['sentence'][o['answerStart']:o['answerEnd']]==o['answer']

def test_excerpt_budget():
    # Copyright: published context sentences stay a small fraction of the episode (<=12% of words).
    for path in EPISODE_DIR.glob('[0-9]*.json'):
        data=json.loads(path.read_text()); t=TRANSCRIPT_DIR/f"{data['number']}.json"
        if not t.exists(): continue
        raw=json.loads(t.read_text()); segs=raw if isinstance(raw,list) else raw['segments']
        total=sum(len(s['text'].split()) for s in segs)
        used=sum(len(o['sentence'].split()) for i in data['items'] for o in i['occurrences'])
        assert used<=0.12*total, (data['number'],used,total)
