// Session generation is deterministic for a given seed and never mutates published data.
function rng(seed) {
  let n = Number(seed) >>> 0;
  return () => {
    n = Math.imul(n, 1664525) + 1013904223 >>> 0;
    return n / 4294967296;
  };
}
function shuffle(values, random) {
  const a = [...values];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
const norm = s => (s || '').toLowerCase().trim();
const tokens = s => new Set(norm(s).match(/[a-z]+/g)?.filter(x => !['to', 'a', 'an', 'the', 'of', 'or', 'and', 'is', 'be', 'someone', 'something', 'in', 'for'].includes(x)) || []);
export function isDistractor(target, candidate) {
  if (!candidate || candidate === target || target.id && target.id === candidate.id || norm(target.text) === norm(candidate.text)) return false;
  if ((target.synonyms || []).some(s => norm(s) === norm(candidate.text)) || (candidate.synonyms || []).some(s => norm(s) === norm(target.text))) return false;
  const wordsA = norm(target.text).match(/[a-z]+/g) || [];
  const wordsB = norm(candidate.text).match(/[a-z]+/g) || [];
  const familyStem = word => word.replace(/^humil/, 'humbl');
  const sharedStem = wordsA.some(a => wordsB.some(b => a.length >= 5 && b.length >= 5 && familyStem(a).slice(0, 5) === familyStem(b).slice(0, 5)));
  const inGloss = (word, gloss) => (norm(gloss).match(/[a-z]+/g) || []).includes(word);
  if (sharedStem || wordsA.length === 1 && inGloss(wordsA[0], candidate.meaningEn) || wordsB.length === 1 && inGloss(wordsB[0], target.meaningEn)) return false;
  const a = tokens(target.meaningEn),
    b = tokens(candidate.meaningEn);
  const overlap = [...a].filter(x => b.has(x)).length;
  return !a.size || !b.size || overlap / Math.min(a.size, b.size) <= .5;
}
export function buildSession(episode, seed = Date.now()) {
  const random = rng(seed),
    items = episode.items || [],
    pool = episode.distractors || [];
  if (!items.length) return [];
  const count = Math.max(10, Math.min(15, items.length * 2));
  const order = shuffle(items, random),
    questions = [];
  for (let i = 0; i < Math.max(count, items.length); i++) {
    const item = order[i % order.length],
      occurrence = item.occurrences?.[0];
    let type = ['meaning', 'cloze', 'listening', 'chinese', 'match'][Math.min(4, Math.floor(i * 5 / Math.max(count, items.length)))];
    if (!occurrence && ['cloze', 'listening'].includes(type)) type = 'meaning';
    const candidates = [...shuffle(items.filter(x => isDistractor(item, x)), random), ...shuffle(pool.filter(x => isDistractor(item, x)), random)];
    const unique = [];
    for (const c of candidates) if (!unique.some(x => norm(x.text) === norm(c.text))) unique.push(c);
    const form = occurrence?.answerForm || 'base';
    const correctLabel = norm(['cloze', 'listening'].includes(type) ? occurrence?.answer : item.text);
    const usable = unique.filter(x => norm(['cloze', 'listening'].includes(type) ? x.inflections?.[form] || x.text : x.text) !== correctLabel);
    const label = x => ['meaning', 'match'].includes(type) ? x.meaningEn || x.text || '' : ['cloze', 'listening'].includes(type) ? x === item ? occurrence.answer : x.inflections?.[form] || x.text : x.text || '';
    const length = label(item).length;
    const close = usable.filter(x => length && Math.abs(label(x).length - length) <= length * 0.4);
    const chosen = [];
    const labels = new Set([norm(label(item)), norm(item.meaningEn), norm(item.meaningZh)].filter(Boolean));
    for (const candidate of [...close, ...usable.filter(x => !close.includes(x))]) {
      const values = [norm(label(candidate)), norm(candidate.meaningEn), norm(candidate.meaningZh)].filter(Boolean);
      if (values.some(value => labels.has(value))) continue;
      chosen.push(candidate);
      values.forEach(value => labels.add(value));
      if (chosen.length === 3) break;
    }
    const options = shuffle([item, ...chosen].map(x => ({
      item: x,
      correct: x === item,
      text: type === 'cloze' || type === 'listening' ? x === item ? occurrence.answer : x.inflections?.[form] || x.text : x.text
    })), random);
    questions.push({
      type,
      item,
      occurrence,
      options,
      episodeNumber: episode.number,
      audioUrl: episode.audioUrl,
      episodeUrl: episode.episodeUrl
    });
  }
  return questions;
}
export function blankSentence(occ) {
  if (!occ) return '';
  const s = occ.sentence || '';
  return s.slice(0, occ.answerStart) + '____' + s.slice(occ.answerEnd);
}
