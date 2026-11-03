"""Filesystem locations. Everything under CACHE_DIR is git-ignored (audio, transcripts, lexicons, models)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(os.environ.get('AEE_CACHE_DIR', ROOT / '.cache'))
AUDIO_DIR = CACHE_DIR / 'audio'
TRANSCRIPT_DIR = CACHE_DIR / 'transcripts'
LEXICON_DIR = CACHE_DIR / 'lexicon'
MODEL_DIR = CACHE_DIR / 'models'
FEED_CACHE = CACHE_DIR / 'feed.xml'
DATA_DIR = ROOT / 'data'
EPISODE_DIR = DATA_DIR / 'episodes'
OVERRIDES_DIR = ROOT / 'overrides'
KAIKKI_PATH = LEXICON_DIR / 'kaikki_en_mini.jsonl'
ECDICT_PATH = LEXICON_DIR / 'ecdict.csv'
MT_MODEL_PATH = MODEL_DIR / 'opus-mt-en-zh-ct2'

FEED_URL = os.environ.get('AEE_FEED_URL', 'https://feeds.megaphone.fm/allearsenglish')
WHISPER_MODEL = 'small.en'  # never base/tiny: base.en hallucinated badly in testing
