"""Optional offline English->Chinese machine translation (opus-mt-en-zh via CTranslate2).

Output is always labelled as machine translation in the app. A translation that looks
malformed is dropped (None) instead of being published.
"""
import json
import os
import re
from pathlib import Path

from .paths import CACHE_DIR, MT_MODEL_PATH

CJK = re.compile(r'[\u4e00-\u9fff]')


def looks_ok(source, zh):
    if not zh or '\u2581' in zh or not CJK.search(zh):
        return False
    # Latin words in the output must come from the source (names such as "Aubrey" are fine);
    # invented English words are a sign of a broken model or a derailed decode.
    src_words = {w.lower() for w in re.findall(r'[A-Za-z]+', source)}
    return all(w.lower() in src_words for w in re.findall(r'[A-Za-z]{3,}', zh))


class Translator:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.model = None
        self.failed = False  # True only when the model itself is missing or broken
        self.path = Path(os.environ.get('AEE_DERIVED_CACHE', str(CACHE_DIR))) / 'mt_cache.json'
        try:
            self.cache = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.cache = {}

    def _load(self):
        import ctranslate2
        import sentencepiece as spm
        self.model = ctranslate2.Translator(str(MT_MODEL_PATH), device='cpu', inter_threads=1, intra_threads=4)
        self.src = spm.SentencePieceProcessor(model_file=str(MT_MODEL_PATH / 'source.spm'))
        self.tgt = spm.SentencePieceProcessor(model_file=str(MT_MODEL_PATH / 'target.spm'))
        probe = 'When I get nervous, I sometimes tell a joke.'
        if not looks_ok(probe, self._run(probe)):
            raise RuntimeError('MT model self-check failed (bad conversion or quantization?)')

    def _run(self, text):
        tokens = self.src.encode(text, out_type=str) + ['</s>']
        result = self.model.translate_batch([tokens], beam_size=4, max_decoding_length=256)[0].hypotheses[0]
        return self.tgt.decode([x for x in result if x not in ('</s>', '<pad>')]).strip()

    def translate(self, text):
        if not self.enabled or not text or self.failed:
            return None
        if text in self.cache and looks_ok(text, self.cache[text]):
            return self.cache[text]
        try:
            if self.model is None:
                if not (MT_MODEL_PATH / 'model.bin').exists():
                    raise RuntimeError(f'MT model not found at {MT_MODEL_PATH}')
                self._load()
            zh = self._run(text)
        except (ImportError, OSError, RuntimeError, ValueError) as ex:
            print(f'MT disabled: {ex}')
            self.failed = True
            return None
        if not looks_ok(text, zh):
            return None
        self.cache[text] = zh
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.cache, ensure_ascii=False))
        return zh
