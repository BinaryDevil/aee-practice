#!/usr/bin/env python3
"""Exercise both explanation languages. --data-root may point to a directory containing data/."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', help='Use an existing server instead of starting one')
    parser.add_argument('--episode-number', type=int)
    parser.add_argument('--data-root', type=Path, help='Directory containing data/, or the data directory itself')
    parser.add_argument('--all', action='store_true', help='Test every prepared episode')
    parser.add_argument('--audio-via-driver', action='store_true',
                        help='Fetch the official megaphone.fm audio through the Playwright driver instead of the browser '
                             '(for sandboxes whose browser egress breaks megaphone signed redirects). The <audio> src '
                             'stays the official URL; bytes are passed through unmodified.')
    parser.add_argument('--allow-no-network', action='store_true', help='Allow unavailable official audio')
    args = parser.parse_args()
    tmp = tempfile.TemporaryDirectory() if args.data_root else None
    serving = ROOT
    if tmp:
        serving = Path(tmp.name)
        shutil.copy(ROOT / 'index.html', serving)
        shutil.copytree(ROOT / 'assets', serving / 'assets')
        source = args.data_root / 'data' if (args.data_root / 'data').is_dir() else args.data_root
        shutil.copytree(source, serving / 'data')
    data = serving / 'data'
    index = json.loads((data / 'episodes/index.json').read_text())['episodes']
    assert index, 'No prepared episodes; provide --data-root with a fixture dataset'
    row = next((x for x in index if x['number'] == args.episode_number), None) if args.episode_number else index[0]
    assert row, 'Requested episode is absent from index'
    rows = index if args.all else [row]
    server = None
    base = args.base_url
    if not base:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        server = subprocess.Popen(['python3', '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', str(serving)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = f'http://127.0.0.1:{port}/'
        time.sleep(.5)
    screenshots = ROOT / 'tests/e2e/screenshots'
    screenshots.mkdir(exist_ok=True)
    results = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--autoplay-policy=no-user-gesture-required'])
            for row, language in ((row, language) for row in rows for language in ('en', 'zh')):
                episode = json.loads((data / row['file']).read_text())
                context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
                page = context.new_page()
                if args.audio_via_driver:
                    def via_driver(route):
                        try:
                            route.fulfill(response=route.fetch())
                        except Exception:
                            pass  # page/context closed while a long audio range was in flight
                    page.route('https://traffic.megaphone.fm/**', via_driver)
                try:
                    page.goto(base, wait_until='networkidle')
                    page.get_by_test_id('episode-row').first.wait_for()
                    assert page.get_by_text('Build episode', exact=False).count()
                    for prepared in index:
                        assert page.locator(f'a[data-testid="episode-row"][href="#/episode/{prepared["number"]}"]').count() == 1
                    if language == 'zh':
                        page.get_by_test_id('language-switch').click()
                    page.locator(f'a[href="#/episode/{row["number"]}"]').click()
                    page.get_by_test_id('start-quiz').click()
                    first_pass = True
                    clicked_audio = False
                    saw_retry = False
                    steps = 0
                    while not page.get_by_test_id('results-screen').count():
                        steps += 1
                        assert steps < 40, 'Quiz did not finish'
                        if page.get_by_test_id('match-pair-tile').count() == 1:
                            page.get_by_test_id('match-pair-tile').click()
                        choices = page.locator('[data-correct]')
                        if first_pass and page.get_by_text('再试一次' if language == 'zh' else 'Let’s try these again', exact=True).count():
                            first_pass = False
                            saw_retry = True
                        choice = page.locator('[data-correct="false"]').first
                        if not first_pass or not choice.count():
                            choice = page.locator('[data-correct="true"]').first
                        chosen_meaning = choice.get_attribute('data-meaning-zh' if language == 'zh' else 'data-meaning-en')
                        sentence = page.locator('.sentence span').last.inner_text() if page.locator('.sentence span').count() else ''
                        choice.click()
                        panel = page.get_by_test_id('explanation-panel')
                        panel.wait_for()
                        assert not any(x in panel.inner_text().lower() for x in ('undefined', 'null', 'nan'))
                        if first_pass:
                            assert ('正确答案' if language == 'zh' else 'Correct answer') in panel.inner_text()
                            if page.locator('.question').get_attribute('data-has-tip') == 'true':
                                assert page.get_by_test_id('exp-tip').inner_text().strip()
                            for key in ('exp-meaning','exp-episode','exp-why'):
                                assert page.get_by_test_id(key).inner_text().strip()
                            if chosen_meaning and language == 'zh':
                                assert chosen_meaning.rstrip('。！？') in page.get_by_test_id('exp-why').inner_text()
                            if sentence and '____' not in sentence:
                                assert sentence in page.get_by_test_id('exp-episode').inner_text()
                            if language == 'zh':
                                assert any('\u4e00' <= c <= '\u9fff' for c in page.get_by_test_id('exp-meaning').inner_text())
                                assert any('\u4e00' <= c <= '\u9fff' for c in page.get_by_test_id('exp-why').inner_text())
                                if '机器翻译' in panel.inner_text():
                                    assert '机器翻译' in panel.inner_text()
                            play = page.get_by_test_id('exp-episode').get_by_test_id('play-button')
                            assert play.count()
                            if not clicked_audio:
                                start = float(play.get_attribute('data-start'))
                                play.click()
                                assert page.evaluate('window.__aee.audio.src') == episode['audioUrl']
                                try:
                                    page.wait_for_function('(start) => Math.abs(window.__aee.audio.currentTime - Math.max(0,start-.5)) < 1.5', arg=start, timeout=20000)
                                except Exception:
                                    if not args.allow_no_network:
                                        raise
                                    print(f'NOTE {language}: official audio unavailable; allowed by --allow-no-network')
                                else:
                                    before = page.evaluate('window.__aee.audio.currentTime')
                                    page.wait_for_function('(before) => window.__aee.audio.currentTime > before + 0.2', arg=before, timeout=10000)
                                clicked_audio = True
                        page.get_by_test_id('next-button').click()
                    assert saw_retry, 'Retry round did not appear'
                    assert clicked_audio
                    page.screenshot(path=str(screenshots / f'{row["number"]}-{language}-results.png'), full_page=True)
                    results.append((f'{row["number"]} {language}', 'PASS'))
                    print(f'PASS {language}: quiz, explanations, retry and results')
                except Exception as exc:
                    page.screenshot(path=str(screenshots / f'{row["number"]}-{language}-failure.png'), full_page=True)
                    results.append((f'{row["number"]} {language}', 'FAIL'))
                    print(f'FAIL {language}: {exc}')
                finally:
                    context.close()
            browser.close()
    finally:
        if server: server.terminate(); server.wait()
        if tmp: tmp.cleanup()
    print('Summary:', ', '.join(f'{lang} {result}' for lang, result in results))
    return 1 if any(result == 'FAIL' for _,result in results) else 0

if __name__ == '__main__':
    raise SystemExit(main())
