import json

import pytest

from pipeline.config import PROMO
from pipeline.enrich import enrich
from pipeline.extract import extract
from pipeline.mt import Translator
from pipeline.paths import TRANSCRIPT_DIR


@pytest.mark.parametrize('source', ['sample', 'real'])
def test_golden(samples, lexicon, source):
    path = samples / 'aee2713_whisper_small_en.json' if source == 'sample' else TRANSCRIPT_DIR / '2713.json'
    if not path.exists():
        pytest.skip(f'{source} transcript is not available')
    data = json.loads(path.read_text())
    candidates, ss = extract(data if isinstance(data, list) else data['segments'],
                             'Take a Crack at These English Phrases', lexicon)
    print(source, [(i + 1, c['text'], c['score']) for i, c in enumerate(candidates)])
    for word in ('take a crack at', 'crack up', 'crack a joke'):
        assert any(c['text'] == word for c in candidates[:8]), word
        print(word, next(i + 1 for i, c in enumerate(candidates) if c['text'] == word))
    focus = next(c for c in candidates[:8] if c['text'] == 'crack' and c.get('pos') == 'adj')
    print('crack (adj.)', candidates.index(focus) + 1)
    item = enrich(focus, ss, lexicon, Translator(False))
    assert any(x in item['meaningEn'].lower() for x in ('skilled', 'excellent', 'expert', 'first-rate', 'competent'))
    for candidate in candidates:
        item = enrich(candidate, ss, lexicon, Translator(False))
        if item:
            assert all(not PROMO.search(o['sentence']) for o in item['occurrences'])
