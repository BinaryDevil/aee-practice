from pipeline.extract import match_pattern
from pipeline.lexicon import valid_pattern

def test_separable():
    assert match_pattern([('cracked','crack'),('me','I'),('up','up')],'crack up')==3

def test_placeholder():
    assert match_pattern([('give','give'),('my','my'),('old','old'),('friend','friend'),('up','up')],'give someone up')==5
    assert not valid_pattern('someone give up')
    assert not valid_pattern('give up someone')
    assert not valid_pattern('give someone')

def test_stop():
    assert not valid_pattern('you know')
    assert not valid_pattern('need to')
