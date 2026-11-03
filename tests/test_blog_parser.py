import json
import pytest
from pipeline.blog import parse_post

def test_blog(samples):
    path=samples/'aee2670_blog_wp_rest.json'
    if not path.exists(): pytest.skip('AEE blog sample is not available')
    items=parse_post(json.loads(path.read_text())[0])
    assert [x['text'] for x in items]==['reveal','share','disclose','divulge']
    assert all(x['teacherNote'] and x['examples'] for x in items)


def test_fetch_caches_success(tmp_path, monkeypatch):
    from pipeline import blog

    post = {'title': {'rendered': 'AEE 42: Example'}, 'content': {'rendered': ''}}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return [post]

    monkeypatch.setattr(blog, 'CACHE_DIR', tmp_path)
    monkeypatch.delenv('AEE_OFFLINE', raising=False)
    monkeypatch.setattr(blog.requests, 'get', lambda *args, **kwargs: Response())
    assert blog.fetch_blog(42) == post
    monkeypatch.setenv('AEE_OFFLINE', '1')
    assert blog.fetch_blog(42) == post
