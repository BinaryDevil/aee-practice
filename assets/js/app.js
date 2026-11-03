import en from '../i18n/en.js';
import zh from '../i18n/zh-CN.js';
import { config } from './config.js';
import { buildSession, blankSentence, checkRecall } from './quiz.js';
import { explanation } from './explain.js';
const $ = s => document.querySelector(s),
  app = $('#app'),
  audio = $('#audio');
const read = (key, fallback) => {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
};
let settings = read('aee-settings', {
    ui: 'en',
    explanation: 'en'
  }),
  progress = read('aee-progress', {}),
  index = [],
  catalog = [],
  cache = new Map(),
  episode,
  session = [],
  cursor = 0,
  answered = false,
  misses = new Map(),
  retrying = false,
  score = 0,
  selectedExplanation = null;
const t = k => (settings.ui === 'zh' ? zh : en)[k] || k;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
})[c]);
const save = () => {
  localStorage.setItem('aee-settings', JSON.stringify(settings));
  localStorage.setItem('aee-progress', JSON.stringify(progress));
};
const duration = n => `${Math.floor((n || 0) / 60)} min`;
const date = d => {
  const x = new Date(d);
  return isNaN(x) ? '' : x.toLocaleDateString(settings.ui === 'zh' ? 'zh-CN' : 'en', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};
const clip = (o, ep = episode) => o ? `<button class="clip" data-testid="play-button" data-start="${Number(o.start) || 0}" data-end="${Number(o.end) || 0}" data-audio="${esc(ep?.audioUrl || '')}" data-url="${esc(ep?.episodeUrl || '')}" data-episode="${esc(String(ep?.number ?? ''))}" aria-label="${t('play')}">▶ <span>${Math.floor((o.start || 0) / 60)}:${String(Math.floor((o.start || 0) % 60)).padStart(2, '0')}</span></button>` : '';
window.__aee = {
  audio,
  lastClip: null
};
let clipEnd = null;
let lastButton = null;
// The official MP3 has dynamically inserted ads whose length varies per listener, so a clip can land
// early or late. Learners can nudge it; the offset is remembered per episode.
const offsetKey = n => `aee-offset-${n}`;
const getOffset = n => Number(localStorage.getItem(offsetKey(n))) || 0;
function clipBar(n) {
  const off = getOffset(n);
  $('#clip-bar').innerHTML = `<span>${t('clipOff')}</span> <button type="button" data-testid="nudge-back" data-nudge="-15">−15s</button> <button type="button" data-testid="nudge-forward" data-nudge="15">+15s</button>${off ? ` <small data-testid="nudge-offset">${off > 0 ? '+' : ''}${off}s</small>` : ''}`;
}
function playClip(button) {
  lastButton = button;
  const n = button.dataset.episode, offset = n ? getOffset(n) : 0;
  const start = Number(button.dataset.start) + offset,
    end = Number(button.dataset.end) + offset,
    src = button.dataset.audio;
  if (n) clipBar(n);
  window.__aee.lastClip = {
    start,
    end
  };
  clipEnd = end + .5;
  $('#audio-error').innerHTML = '';
  if (audio.getAttribute('src') !== src) {
    audio.src = src;
    audio.load();
  }
  const seek = () => {
    try {
      audio.currentTime = Math.max(0, start - .5);
    } catch {}
  };
  seek();
  if (audio.readyState < 1) audio.addEventListener('loadedmetadata', seek, {
    once: true
  });
  audio.play().catch(() => {});
  audio.dataset.episodeUrl = button.dataset.url;
}
audio.addEventListener('timeupdate', () => {
  if (clipEnd !== null && audio.currentTime >= clipEnd) {
    audio.pause();
    clipEnd = null;
  }
});
audio.addEventListener('error', () => {
  $('#audio-error').innerHTML = `${t('audioError')} ${audio.dataset.episodeUrl ? `<a href="${esc(audio.dataset.episodeUrl)}" target="_blank" rel="noopener">${t('official')}</a>` : ''}`;
});
async function json(path) {
  const r = await fetch(path);
  if (!r.ok) throw Error(path);
  return r.json();
}
async function getEpisode(number) {
  if (cache.has(number)) return cache.get(number);
  const row = index.find(x => String(x.number) === String(number));
  if (!row) throw Error('missing');
  const data = await json(`data/${row.file || `episodes/${number}.json`}`);
  cache.set(number, data);
  return data;
}
function chrome() {
  document.documentElement.lang = settings.ui === 'zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-nav]').forEach(a => a.textContent = t(a.dataset.nav));
  $('#language-switch').textContent = settings.explanation === 'zh' ? '解释：中文' : settings.explanation === 'both' ? 'Explanation: EN + 中文' : 'Explanation: EN';
}
function meaning(item) {
  return `${settings.explanation !== 'zh' ? `<span>${esc(item.meaningEn)}</span>` : ''}${settings.explanation !== 'en' ? `<span lang="zh">${esc(item.meaningZh || '暂无中文释义')}${item.meaningZhSource === 'mt' ? ' <small>机器翻译</small>' : ''}</span>` : ''}`;
}
function home() {
  const newest = (a, b) => (Date.parse(b.pubDate) || 0) - (Date.parse(a.pubDate) || 0);
  const ready = [...index].sort(newest);
  const other = catalog.filter(row => !index.some(item => String(item.number) === String(row.number))).sort(newest);
  const workflow = `${t('workflow')} ${config.repoUrl ? `<a href="${esc(config.repoUrl.replace(/\/$/, ''))}/actions/workflows/build-episode.yml" target="_blank" rel="noopener">GitHub Actions ↗</a>` : t('noRepo')}`;
  app.innerHTML = `<section class="hero"><p class="eyebrow">ALL EARS ENGLISH / PRACTICE</p><h1>${t('title')}</h1><p>${t('intro')}</p></section><section><label class="search"><span aria-hidden="true">⌕</span><input data-testid="search-box" type="search" placeholder="${t('search')}" aria-label="${t('search')}"></label><div class="section-head"><h2>${t('readyList')}</h2></div><div id="ready-list"></div><p class="workflow">${workflow}</p><details><summary>${t('otherEpisodes')}</summary><div id="other-list"></div></details></section>`;
  function row(item, prepared) {
    const tag = prepared ? 'a' : 'div';
    return `<${tag} ${prepared ? `href="#/episode/${item.number}"` : ''} class="episode-row ${prepared ? '' : 'disabled'}" data-testid="episode-row"><span class="episode-number">${esc(item.number)}</span><span class="episode-copy"><strong>${esc(item.title)}</strong><small>${date(item.pubDate)} · ${duration(item.durationSec)}${prepared ? ` · ${item.itemCount ?? 0} ${t('items')}` : ''}</small>${prepared ? '' : `<small>${workflow}</small>`}</span><span class="status">${t(prepared ? 'ready' : 'unprepared')}</span></${tag}>`;
  }
  function render() {
    const query = $('[data-testid="search-box"]').value.toLowerCase();
    const filter = rows => rows.filter(item => `${item.number} ${item.title}`.toLowerCase().includes(query));
    $('#ready-list').innerHTML = filter(ready).map(item => row(item, true)).join('') || `<p class="empty">${t(ready.length ? 'notFound' : 'noEpisodes')}</p>`;
    $('#other-list').innerHTML = filter(other).map(item => row(item, false)).join('') || `<p class="empty">${t('notFound')}</p>`;
  }
  $('[data-testid="search-box"]').addEventListener('input', render);
  render();
}
function study(ep, only = null) {
  episode = ep;
  const items = only || ep.items || [];
  app.innerHTML = `<a class="back" href="#/">← ${t('back')}</a><div class="study-head"><p class="eyebrow">AEE ${esc(ep.number)} / ${t('study')}</p><h1>${esc(ep.title)}</h1><p>${date(ep.pubDate)} · ${duration(ep.durationSec)} · ${items.length} ${t('items')}</p>${ep.episodeUrl ? `<p><a href="${esc(ep.episodeUrl)}" target="_blank" rel="noopener">${t('official')} ↗</a></p>` : ''}<button class="primary" data-testid="start-quiz">${t('start')}</button></div><div class="cards">${items.map(item => `<article class="study-card"><div class="card-top"><div><h2>${esc(item.display || item.text)}</h2>${item.ipa ? `<span class="ipa">${esc(item.ipa)}</span>` : ''}</div>${clip(item.occurrences?.[0], ep)}</div><div class="meanings">${meaning(item)}</div>${item.occurrences?.[0] ? `<blockquote>${esc(item.occurrences[0].sentence)}</blockquote>` : ''}</article>`).join('')}</div>`;
  $('[data-testid="start-quiz"]').onclick = () => start(ep, items);
}
function start(ep, items = ep.items) {
  episode = ep;
  session = buildSession({
    ...ep,
    items
  }, Date.now() + Math.floor(Math.random() * 100000));
  session.forEach(q => {
    if (q.item._episode) {
      q.episodeNumber = q.item._episode.number;
      q.audioUrl = q.item._episode.audioUrl;
      q.episodeUrl = q.item._episode.episodeUrl;
    }
  });
  totalBeforeRetry = session.length;
  cursor = 0;
  misses = new Map();
  retrying = false;
  score = 0;
  showQuestion();
}
function showQuestion() {
  const q = session[cursor];
  if (!q) {
    finish();
    return;
  }
  answered = false;
  selectedExplanation = null;
  const occurrence = q.occurrence;
  const ep = {
    number: q.episodeNumber,
    audioUrl: q.audioUrl,
    episodeUrl: q.episodeUrl
  };
  const prompt = t({
    meaning: 'meaningPrompt',
    cloze: 'clozePrompt',
    listening: 'listeningPrompt',
    chinese: 'chinesePrompt',
    definition: 'definitionPrompt',
    recall: 'recallPrompt'
  }[q.type]);
  // Listening hides the sentence and recall hides the audio, so neither can be answered by the other channel.
  const sentenceBlock = !occurrence ? '' : q.type === 'listening' ? `${clip(occurrence, ep)} <span class="hidden-sentence">${t('listenHint')}</span>` : `${q.type === 'recall' ? '' : clip(occurrence, ep)} <span>${esc(['cloze', 'recall'].includes(q.type) ? blankSentence(occurrence) : occurrence.sentence)}</span>`;
  app.innerHTML = `<div class="quiz-head"><a class="back" href="#/">← ${t('home')}</a><span>${retrying ? t('retry') : `${cursor + 1} / ${session.length}`}</span></div><div class="progress"><span style="width:${cursor / session.length * 100}%"></span></div><section class="question" data-has-tip="${Boolean(q.item.teacherNote || q.item.synonyms?.length || (q.item.tags || []).some(tag => ['informal', 'formal', 'slang'].includes(tag)))}"><p class="eyebrow">${t('quiz')} · ${q.type === 'listening' ? '♫' : q.type === 'recall' ? '✎' : '✦'}</p><h1>${prompt}</h1>${q.type === 'meaning' ? `<p class="question-word">${esc(q.item.display || q.item.text)}</p>` : ''}${q.type === 'chinese' ? `<p class="question-word">${esc(q.item.meaningZh)}</p>` : ''}${q.type === 'definition' ? `<p class="question-word definition">${esc(q.item.meaningEn)}</p>` : ''}${sentenceBlock ? `<div class="sentence" data-testid="question-sentence">${sentenceBlock}</div>` : ''}<div id="options" class="options"></div><div id="feedback" aria-live="polite"></div><button class="primary next" data-testid="next-button" hidden>${t('next')}</button></section>`;
  renderOptions(q);
  $('[data-testid="next-button"]').onclick = advance;
}
function renderOptions(q) {
  const el = $('#options');
  if (q.type === 'recall') {
    el.innerHTML = `<form class="recall" data-testid="recall-form"><label for="recall-input">${t('recallLabel')} <code data-testid="recall-hint">${esc(q.hint)}</code></label><input id="recall-input" data-testid="recall-input" autocomplete="off" autocapitalize="off" spellcheck="false"><div class="recall-actions"><button class="primary" data-testid="recall-submit">${t('check')}</button><button type="button" class="text-button" data-testid="recall-giveup">${t('giveUp')}</button></div></form>`;
    const input = el.querySelector('input');
    const submit = typed => answer(q, {item: {text: q.occurrence.answer, typed}, correct: checkRecall(q, typed)});
    el.querySelector('form').onsubmit = e => { e.preventDefault(); submit(input.value); };
    el.querySelector('[data-testid="recall-giveup"]').onclick = () => submit('');
    input.focus();
    return;
  }
  el.innerHTML = q.options.map((o, i) => `<button class="option" data-testid="option-button" data-index="${i}" data-correct="${o.correct}" data-meaning-en="${esc(o.item.meaningEn)}" data-meaning-zh="${esc(o.item.meaningZh)}">${q.type === 'meaning' ? meaning(o.item) : esc(o.text)}</button>`).join('');
  el.querySelectorAll('button').forEach(b => b.onclick = () => answer(q, q.options[Number(b.dataset.index)]));
}
function answer(q, option) {
  if (answered) return;
  answered = true;
  const right = option.correct;
  if (!retrying && right) score++;
  const key = `${q.episodeNumber}:${q.item.id}`;
  const old = progress[key] || {
    itemId: q.item.id,
    episode: q.episodeNumber,
    box: 1,
    wrongCount: 0
  };
  old.box = right ? Math.min(5, old.box + 1) : Math.max(1, old.box - 1);
  if (!right) {
    old.wrongCount++;
    if (!retrying && !misses.has(key)) misses.set(key, q);
  }
  old.lastSeen = new Date().toISOString();
  progress[key] = old;
  save();
  selectedExplanation = {
    q,
    option,
    right,
    lang: settings.explanation === 'zh' ? 'zh' : 'en'
  };
  document.querySelectorAll('#options button, #options input').forEach(b => b.disabled = true);
  document.querySelectorAll('#options .option').forEach(b => {
    if (b.dataset.correct === 'true') b.classList.add('is-correct');
    else if (q.options[Number(b.dataset.index)] === option) b.classList.add('is-wrong');
  });
  $('#recall-input')?.classList.add(right ? 'is-correct' : 'is-wrong');
  revealSentence(q);
  renderExplanation();
  $('[data-testid="next-button"]').hidden = false;
}
// Once answered, show the full sentence (with the expression marked) and its clip in the question card.
function markedSentence(o) {
  if (!o) return '';
  if (!Number.isInteger(o.answerStart) || !Number.isInteger(o.answerEnd)) return esc(o.sentence || '');
  return `${esc(o.sentence.slice(0, o.answerStart))}<mark>${esc(o.sentence.slice(o.answerStart, o.answerEnd))}</mark>${esc(o.sentence.slice(o.answerEnd))}`;
}
function revealSentence(q) {
  const box = $('[data-testid="question-sentence"]');
  if (!box || !q.occurrence) return;
  box.innerHTML = `${clip(q.occurrence, {number: q.episodeNumber, audioUrl: q.audioUrl, episodeUrl: q.episodeUrl})} <span>${markedSentence(q.occurrence)}</span>`;
}
function renderExplanation() {
  const {
    q,
    option,
    right,
    lang
  } = selectedExplanation;
  const o = q.occurrence;
  const ep = {
    number: q.episodeNumber,
    audioUrl: q.audioUrl,
    episodeUrl: q.episodeUrl
  };
  const x = explanation(q.item, option.item, lang, right, q.type, o);
  const meaning = `${esc(x.meaning)}${x.secondary ? `<br>${esc(x.secondary)}` : ''}`;
  const sentence = markedSentence(o);
  const context = `<div data-testid="exp-episode">② ${lang === 'zh' ? '在节目中：' : 'In the episode:'} ${clip(o, ep)} ${sentence ? `“${sentence}”` : ''}${o?.sentenceZh ? `<div class="translation">机器翻译（仅供参考）：${esc(o.sentenceZh)}</div>` : ''}</div>`;
  $('#feedback').innerHTML = `<div class="feedback ${right ? 'correct' : 'wrong'}" data-testid="explanation-panel"><h2>${esc(x.heading)}</h2>${right ? `<details${selectedExplanation.open ? ' open' : ''}><summary>${t('correctMeaning')}</summary><p data-testid="exp-meaning">${meaning}</p></details>` : `<p data-testid="exp-meaning">${meaning}</p>${context}<p data-testid="exp-why">${esc(x.why)}</p>${x.tip ? `<p data-testid="exp-tip">${esc(x.tip)}</p>` : ''}`}<button class="text-button" id="other-language" data-testid="other-language" lang="${lang === 'zh' ? 'en' : 'zh'}">${lang === 'zh' ? 'Explain in English' : '用中文解释'}</button></div>`;
  const details = $('#feedback details');
  if (details) details.ontoggle = () => { selectedExplanation.open = details.open; };
  $('#other-language').onclick = () => {
    // Switching language is a request to read the explanation, so keep the meaning section open.
    selectedExplanation.lang = lang === 'zh' ? 'en' : 'zh';
    selectedExplanation.open = true;
    renderExplanation();
  };
}
function advance() {
  cursor++;
  if (cursor >= session.length && !retrying && misses.size) {
    session = [...misses.values()];
    cursor = 0;
    retrying = true;
  }
  if (cursor >= session.length) finish();else showQuestion();
}
function finish() {
  const initialTotal = retrying ? originalTotal() : session.length;
  app.innerHTML = `<section data-testid="results-screen" class="results"><p class="eyebrow">${t('quiz')}</p><h1>${t('results')}</h1><div class="score">${score}<span> / ${initialTotal}</span></div><p>${t('score')}</p>${misses.size ? `<h2>${t('missed')}</h2><ul>${[...misses.values()].map(q => `<li>${esc(q.item.display || q.item.text)}</li>`).join('')}</ul><button id="review" class="secondary">${t('review')}</button>` : ''}<button id="again" class="primary">${t('again')}</button><a class="back" href="#/">← ${t('back')}</a></section>`;
  $('#again').onclick = () => start(episode, episode.items);
  if ($('#review')) $('#review').onclick = () => {
    const items = [...misses.values()].map(q => q.item);
    start(episode, items);
  };
}
let totalBeforeRetry = 0;
function originalTotal() {
  return totalBeforeRetry || score + misses.size;
} // The initial total is captured before the retry round.
async function words() {
  const entries = Object.values(progress);
  if (!entries.length) {
    app.innerHTML = `<h1>${t('words')}</h1><p class="empty">${t('empty')}</p>`;
    return;
  }
  const numbers = [...new Set(entries.map(x => x.episode))];
  await Promise.all(numbers.map(n => getEpisode(n).catch(() => null)));
  const rows = entries.map(p => ({
    p,
    ep: cache.get(p.episode),
    item: cache.get(p.episode)?.items.find(x => x.id === p.itemId)
  })).filter(x => x.item);
  app.innerHTML = `<div class="study-head"><p class="eyebrow">${t('study')}</p><h1>${t('words')}</h1><button class="primary" id="mistakes">${t('mistakes')}</button></div><div class="cards">${rows.map(({
    p,
    ep,
    item
  }) => `<article class="study-card"><div class="card-top"><h2>${esc(item.display || item.text)}</h2><span class="box">${t('box')} ${p.box}</span></div><div class="meanings">${meaning(item)}</div><small>AEE ${ep.number} · ${p.wrongCount} ${t('wrong')}</small></article>`).join('')}</div>`;
  $('#mistakes').onclick = () => {
    const wrong = rows.filter(x => x.p.wrongCount > 0);
    if (!wrong.length) {
      $('#mistakes').insertAdjacentHTML('afterend', `<p>${t('noMistakes')}</p>`);
      return;
    }
    const mixed = {
      ...wrong[0].ep,
      items: wrong.map(x => ({
        ...x.item,
        _episode: x.ep
      })),
      distractors: rows.flatMap(x => x.ep.distractors || [])
    };
    start(mixed);
  };
}
function settingsView() {
  app.innerHTML = `<section class="narrow"><h1>${t('settings')}</h1><fieldset><legend>${t('explanation')}</legend>${[['en', 'English'], ['zh', '中文'], ['both', t('both')]].map(([v, l]) => `<label class="radio"><input type="radio" name="explanation" value="${v}" ${settings.explanation === v ? 'checked' : ''}> ${l}</label>`).join('')}</fieldset><fieldset><legend>${t('ui')}</legend>${[['en', 'English'], ['zh', '中文']].map(([v, l]) => `<label class="radio"><input type="radio" name="ui" value="${v}" ${settings.ui === v ? 'checked' : ''}> ${l}</label>`).join('')}</fieldset></section>`;
  app.querySelectorAll('input').forEach(x => x.onchange = () => {
    settings[x.name] = x.value;
    if (x.name === 'ui') settings.uiExplicit = true;
    save();
    chrome();
    settingsView();
  });
}
function about() {
  app.innerHTML = `<section class="narrow about"><h1>${t('aboutTitle')}</h1><p>${t('copyright')}</p><p><a href="https://www.allearsenglish.com/" target="_blank" rel="noopener">All Ears English ↗</a></p><p>${t('overrides')}</p><h2>${t('credits')}</h2><ul><li>Kaikki / Wiktionary — CC BY-SA 4.0</li><li>ECDICT — MIT</li><li>faster-whisper / Whisper — MIT</li><li>opus-mt-en-zh — CC BY 4.0</li><li>spaCy — MIT</li></ul></section>`;
}
async function route() {
  chrome();
  const parts = location.hash.replace(/^#\/?/, '').split('/');
  try {
    if (parts[0] === 'episode') {
      const ep = await getEpisode(parts[1]);
      study(ep);
    } else if (parts[0] === 'words') await words();else if (parts[0] === 'settings') settingsView();else if (parts[0] === 'about') about();else home();
  } catch {
    app.innerHTML = `<p class="empty">${t('loadError')}</p><a href="#/">${t('back')}</a>`;
  }
}
$('#language-switch').onclick = () => {
  settings.explanation = settings.explanation === 'zh' ? 'en' : 'zh';
  if (!settings.uiExplicit) settings.ui = settings.explanation;
  save();
  chrome();
  if (selectedExplanation) {
    selectedExplanation.lang = settings.explanation;
    renderExplanation();
  } else if ($('.question')) showQuestion();else route();
};
document.addEventListener('click', e => {
  const b = e.target.closest('[data-testid="play-button"]');
  if (b) playClip(b);
  const nudge = e.target.closest('[data-nudge]');
  if (nudge && lastButton?.dataset.episode) {
    const n = lastButton.dataset.episode;
    localStorage.setItem(offsetKey(n), String(getOffset(n) + Number(nudge.dataset.nudge)));
    playClip(lastButton);
  }
});
window.addEventListener('hashchange', route);
Promise.all([json('data/episodes/index.json').catch(() => ({
  episodes: []
})), json('data/catalog.json').catch(() => ({
  episodes: []
}))]).then(([a, b]) => {
  index = a.episodes || [];
  catalog = b.episodes || [];
  route();
});
