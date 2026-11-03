"""Official All Ears English RSS (Megaphone) -> episode metadata."""
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from .paths import FEED_CACHE, FEED_URL

ITUNES = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'
UA = {'User-Agent': 'aee-practice-builder/1.0 (+personal study app)'}


def fetch_feed(max_age_s=3600, url=FEED_URL):
    """Download the feed (cached on disk for max_age_s)."""
    FEED_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if FEED_CACHE.exists() and time.time() - FEED_CACHE.stat().st_mtime < max_age_s:
        return FEED_CACHE.read_bytes()
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    FEED_CACHE.write_bytes(r.content)
    return r.content


def _duration(s):
    if not s:
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    parts = [int(p) for p in s.split(':') if p.isdigit()]
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec or None


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter('item'):
        title = (it.findtext('title') or '').strip()
        num = it.findtext(ITUNES + 'episode')
        m = re.match(r'^AEE\s*(\d+)\s*[:\-]\s*(.*)$', title)
        if m:
            num = num or m.group(1)
            clean = m.group(2).strip()
        else:
            clean = title
        if not num or not str(num).strip().isdigit():
            continue
        # Only the main "AEE nnnn" series is numbered consistently.
        if not m:
            continue
        enc = it.find('enclosure')
        pub = it.findtext('pubDate')
        try:
            pub_iso = parsedate_to_datetime(pub).astimezone().strftime('%Y-%m-%dT%H:%M:%SZ') if pub else None
            pub_iso = parsedate_to_datetime(pub).strftime('%Y-%m-%dT%H:%M:%S%z') if pub else None
        except (TypeError, ValueError):
            pub_iso = None
        out.append({
            'number': int(num),
            'title': clean,
            'fullTitle': title,
            'subtitle': (it.findtext(ITUNES + 'subtitle') or '').strip(),
            'guid': (it.findtext('guid') or '').strip(),
            'pubDate': pub_iso,
            'durationSec': _duration(it.findtext(ITUNES + 'duration')),
            'audioUrl': enc.get('url') if enc is not None else None,
            'link': (it.findtext('link') or '').strip() or None,
        })
    # newest first, de-duplicate by number (keep first = newest)
    seen, uniq = set(), []
    for e in out:
        if e['number'] in seen:
            continue
        seen.add(e['number'])
        uniq.append(e)
    uniq.sort(key=lambda e: e['number'], reverse=True)
    return uniq


def episodes(max_age_s=3600):
    return parse_feed(fetch_feed(max_age_s))


def find_episode(number, eps=None):
    eps = eps if eps is not None else episodes()
    for e in eps:
        if e['number'] == int(number):
            return e
    return None
