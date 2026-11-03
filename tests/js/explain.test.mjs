import { test } from 'node:test';
import assert from 'node:assert/strict';
import { explanation } from '../../assets/js/explain.js';

const item = { text: 'try', pos: 'verb', meaningEn: 'To make an attempt.', meaningZh: '尝试', occurrences: [{ sentence: 'I try.', answer: 'try' }] };
const chosen = { text: 'humility', pos: 'noun', meaningEn: 'Not pretentious.', meaningZh: '谦逊' };

test('explanations include both languages and natural embedded glosses', () => {
  const x = explanation(item, chosen, 'en', false, 'cloze');
  assert.match(x.meaning, /① Meaning/);
  assert.match(x.secondary, /中文：尝试/);
  assert.match(x.why, /means not pretentious \(谦逊\)\./);
  assert.match(x.why, /blank needs an action word.*thing word/);
  assert.doesNotMatch(x.why, /\.\./);
  assert.equal(x.tip, '');
  const zh = explanation(item, chosen, 'zh', false, 'cloze');
  assert.match(zh.secondary, /English: To make an attempt/);
  assert.match(zh.why, /动词.*名词/);
});

test('contrast depends on question type and register', () => {
  assert.doesNotMatch(explanation(item, chosen, 'en', false, 'chinese').why, /blank/);
  assert.match(explanation(item, chosen, 'en', false, 'meaning').why, /This one is about/);
  assert.match(explanation(item, {...chosen, tags: ['informal']}, 'en', false, 'cloze').why, /is informal/);
});

test('tips are optional, limited and include notes in Chinese', () => {
  const x = explanation({...item, teacherNote: 'A useful note.', synonyms: ['a', 'b', 'c', 'd']}, chosen, 'zh');
  assert.match(x.tip, /节目笔记：A useful note/);
  assert.match(x.tip, /相似表达：a、b、c/);
  assert.doesNotMatch(x.tip, /、d/);
  assert.doesNotMatch(JSON.stringify(explanation({}, {}, 'en')), /undefined|null|NaN|“”|\(\)/);
});

test('long distractor gloss uses its first sentence', () => {
  const x = explanation(item, {...chosen, meaningEn: `A short first sentence. ${'More words '.repeat(20)}`});
  assert.match(x.why, /means a short first sentence/);
  assert.doesNotMatch(x.why, /More words/);
});

test('typed-answer explanations compare what was written with what was said', () => {
  const x = explanation(item, {text: 'try', typed: 'tri'}, 'en', false, 'recall');
  assert.match(x.why, /You wrote “tri”; the hosts said “try”/);
  assert.match(explanation(item, {text: 'try', typed: ''}, 'zh', false, 'recall').why, /你写的是“（空白）”/);
  assert.equal(explanation(item, {text: 'try', typed: 'try'}, 'en', true, 'recall').why, '');
});
