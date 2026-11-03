from pipeline.config import PROMO
from pipeline.extract import sentences

def test_filter():
    segments=[{'text':x,'start':0,'end':1} for x in ('allearsenglish.com slash vocabulary','Your fluency score is here','Downloaded more than 200 million times','This is a useful sentence.')]
    assert len(sentences(segments))==1
    assert not PROMO.search(sentences(segments)[0]['text'])
