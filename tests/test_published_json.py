import json
from pipeline.paths import EPISODE_DIR
from pipeline.config import PROMO

def test_published():
    for path in EPISODE_DIR.glob('[0-9]*.json'):
        data=json.loads(path.read_text()); assert 'segments' not in json.dumps(data)
        assert data['audioUrl'].startswith('https://traffic.megaphone.fm/')
        for item in data['items']:
            assert item['meaningEn'] and item['meaningZh']
            assert len(item['occurrences'])<=3
            for o in item['occurrences']:
                assert len(o['sentence'])<=240 and not PROMO.search(o['sentence'])
                assert o['sentence'][o['answerStart']:o['answerEnd']]==o['answer']
