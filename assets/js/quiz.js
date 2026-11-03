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
// Questions go from recognising an expression to producing it. Each stage picks a different type per item,
// so one item never gets the same kind of question twice in a session.
const STAGES = [['meaning', 'chinese'], ['definition', 'cloze'], ['listening', 'recall']];
const NEEDS_SENTENCE = ['cloze', 'listening', 'recall'];
const MAX_QUESTIONS = 15;
function available(item, type) {
  if (NEEDS_SENTENCE.includes(type)) return Boolean(item.occurrences?.length);
  if (type === 'chinese') return Boolean(item.meaningZh);
  return Boolean(item.meaningEn);
}
// Few items: ask both types of every stage. Many items: one per stage, capped at MAX_QUESTIONS.
function plan(items, random) {
  const perStage = items.length <= 2 ? 2 : 1;
  const stages = STAGES.map(types => shuffle(items, random).flatMap(item => shuffle(types.filter(type => available(item, type)), random).slice(0, perStage).map(type => ({item, type}))));
  const out = [];
  for (const stage of stages) {
    for (const entry of stage) {
      // Avoid asking about the same item twice in a row when another order is possible.
      const previous = out[out.length - 1];
      if (previous && previous.item === entry.item) {
        const swap = stage.findIndex(x => x.item !== entry.item && !out.includes(x));
        if (swap >= 0) { out.push(stage[swap]); stage.splice(swap, 1, entry); continue; }
      }
      if (!out.includes(entry)) out.push(entry);
    }
  }
  return out.slice(0, Math.max(items.length, MAX_QUESTIONS));
}
// Typed answers ignore case, punctuation and apostrophe style; any listed inflection of the item counts.
export const normalizeAnswer = s => (s || '').toLowerCase().replace(/[’']/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
export function checkRecall(q, typed) {
  const value = normalizeAnswer(typed);
  if (!value) return false;
  const accepted = [q.occurrence?.answer, q.item.text, q.item.display, ...Object.values(q.item.inflections || {})];
  return accepted.some(x => normalizeAnswer(x) === value);
}
export function recallHint(answer) {
  return (answer || '').split(/\s+/).filter(Boolean).map(w => w[0] + '_'.repeat(Math.max(0, w.replace(/[^A-Za-z]/g, '').length - 1))).join(' ');
}
export function buildSession(episode, seed = Date.now()) {
  const random = rng(seed),
    items = episode.items || [],
    pool = episode.distractors || [];
  if (!items.length) return [];
  const used = new Map();
  const questions = [];
  for (const {item, type} of plan(items, random)) {
    // Sentence questions rotate through the item's occurrences so the same sentence isn't reused.
    let occurrence = item.occurrences?.[0];
    if (NEEDS_SENTENCE.includes(type)) {
      const n = used.get(item) || 0;
      occurrence = item.occurrences[n % item.occurrences.length];
      used.set(item, n + 1);
    }
    const base = {type, item, occurrence, episodeNumber: episode.number, audioUrl: episode.audioUrl, episodeUrl: episode.episodeUrl};
    if (type === 'recall') {
      questions.push({...base, options: [], hint: recallHint(occurrence.answer)});
      continue;
    }
    const sentence = ['cloze', 'listening'].includes(type);
    const candidates = [...shuffle(items.filter(x => isDistractor(item, x)), random), ...shuffle(pool.filter(x => isDistractor(item, x)), random)];
    const unique = [];
    for (const c of candidates) if (!unique.some(x => norm(x.text) === norm(c.text))) unique.push(c);
    const form = occurrence?.answerForm || 'base';
    const correctLabel = norm(sentence ? occurrence?.answer : item.text);
    const usable = unique.filter(x => norm(sentence ? x.inflections?.[form] || x.text : x.text) !== correctLabel);
    const label = x => type === 'meaning' ? x.meaningEn || x.text || '' : sentence ? x === item ? occurrence.answer : x.inflections?.[form] || x.text : x.text || '';
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
      text: sentence ? x === item ? occurrence.answer : x.inflections?.[form] || x.text : x.text
    })), random);
    questions.push({...base, options});
  }
  return questions;
}
export function blankSentence(occ) {
  if (!occ) return '';
  const s = occ.sentence || '';
  return s.slice(0, occ.answerStart) + '____' + s.slice(occ.answerEnd);
}
