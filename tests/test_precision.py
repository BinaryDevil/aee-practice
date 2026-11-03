"""Safety and precision checks against locally available transcripts."""
import json
import re

import pytest

from pipeline.config import META
from pipeline.enrich import clean_gloss, valid_gloss
from pipeline.paths import EPISODE_DIR, TRANSCRIPT_DIR


def published():
    return sorted(EPISODE_DIR.glob('[0-9]*.json'))


def test_excerpt_limits():
    for path in published():
        data = json.loads(path.read_text())
        total = 0
        for item in data['items']:
            assert len(item['occurrences']) <= 2
            for occurrence in item['occurrences']:
                assert len(occurrence['sentence']) <= 160
                total += len(occurrence['sentence'].split())
        transcript = TRANSCRIPT_DIR / path.name
        if transcript.exists():
            raw = json.loads(transcript.read_text())
            segments = raw if isinstance(raw, list) else raw['segments']
            assert total <= int(sum(len(s['text'].split()) for s in segments) * .12)


def test_real_transcript_precision(lexicon):
    paths = [p for p in published() if (TRANSCRIPT_DIR / p.name).exists()]
    if not paths:
        pytest.skip('No real transcripts available')
    for path in paths:
        data = json.loads(path.read_text())
        words = [i for i in data['items'] if i['kind'] == 'word' and i['origin'] != 'blog' and '(' not in i['display']]
        assert len(words) <= 5
        for item in data['items']:
            assert valid_gloss(item['meaningEn'])
            assert item['text'] not in META
            if item['meaningEnSource'] == 'kaikki':
                entries, _ = lexicon.lookup(item['text'])
                assert entries
                definitions = {clean_gloss(sense.get('g', '')) for entry in entries for sense in entry.get('s', [])}
                for entry in entries:
                    for sense in entry.get('s', []):
                        match = re.match(r'(?i)^synonym of\s+([^.(]+)', sense.get('g', ''))
                        target = sense.get('alt') or (match.group(1).strip() if match else None)
                        if target:
                            linked, _ = lexicon.lookup(target)
                            definitions.update(clean_gloss(other.get('g', '')) for e in linked for other in e.get('s', []))
                assert item['meaningEn'] in definitions
        stems = []
        for item in words:
            stem = re.sub(r'(?:ing|ed|ment|ness|s)$', '', item['text'])
            assert stem not in stems
            stems.append(stem)
        for d in data['distractors']:
            assert valid_gloss(d['meaningEn'])
        expected = {'2702': (6, ['have the last laugh', 'laugh off', "pull someone's leg"]),
                    '2715': (3, ['hang on']), '2670': (15, ['spill the beans'])}
        if path.stem in expected:
            limit, targets = expected[path.stem]
            assert set(targets) <= {i['text'] for i in data['items'][:limit]}


def test_sense_prior_and_gloss_validation():
    from pipeline.enrich import choose

    class Dictionary:
        def lookup(self, word):
            return ([{'pos': 'verb', 's': [
                {'g': 'To tease someone.', 't': ['idiomatic']},
                {'g': 'To extract money.', 't': ['idiomatic', 'obsolete']},
            ]}], {})

    assert choose('a phrase', Dictionary(), 'money extract')[1]['g'] == 'To tease someone.'
    assert not valid_gloss('To cause to exist in .')
    assert not valid_gloss('An empty () template.')
    assert valid_gloss('Synonym of take a stab at.')
