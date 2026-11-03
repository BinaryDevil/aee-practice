"""Download the official MP3 (cache only, never committed) and transcribe it locally with
faster-whisper `small.en` (int8, CPU, VAD). Output is cached in .cache/transcripts/<n>.json."""
import json
import os
import subprocess
import time

import numpy as np
import requests

from .paths import AUDIO_DIR, TRANSCRIPT_DIR, WHISPER_MODEL
from .rss import UA

_model = None


def download_audio(ep):
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIO_DIR / f"{ep['number']}.mp3"
    if path.exists() and path.stat().st_size > 100_000:
        return path
    tmp = path.with_suffix('.part')
    with requests.get(ep['audioUrl'], headers=UA, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, 'wb') as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.rename(path)
    return path


def decode_pcm(path):
    raw = subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(path), '-ar', '16000', '-ac', '1',
                          '-f', 's16le', '-'], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        assert 'base' not in WHISPER_MODEL and 'tiny' not in WHISPER_MODEL
        _model = WhisperModel(WHISPER_MODEL, device='cpu', compute_type='int8',
                              cpu_threads=int(os.environ.get('WHISPER_THREADS', os.cpu_count() or 4)))
    return _model


ATTEMPTS = [
    dict(beam_size=1, vad_filter=True),
    dict(beam_size=1, vad_filter=False),
    dict(beam_size=5, vad_filter=True, temperature=0.0),
]


def _seg(s):
    return {'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip(),
            'avg_logprob': round(s.avg_logprob, 3), 'no_speech_prob': round(s.no_speech_prob, 3),
            'words': [[round(w.start, 2), round(w.end, 2), w.word] for w in (s.words or [])]}


# Healthy AEE transcripts run ~140-160 words/min; a degraded decode was observed at ~120.
MIN_WORDS_PER_MIN = 130


def coverage_ok(segments, duration_sec):
    """Podcast speech runs ~150 words/min; a derailed decode yields far fewer words."""
    words = sum(len(s['text'].split()) for s in segments)
    return duration_sec <= 0 or words / (duration_sec / 60) >= MIN_WORDS_PER_MIN


def transcribe(ep, force=False):
    """Return {'source','model','segments':[{start,end,text,avg_logprob,no_speech_prob}],...}."""
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRANSCRIPT_DIR / f"{ep['number']}.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text())
    audio = download_audio(ep)
    t0 = time.time()
    pcm = decode_pcm(audio)
    segments, attempt, ok = None, None, False
    # Same settings as the tested prototype (beam 1 + VAD). Whisper occasionally derails on a long
    # episode (skips minutes of speech); detect that by word coverage and retry with other settings.
    for attempt, kw in enumerate(ATTEMPTS):
        segs, info = get_model().transcribe(pcm, word_timestamps=True, **kw)
        segments = [_seg(s) for s in segs]
        if coverage_ok(segments, len(pcm) / 16000):
            ok = True
            break
    if not ok:
        # Never cache or publish from a derailed transcript.
        raise RuntimeError(f"{ep['number']}: transcript coverage too low after {len(ATTEMPTS)} attempts")
    data = {'source': f'whisper:{WHISPER_MODEL}', 'number': ep['number'], 'guid': ep['guid'],
            'audioUrl': ep['audioUrl'], 'audioBytes': audio.stat().st_size,
            'audioDurationSec': round(len(pcm) / 16000, 2), 'elapsedSec': round(time.time() - t0, 1), 'attempt': attempt,
            'wordsPerMin': round(sum(len(x['text'].split()) for x in segments) / (len(pcm) / 16000 / 60), 1),
            'segments': segments}
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=0))
    return data


if __name__ == '__main__':
    import sys
    from .rss import episodes, find_episode
    eps = episodes()
    for n in sys.argv[1:]:
        ep = find_episode(int(n), eps)
        d = transcribe(ep)
        print(n, ep['title'], len(d['segments']), 'segments', d['elapsedSec'], 's', flush=True)
