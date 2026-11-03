"""Stream the Kaikki.org English Wiktionary dump (stdin) into a compact JSONL lexicon.

Usage:
  curl -sL https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl \
    | python pipeline/build_kaikki_mini.py cache/lexicon/kaikki_en_mini.jsonl

Output fields per line: w (headword), pos, s (senses: g gloss, t tags, ex examples,
syn synonyms, alt alt-of/form-of target), zh (Chinese translations), ipa, syn (entry synonyms).
Data: Wiktionary via Kaikki.org (CC BY-SA 4.0 / GFDL).
"""
import json
import sys

KEEP_TAGS = {'idiomatic', 'slang', 'informal', 'colloquial', 'figuratively', 'US', 'UK', 'formal',
             'dated', 'obsolete', 'archaic', 'rare', 'vulgar', 'offensive', 'transitive', 'intransitive',
             'form-of', 'alt-of', 'derogatory', 'humorous', 'nonstandard'}
SKIP_POS = {'name', 'character', 'symbol', 'prefix', 'suffix', 'infix', 'interfix', 'circumfix', 'punct', 'affix'}


def main(out_path):
    out = open(out_path, 'w', encoding='utf-8')
    n = k = 0
    for line in sys.stdin:
        n += 1
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('lang_code') != 'en' or e.get('pos') in SKIP_POS:
            continue
        w = e.get('word', '')
        if not w or len(w) > 60:
            continue
        senses = []
        for s in e.get('senses', []):
            if not s.get('glosses'):
                continue
            tags = s.get('tags', [])
            alt = None
            for key in ('alt_of', 'form_of'):
                if s.get(key):
                    alt = s[key][0].get('word')
            senses.append({
                'g': s['glosses'][-1],
                't': [t for t in tags if t in KEEP_TAGS],
                'ex': [x['text'] for x in s.get('examples', []) if x.get('text')][:2],
                'syn': [x['word'] for x in s.get('synonyms', []) if x.get('word')][:6],
                'alt': alt,
            })
        if not senses:
            continue
        zh = [t['word'] for t in e.get('translations', []) if t.get('code') in ('zh', 'cmn') and t.get('word')][:6]
        rec = {
            'w': w, 'pos': e.get('pos'), 's': senses[:8], 'zh': zh,
            'ipa': next((p.get('ipa') for p in e.get('sounds', []) if p.get('ipa')), None),
            'syn': [x['word'] for x in e.get('synonyms', []) if x.get('word')][:8],
        }
        out.write(json.dumps(rec, ensure_ascii=False) + '\n')
        k += 1
    print(n, k, file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'kaikki_en_mini.jsonl')
