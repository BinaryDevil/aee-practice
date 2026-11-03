import {test} from 'node:test'; import assert from 'node:assert/strict'; import {readFile} from 'node:fs/promises'; import {buildSession,isDistractor,checkRecall,recallHint} from '../../assets/js/quiz.js';
const ep=JSON.parse(await readFile(new URL('./fixtures/episode.json',import.meta.url)));
const pairs=q=>q.map(x=>`${x.item.id}:${x.type}`);
test('sessions cover every item with varied types and unique correct choices',()=>{const q=buildSession(ep,42); assert.ok(q.length>=ep.items.length&&q.length<=15); assert.deepEqual(new Set(q.map(x=>x.item.id)),new Set(ep.items.map(x=>x.id))); assert.ok(new Set(q.map(x=>x.type)).size>=4); for(const x of q.filter(x=>x.type!=='recall')){assert.equal(x.options.filter(o=>o.correct).length,1); for(const o of x.options.filter(o=>!o.correct)) assert.ok(isDistractor(x.item,o.item));}});
test('no item gets the same question type twice',()=>{for(const seed of [1,2,3,42,99]){const p=pairs(buildSession(ep,seed)); assert.equal(new Set(p).size,p.length);}});
test('a one-item episode gets a short, varied session instead of ten repeats',()=>{const q=buildSession({...ep,items:[ep.items[0]]},5); assert.ok(q.length<=6); assert.equal(new Set(q.map(x=>x.type)).size,q.length);});
test('questions ramp from recognition to production',()=>{const stage={meaning:0,chinese:0,definition:1,cloze:1,listening:2,recall:2}; for(const seed of [3,8]){const s=buildSession(ep,seed).map(x=>stage[x.type]); assert.deepEqual(s,[...s].sort((a,b)=>a-b));}});
test('seeds are deterministic and cloze uses inflections',()=>{const a=buildSession(ep,123); assert.deepEqual(a,buildSession(ep,123)); assert.notDeepEqual(a,buildSession(ep,124)); for(const q of a.filter(x=>['cloze','listening'].includes(x.type))) for(const o of q.options) assert.equal(o.text,o.correct?q.occurrence.answer:(o.item.inflections?.[q.occurrence.answerForm]||o.item.text));});
test('typed answers ignore case and punctuation and accept inflections',()=>{const q={item:{text:"pick one's battles",inflections:{past:'picked my battles'}},occurrence:{answer:'Pick your battles'}}; for(const ok of ['pick your battles','  Pick  your battles!','PICK ONE’S BATTLES','picked my battles']) assert.ok(checkRecall(q,ok),ok); for(const bad of ['','pick battles','choose your battles']) assert.ok(!checkRecall(q,bad),bad); assert.equal(recallHint("Pick your battles"),'P___ y___ b______'); assert.equal(recallHint("one's"),'o___');});
test('synonyms and same items are excluded',()=>{assert.equal(isDistractor(ep.items[1],ep.items[1]),false); assert.equal(isDistractor(ep.items[1],ep.distractors[2]),false);});
test('word families and words in meanings are excluded', () => {
  const make = (text, meaningEn = '') => ({text, meaningEn});
  for (const [a, b] of [['humble', 'humility'], ['embarrassed', 'embarrassing']]) {
    assert.equal(isDistractor(make(a), make(b)), false);
  }
  assert.equal(isDistractor(make('humble'), make('modesty', 'the characteristic of being humble')), false);
});
