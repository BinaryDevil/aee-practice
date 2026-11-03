import {test} from 'node:test'; import assert from 'node:assert/strict'; import {readFile} from 'node:fs/promises'; import {buildSession,isDistractor} from '../../assets/js/quiz.js';
const ep=JSON.parse(await readFile(new URL('./fixtures/episode.json',import.meta.url)));
test('sessions cover items, question types and unique correct choices',()=>{const q=buildSession(ep,42); assert.ok(q.length>=10&&q.length<=15); assert.deepEqual(new Set(q.map(x=>x.item.id)),new Set(ep.items.map(x=>x.id))); assert.ok(new Set(q.map(x=>x.type)).size>=4); for(const x of q){assert.equal(x.options.filter(o=>o.correct).length,1); for(const o of x.options.filter(o=>!o.correct)) assert.ok(isDistractor(x.item,o.item));}});
test('seeds are deterministic and cloze uses inflections',()=>{const a=buildSession(ep,123); assert.deepEqual(a,buildSession(ep,123)); assert.notDeepEqual(a,buildSession(ep,124)); for(const q of a.filter(x=>['cloze','listening'].includes(x.type))) for(const o of q.options) assert.equal(o.text,o.correct?q.occurrence.answer:(o.item.inflections?.[q.occurrence.answerForm]||o.item.text));});
test('synonyms and same items are excluded',()=>{assert.equal(isDistractor(ep.items[1],ep.items[1]),false); assert.equal(isDistractor(ep.items[1],ep.distractors[2]),false);});
test('word families and words in meanings are excluded', () => {
  const make = (text, meaningEn = '') => ({text, meaningEn});
  for (const [a, b] of [['humble', 'humility'], ['embarrassed', 'embarrassing']]) {
    assert.equal(isDistractor(make(a), make(b)), false);
  }
  assert.equal(isDistractor(make('humble'), make('modesty', 'the characteristic of being humble')), false);
});
