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


def transcribe(ep, force=False):
    """Return {'source','model','segments':[{start,end,text,avg_logprob,no_speech_prob}],...}."""
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRANSCRIPT_DIR / f"{ep['number']}.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text())
    audio = download_audio(ep)
    t0 = time.time()
    pcm = decode_pcm(audio)
    segs, info = get_model().transcribe(pcm, beam_size=1, vad_filter=True, language='en')
    segments = [{'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip(),
                 'avg_logprob': round(s.avg_logprob, 3), 'no_speech_prob': round(s.no_speech_prob, 3)}
                for s in segs]
    data = {'source': f'whisper:{WHISPER_MODEL}', 'number': ep['number'], 'guid': ep['guid'],
            'audioUrl': ep['audioUrl'], 'audioBytes': audio.stat().st_size,
            'audioDurationSec': round(len(pcm) / 16000, 2), 'elapsedSec': round(time.time() - t0, 1),
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
