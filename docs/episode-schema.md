# Published data schema (v1)

Only these files are published. They contain **extracted items + short context sentences + timestamps**.
They never contain a full transcript, and audio is always streamed from the official MP3 URL.

## `data/episodes/index.json`
```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-11-03T09:00:00Z",
  "episodes": [
    { "number": 2713, "guid": "…", "title": "Take a Crack at These English Phrases", "pubDate": "…",
      "durationSec": 1008, "itemCount": 12, "hasBlog": false, "file": "episodes/2713.json" }
  ]
}
```
Sorted newest first (by number).

## `data/catalog.json`
Metadata only (no content) of the newest ~60 numbered episodes in the RSS, so the app can show
"not prepared yet" episodes with instructions for the build workflow.
```json
{ "generatedAt": "…", "episodes": [ { "number": 2715, "title": "…", "pubDate": "…", "durationSec": 1100 } ] }
```

## `data/episodes/<number>.json`
```json
{
  "schemaVersion": 1,
  "number": 2713, "guid": "…", "title": "…", "subtitle": "…", "pubDate": "…", "durationSec": 1008,
  "audioUrl": "https://traffic.megaphone.fm/ALLE….mp3",          // official URL, streamed, never rehosted
  "episodeUrl": "https://www.allearsenglish.com/…" | null,
  "blogUrl": null,
  "transcriptSource": "whisper:small.en",                         // metadata only, no segments
  "items": [
    {
      "id": "take-a-crack-at",
      "rank": 1,
      "text": "take a crack at",                  // canonical (lemma) form
      "display": "take a crack at (something)",
      "kind": "expression" | "word",
      "origin": "transcript" | "blog",
      "score": 27.0,
      "pos": "verb" | "noun" | "adj" | "adv" | "phrase" | "intj" | …,
      "ipa": null,
      "tags": ["idiomatic", "informal"],
      "meaningEn": "To attempt or try (something difficult).",
      "meaningEnSource": "kaikki" | "ecdict" | "blog" | "override",
      "meaningZh": "尝试；试一试",
      "meaningZhSource": "override" | "kaikki" | "ecdict" | "mt",
      "meaningZhAlt": "ECDICT gloss shown as secondary, or null",
      "teacherNote": "string or null (blog explanation / usage tip; may be null)",
      "occurrences": [                            // max 3, each sentence <= ~240 chars
        { "start": 379.46, "end": 384.7,
          "sentence": "So I decided to take a crack at it.",
          "sentenceZh": "…", "sentenceZhSource": "mt",
          "answer": "take a crack at",            // exact surface span inside sentence, for cloze
          "answerStart": 13, "answerEnd": 28,     // char offsets of answer in sentence
          "answerForm": "base" | "past" | "pp" | "ing" | "s3" | "plural" | "other" }
      ],
      "inflections": { "base": "take a crack at", "past": "took a crack at", "pp": "taken a crack at",
                       "ing": "taking a crack at", "s3": "takes a crack at" },
      "examples": ["Would you like to take a stab at explaining the theory?"],
      "synonyms": ["take a stab at", "give it a shot"]
    }
  ],
  "distractors": [                               // extra confusables from the lexicon (not in the episode)
    { "text": "crack down", "pos": "verb", "meaningEn": "…", "meaningZh": "…", "meaningZhSource": "mt",
      "inflections": { … } }
  ],
  "generator": { "version": "1.0.0", "builtAt": "…", "lexicons": { "kaikki": "…", "ecdict": "…" }, "mt": "opus-mt-en-zh (CTranslate2, offline)" }
}
```
Notes:
- `meaningZhSource: "mt"` / `sentenceZhSource: "mt"` must be labelled 机器翻译 in the UI.
- Questions are generated client-side from `items` + `distractors` (new mix each session).
