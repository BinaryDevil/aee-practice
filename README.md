# AEE practice — Listening notes

A static web app (GitHub Pages) for practising the phrases taught in
[All Ears English](https://www.allearsenglish.com/) podcast episodes. Each episode gets a study list
plus a quiz (meaning, cloze, listening, matching, Chinese→English) in English or 中文 mode, with plain
wrong-answer explanations and a ▶ button that seeks the **official** episode audio to the place the phrase is used.

Unofficial fan project; not affiliated with All Ears English.

## Copyright policy
* Published data (`data/`) holds only the taught items, at most 2 short context sentences per item
  (≤160 chars each, ≤12 % of the transcript in total — enforced by `tests/test_published_json.py`) and timestamps.
* Audio is played straight from the official Megaphone MP3 URL in the RSS feed. It is never downloaded into the site or rehosted.
* Full transcripts, MP3s, lexicons and models live in `.cache/`, which is gitignored and never committed.

## Layout
| Path | What |
|---|---|
| `index.html`, `assets/` | Front end: vanilla ES modules, hash routing, localStorage progress |
| `data/episodes/<n>.json`, `data/episodes/index.json`, `data/catalog.json` | Published episode data (schema: `docs/episode-schema.md`) |
| `pipeline/` | RSS → faster-whisper `small.en` → phrase extraction → Wiktionary/ECDICT enrichment → quiz distractors |
| `overrides/zh.json` | Hand-curated Chinese meanings that override ECDICT (currently ep 2713) |
| `.github/workflows/` | `build-latest` (scheduled), `build-episode` (manual, by number), `pages` (deploy), `test` |
| `tests/` | pytest (pipeline + published-data checks + ep 2713 acceptance), `tests/js` (node), `tests/e2e` (Playwright) |

## Local setup
```bash
python -m venv venv && . venv/bin/activate
pip install -r pipeline/requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r pipeline/requirements-convert.txt  # one-off, to convert opus-mt
python -m pipeline.setup_resources        # ECDICT, Kaikki mini lexicon, opus-mt-en-zh (CTranslate2) into .cache/
python -m pipeline.build --number 2713    # or --latest 10; add --skip-existing / --force / --no-mt
python -m http.server 8765                # open http://127.0.0.1:8765/
```
Whisper runs on CPU (int8). Run one transcription at a time; parallel runs starve each other and
produce truncated transcripts. A coverage check (≥130 words/min) rejects truncated output.

## Tests
```bash
python -m pytest -q                       # set AEE_REQUIRE_ACCEPTANCE=1 to fail (not skip) when the real 2713 transcript is missing
node --test tests/js
pip install playwright && playwright install chromium
python tests/e2e/e2e.py --all             # starts its own server; or --base-url http://127.0.0.1:8765/
```
`e2e.py` flags: `--episode-number N`, `--all`, `--base-url`, `--data-root`,
`--allow-no-network` (don't fail when the official MP3 can't load), and `--audio-via-driver`
(fetch `traffic.megaphone.fm` through Playwright's own network instead of the browser's — needed in sandboxes
where the headless browser's egress is blocked; the `<audio>` src is still the official URL).

## Acceptance (AC-1)
For ep 2713 "Take a Crack at These English Phrases" all four taught items must rank in the top 8.
`tests/test_acceptance_2713.py` checks the committed sample transcript and, when present, the real one;
the CI `test` workflow transcribes 2713 first so the real check always runs there.

## Workflows
* **Build latest episodes** — daily cron + manual; builds the 10 newest episodes (skips ones already built), runs the
  published-data tests, commits `data/`, then calls the Pages deploy.
* Both builds look up the episode's allearsenglish.com blog post (WordPress API) and, when it has numbered
  "#1: phrase" sections, use those as the taught items. Posts often appear weeks later, so `--skip-existing`
  re-checks episodes built without one and rebuilds them when a post shows up. Lookup failures are logged as `blog: …`.
* **Build episode** — manual (`workflow_dispatch`) with an episode number (or several); same steps.
* **Deploy site to GitHub Pages** — publishes only `index.html`, `assets/`, `data/`.
* **Tests** — pytest, node tests and the 2713 acceptance check.

The app lists the ready episodes and, for others, explains how to run **Build episode**.

## Publishing later (not done yet)
Nothing has been pushed or published. When ready:
1. Create the GitHub repo and push `main`.
2. Settings → Pages → Source: **GitHub Actions**; Settings → Actions → Workflow permissions: **Read and write**.
3. Set `repoUrl` in `assets/js/config.js` to the repo URL so the "add an episode" link points at the workflow.
4. Run **Build latest episodes** once (or wait for the cron).

## Known limitations
* **Ad drift:** Megaphone inserts ads dynamically and their length varies per request, so timestamps can be off by
  ~15–45 s. The bar at the bottom offers −15 s / +15 s nudges; the offset is remembered per episode.
* **Machine translation:** context-sentence translations come from offline opus-mt-en-zh and are labelled
  机器翻译（仅供参考）. ECDICT meanings can include the wrong sense; use `overrides/zh.json` to fix them.
* Extraction is heuristic (no LLM): some episodes yield few items and senses can be wrong (e.g. 2712 "what now").

## Credits & licences
Wiktionary data via [Kaikki.org](https://kaikki.org/) (CC BY-SA 4.0 / GFDL) ·
[ECDICT](https://github.com/skywind3000/ECDICT) (MIT) ·
[Helsinki-NLP opus-mt-en-zh](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh) (CC BY 4.0) ·
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT) with OpenAI Whisper weights (MIT) ·
[spaCy](https://spacy.io/) `en_core_web_sm` (MIT). Podcast content © All Ears English.
