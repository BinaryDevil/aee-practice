const isChinese = language => language === 'zh' || language === 'zh-CN';
const clean = value => typeof value === 'string' ? value.trim() : '';
function embeddedGloss(value) {
  let gloss = clean(value);
  if (gloss.length > 160) gloss = gloss.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim() || gloss;
  if (/^(?:[A-Z][a-z]|A\s)/.test(gloss) && !/^I\b/.test(gloss)) {
    // A capitalized first word can be a proper noun; preserve common names.
    const first = gloss.split(/\s/)[0];
    if (!['English', 'American', 'British', 'Chinese'].includes(first)) {
      gloss = gloss[0].toLowerCase() + gloss.slice(1);
    }
  }
  return gloss.replace(/[.!?]+$/, '');
}
function register(item) {
  return (item?.tags || []).find(tag => ['informal', 'slang', 'formal'].includes(tag));
}
function contentWords(gloss) {
  return embeddedGloss(gloss).replace(/^(to |the |a |an |being |used (?:to|when) )/i, '').split(/\s+/).slice(0, 4).join(' ').replace(/[,;:.]+$/, '');
}
function contrast(item, chosen, language, type) {
  const chinese = isChinese(language);
  const selected = register(chosen);
  const correct = register(item);
  const names = {
    informal: '非正式',
    formal: '正式',
    slang: '俚语'
  };
  if (Boolean(selected) !== Boolean(correct)) {
    const subject = selected ? chosen : item;
    const tag = selected || correct;
    return chinese ? `“${subject.text}”属于${names[tag]}表达。` : `“${subject.text}” is ${tag}.`;
  }
  const pos = chinese ? {
    verb: '动词',
    adj: '形容词',
    noun: '名词'
  } : {
    verb: 'action word',
    adj: 'describing word',
    noun: 'thing word'
  };
  if (['cloze', 'listening'].includes(type) && pos[item.pos] && pos[chosen?.pos] && item.pos !== chosen.pos) {
    const article = word => word === 'action word' ? 'an' : 'a';
    return chinese ? `空格需要${pos[item.pos]}；“${chosen.text}”是${pos[chosen.pos]}。` : `The blank needs ${article(pos[item.pos])} ${pos[item.pos]}; “${chosen.text}” is ${article(pos[chosen.pos])} ${pos[chosen.pos]}.`;
  }
  if (type === 'meaning') {
    const a = chinese ? clean(chosen?.meaningZh).split(/[；，。]/)[0] : contentWords(chosen?.meaningEn);
    const b = chinese ? clean(item.meaningZh).split(/[；，。]/)[0] : contentWords(item.meaningEn);
    if (a && b) return chinese ? `这个选项说的是 ${a}，而不是 ${b}。` : `This one is about ${a}, not ${b}.`;
  }
  return '';
}
export function explanation(item, chosen, lang = 'en', correct = false, type = 'meaning', occurrence = item.occurrences?.[0]) {
  const chinese = isChinese(lang);
  const en = clean(item.meaningEn);
  const zh = clean(item.meaningZh);
  const meaning = chinese ? `① 含义：${zh || '暂无中文释义'}${item.meaningZhSource === 'mt' && zh ? '（机器翻译）' : ''}` : `① Meaning: ${en}`;
  const secondary = chinese ? en ? `English: ${en}` : '' : zh ? `中文：${zh}${item.meaningZhSource === 'mt' ? '（机器翻译）' : ''}` : '';
  const name = clean(chosen?.text);
  const gloss = chinese ? clean(chosen?.meaningZh) : embeddedGloss(chosen?.meaningEn);
  const translation = !chinese && clean(chosen?.meaningZh) ? ` (${clean(chosen.meaningZh)})` : '';
  const typed = type === 'recall' ? clean(chosen?.typed) : '';
  const heard = clean(occurrence?.answer) || clean(item.text);
  const recallWhy = type === 'recall' && !correct ? chinese ? `③ 你写的是“${typed || '（空白）'}”，节目里说的是“${heard}”。` : `③ You wrote “${typed || '(nothing)'}”; the hosts said “${heard}”.` : '';
  const why = recallWhy ? recallWhy : name && gloss && type !== 'recall' ? `${chinese ? `③ 为什么不是“${name}”？“${name}”的意思是${gloss.replace(/[。！？]+$/, '')}${translation}。` : `③ Why not “${name}”? “${name}” means ${gloss}${translation}.`} ${contrast(item, chosen, lang, type)}`.trim() : '';
  const tags = (item.tags || []).filter(tag => ['informal', 'formal', 'slang'].includes(tag));
  const tagNames = {
    informal: '非正式表达',
    formal: '正式表达',
    slang: '俚语'
  };
  const parts = [];
  if (clean(item.teacherNote)) parts.push(`${chinese ? '节目笔记：' : 'From the episode notes: '}${clean(item.teacherNote)}`);
  if (tags.length) parts.push(chinese ? tags.map(tag => tagNames[tag]).join('、') : tags.map(tag => `This is ${tag}.`).join(' '));
  const synonyms = (item.synonyms || []).filter(x => clean(x)).slice(0, 3);
  if (synonyms.length) parts.push(`${chinese ? '相似表达：' : 'Similar: '}${synonyms.join(chinese ? '、' : ', ')}`);
  return {
    heading: correct ? chinese ? '✓ 答对了！' : '✓ Correct!' : chinese ? `✘ 不太对。正确答案：${item.display || item.text || ''}` : `✘ Not quite. Correct answer: ${item.display || item.text || ''}`,
    meaning,
    secondary,
    episode: `${chinese ? '② 在节目中：' : '② In the episode:'} ${clean(occurrence?.sentence)}`,
    why,
    tip: parts.length ? `${chinese ? '④ 提示：' : '④ Tip: '}${parts.join(' ')}` : '',
    correct
  };
}
