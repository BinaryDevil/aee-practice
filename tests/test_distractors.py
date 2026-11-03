import json
from pipeline.enrich import content
from pipeline.paths import EPISODE_DIR

def test_pool_excludes_overlapping_definitions():
    path=EPISODE_DIR/'2713.json'
    if not path.exists(): return
    episode=json.loads(path.read_text()); items=episode['items']
    banned={item['text'].lower() for item in items}
    for item in items: banned.update(s.lower() for s in item['synonyms'])
    for d in episode['distractors']:
        assert d['text'].lower() not in banned
        words=content(d['meaningEn'])
        for item in items:
            other=content(item['meaningEn'])
            assert not words or not other or len(words&other)/min(len(words),len(other))<=0.5
