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


def test_fetch_warns_and_does_not_cache_failures(tmp_path, monkeypatch, capsys):
    from pipeline import blog

    calls = []

    def boom(*args, **kwargs):
        calls.append(kwargs)
        raise blog.requests.ConnectionError('blocked')

    monkeypatch.setattr(blog, 'CACHE_DIR', tmp_path)
    monkeypatch.delenv('AEE_OFFLINE', raising=False)
    monkeypatch.setattr(blog.requests, 'get', boom)
    monkeypatch.setattr(blog.time, 'sleep', lambda s: None)
    assert blog.fetch_blog(42) is None
    assert len(calls) == blog.ATTEMPTS
    assert calls[0]['headers']['User-Agent'].startswith('aee-practice/')
    err = capsys.readouterr().err
    assert 'AEE 42' in err and 'giving up' in err
    assert not (tmp_path / 'blog' / '42.json').exists()


def test_skip_existing_rebuilds_when_post_appears(tmp_path, monkeypatch):
    import argparse, json
    from pipeline import build

    (tmp_path / '7.json').write_text(json.dumps({'number': 7, 'blogUrl': None, 'items': []}))
    (tmp_path / '8.json').write_text(json.dumps({'number': 8, 'blogUrl': 'https://x/aee-8', 'items': []}))
    monkeypatch.setattr(build, 'EPISODE_DIR', tmp_path)
    fetched = []
    monkeypatch.setattr(build, 'fetch_blog', lambda n: fetched.append(n) or {'link': f'https://x/aee-{n}'})

    class Rebuilt(Exception):
        pass

    def transcribe(ep, force=False):
        raise Rebuilt(ep['number'])

    monkeypatch.setattr(build.transcribe, 'transcribe', transcribe)
    args = argparse.Namespace(skip_existing=True, force=False, transcript_file=None, no_mt=True)

    with pytest.raises(Rebuilt):
        build.build_one({'number': 7}, args, None, None)
    build.build_one({'number': 8}, args, None, None)  # already has a blog: skipped, no API call
    assert fetched == [7]

    monkeypatch.setattr(build, 'fetch_blog', lambda n: None)
    build.build_one({'number': 7}, args, None, None)  # still no post: skipped
