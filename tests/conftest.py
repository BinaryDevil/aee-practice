import os
from pathlib import Path
import pytest
from pipeline.paths import KAIKKI_PATH,ECDICT_PATH

@pytest.fixture(scope='session')
def samples():
    return Path(os.environ.get('AEE_SAMPLES_DIR',Path(__file__).resolve().parents[2]/'samples'))
@pytest.fixture(scope='session')
def lexicon():
    if not KAIKKI_PATH.exists() or not ECDICT_PATH.exists(): pytest.skip('large lexicon cache is not available')
    from pipeline.lexicon import Lexicon
    return Lexicon()
