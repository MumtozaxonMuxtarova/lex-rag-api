'use strict';
const $ = (id) => document.getElementById(id);
const state = {key: '', coverage: null, busy: false, pending: false, lastRequest: null};
const examples = {
  'uz-Latn': {leave: 'Yillik asosiy mehnat ta’tilining eng kam muddati qancha?', limitation: 'Umumiy da’vo muddati qancha?'},
  'uz-Cyrl': {leave: 'Ҳар йилги асосий энг кам меҳнат таътилининг давомийлиги қанча?', limitation: 'Умумий даъво муддати қанча?'},
  'ru': {leave: 'Какова минимальная продолжительность ежегодного основного трудового отпуска?', limitation: 'Каков общий срок исковой давности?'}
};
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const number = (value) => new Intl.NumberFormat('uz-UZ').format(value);

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function feedback(message, error = false) {
  $('feedback').textContent = message;
  $('feedback').classList.toggle('error', error);
  $('feedback').hidden = !message;
}
function setBusy(busy) {
  state.busy = busy;
  document.body.classList.toggle('busy', busy);
  $('submit-button').disabled = busy;
  $('submit-label').textContent = busy ? 'Qidirilmoqda…' : 'Javobni topish';
  for (const id of ['question', 'language', 'connect-button', 'new-search']) $(id).disabled = busy;
  $('as-of-date').disabled = busy || !state.coverage;
  document.querySelectorAll('[data-example]').forEach(button => {button.disabled = busy;});
}
function updateDateWindow() {
  const window = state.coverage?.date_windows[$('language').value];
  $('as-of-date').disabled = !window;
  if (!window) return;
  const date = $('as-of-date');
  date.min = window.from;
  date.max = window.to;
  if (!date.value || date.value < window.from || date.value > window.to) date.value = window.to;
  $('date-hint').textContent = `Mavjud tahrirlar: ${window.from} — ${window.to}`;
}
function renderCoverage(coverage) {
  state.coverage = coverage;
  const count = (id) => coverage.documents.filter(d => d.doc_id === id && d.language === 'uz-Latn')[0]?.articles;
  const labor = count('lex:6257288');
  const civil = count('lex:111189');
  $('labor-count').textContent = `${labor ? number(labor) + ' modda · ' : ''}Lotin · Kirill · Rus`;
  $('civil-count').textContent = `${civil ? number(civil) + ' modda · ' : ''}Lotin · Kirill · Rus`;
  $('coverage-summary').textContent = `${number(coverage.total_chunks)} ta tahrirlar bo‘yicha modda bo‘lagi, ${coverage.document_variants} ta til varianti. Baza sanasi: ${coverage.snapshot_date || 'ma’lumot yo‘q'}. ${coverage.scope_note}`;
  updateDateWindow();
}
function showConnection(pending = false) {
  state.pending = pending;
  $('connection-error').hidden = true;
  $('api-key').value = '';
  $('connection-dialog').showModal();
  $('api-key').focus();
}
function messageFor(code) {
  return {
    SNAPSHOT_DATE_UNAVAILABLE: 'Tanlangan sana bazada to‘liq qamrab olinmagan. Mavjud oraliqdagi sanani tanlang yoki bazani yangilang.',
    TRANSLATION_UNAVAILABLE: 'Tanlangan javob tilida shu sanadagi rasmiy modda nusxasi topilmadi. Boshqa javob tilini tanlang.',
    INDEX_UNAVAILABLE: 'Hujjatlar bazasi topilmadi. Backendda lex.uz importini ishga tushiring.',
    RETRIEVAL_FAILED: 'Qidiruvni bajarib bo‘lmadi. Qayta urinib ko‘ring.',
    PROCESS_RESTARTED: 'So‘rov davomida backend qayta ishga tushgan. Yangi qidiruvni boshlang.'
  }[code] || 'So‘rov bajarilmadi. Backend holatini tekshirib, qayta urinib ko‘ring.';
}
async function api(path, options = {}, key = state.key) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 125000);
  try {
    const response = await fetch(path, {...options, signal: controller.signal,
      headers: {'Content-Type': 'application/json', Authorization: `Bearer ${key}`, ...options.headers}});
    let data;
    try {data = await response.json();} catch {throw new Error('Backenddan kutilgan javob kelmadi.');}
    if (!response.ok) {
      const error = new Error(response.status === 401 || response.status === 403 ? 'API kaliti noto‘g‘ri. Kalitni tekshiring.' : response.status === 429 ? 'Qidiruvlar juda tez yuborildi. Bir ozdan keyin qayta urinib ko‘ring.' : response.status === 400 ? 'Savol, til yoki sana qiymatini tekshiring.' : 'Backend so‘rovni bajara olmadi.');
      error.status = response.status;
      error.retryAfter = Math.max(1, Math.min(10, Number(response.headers.get('Retry-After')) || 1));
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Javob kutish muddati tugadi. Shu savolni qayta yuborsangiz, saqlangan natija tekshiriladi.');
    if (error instanceof TypeError) throw new Error('Backend bilan aloqa uzildi. Server ishga tushganini tekshiring.');
    throw error;
  } finally {clearTimeout(timeout);}
}
function sourceLink(citation) {
  try {
    const url = new URL(citation.source_url || citation.url);
    if (url.protocol !== 'https:' || !['lex.uz', 'www.lex.uz'].includes(url.hostname)) return null;
    if (!url.searchParams.has('ONDATE') && citation.edition_date) {
      const date = citation.edition_date.split('-').reverse().join('.');
      url.searchParams.set('ONDATE', citation.edition_label || date);
    }
    if (citation.source_anchor) url.hash = citation.source_anchor;
    return url.href;
  } catch {return null;}
}
function renderResult(result, question) {
  const root = $('results');
  root.replaceChildren();
  root.hidden = false;
  const head = element('div', 'result-head');
  head.append(element('h2', '', 'Qidiruv natijasi'), element('span', 'result-meta', `${result.timing?.total_ms?.toFixed(0) || 0} ms · Asl manba`));
  root.append(head);
  const card = element('article', 'answer-card');
  const body = element('div', 'answer-body');
  body.append(element('span', 'answer-label', 'SIZNING SAVOLINGIZ'), element('p', '', question));
  body.append(element('span', 'answer-label', 'QONUNDAN TOPILGAN MATN'), element('div', 'answer-text', result.answer || ''));
  const foot = element('div', 'answer-foot');
  const copy = element('button', 'copy-button', 'Nusxa olish');
  copy.type = 'button';
  copy.addEventListener('click', async () => {
    try {await navigator.clipboard.writeText(result.answer); copy.textContent = 'Nusxa olindi ✓';}
    catch {feedback('Avtomatik nusxalash ishlamadi. Javob matnini belgilab nusxalang.');}
  });
  foot.append(element('span', '', 'Javob qayta yozilmagan — qonundagi asl matn keltirilgan.'), copy);
  card.append(body, foot);
  root.append(card);
  const sources = element('div', 'citation-list');
  sources.append(element('h3', '', 'Javobning qonuniy manbasi'));
  for (const citation of result.citations || []) {
    const block = element('article', 'citation');
    const title = element('div', 'citation-title');
    title.append(element('span', 'ref-number', `[${citation.ref}]`), element('span', '', citation.doc_title));
    const info = element('div', 'citation-info');
    info.append(element('span', '', citation.article), element('span', '', `Tahrir: ${citation.edition_date}`), element('span', '', citation.doc_status === 'amalda' ? 'Tanlangan tahrirda amalda' : citation.doc_status));
    if (citation.part) info.append(element('span', '', citation.part));
    block.append(title, info);
    const url = sourceLink(citation);
    if (url) {
      const link = element('a', '', 'Lex.uz’da manbani ochish ↗');
      link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      block.append(link);
    }
    block.append(element('blockquote', '', citation.quote));
    sources.append(block);
  }
  root.append(sources);
  if (result.contexts?.length) {
    const details = element('details', 'contexts');
    details.append(element('summary', '', `Qidiruvda topilgan moddalar (${result.contexts.length})`));
    for (const context of result.contexts) {
      const block = element('article', 'context-item');
      block.append(element('h4', '', `${context.rank}. ${context.article}${context.used_in_answer ? ' · Javobda ishlatilgan' : ''}`), element('p', '', context.text));
      details.append(block);
    }
    root.append(details);
  }
  root.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
}
async function search() {
  if (state.busy) return;
  const question = $('question').value.trim();
  if (!question) {feedback('Avval savolingizni yozing.', true); return;}
  if (!state.key) {showConnection(true); return;}
  if (!$('search-form').reportValidity()) return;
  setBusy(true);
  $('results').hidden = true;
  feedback('Tegishli qonun moddalari qidirilmoqda…');
  const language = $('language').value;
  const date = $('as-of-date').value;
  const signature = JSON.stringify([question, language, date]);
  if (state.lastRequest?.signature !== signature) {
    const id = crypto.randomUUID();
    state.lastRequest = {signature, body: {run_id: `web-${id}`, batch_id: `web-${id}`, batch_index: 1, total_batches: 1,
      options: {top_k: 5, return_contexts: true, as_of_date: date}, items: [{id: 'q001', question, language}]}};
  }
  try {
    let batch;
    for (let retry = 0; retry < 3; retry++) {
      try {batch = await api('/v1/rag/batch', {method: 'POST', body: JSON.stringify(state.lastRequest.body)}); break;}
      catch (error) {if (error.status !== 429 || retry === 2) throw error; await sleep(error.retryAfter * 1000);}
    }
    const deadline = Date.now() + 180000;
    while (batch.status === 'processing') {
      if (Date.now() > deadline) throw new Error('So‘rov hali qayta ishlanmoqda. Shu savolni qayta yuborib natijani tekshiring.');
      feedback('So‘rov qabul qilindi. Qidiruv natijasi kutilmoqda…');
      await sleep(1500);
      batch = await api(`/v1/rag/batch/${encodeURIComponent(batch.batch_id)}`);
    }
    if (batch.status === 'failed') throw new Error(messageFor(batch.error?.code));
    const result = batch.results?.find(item => item.id === 'q001');
    if (!result) throw new Error('Backend javobida savol natijasi topilmadi.');
    if (result.status === 'error' || result.status === 'timeout') throw new Error(messageFor(result.error?.code));
    if (result.no_answer || result.status === 'no_answer') {
      feedback('Mavjud ikki kodeksdan mos javob topilmadi. Savolni aniqroq yozing. Bu boshqa qonunlarda ham javob yo‘q degani emas.');
    } else {feedback(''); renderResult(result, question);}
  } catch (error) {
    feedback(error.message, true);
    if (error.status === 401 || error.status === 403) {
      state.key = '';
      $('connect-button').textContent = 'Qayta ulanish ↗';
    }
  } finally {setBusy(false);}
}
$('as-of-date').disabled = true;
$('search-form').addEventListener('submit', event => {event.preventDefault(); search();});
$('question').addEventListener('input', () => {$('character-count').textContent = `${number($('question').value.length)} / 2 000`;});
$('question').addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {event.preventDefault(); search();}
});
$('language').addEventListener('change', updateDateWindow);
$('connect-button').addEventListener('click', () => showConnection());
$('close-dialog').addEventListener('click', () => {$('connection-dialog').close(); state.pending = false;});
$('new-search').addEventListener('click', () => {
  if (state.busy) return;
  $('question').value = '';
  $('character-count').textContent = '0 / 2 000';
  $('results').hidden = true;
  state.lastRequest = null;
  feedback('');
  $('question').focus();
  window.scrollTo({top: 0, behavior: 'smooth'});
});
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => {
  $('question').value = examples[$('language').value][button.dataset.example];
  $('question').dispatchEvent(new Event('input'));
  $('question').focus();
}));
$('connection-form').addEventListener('submit', async event => {
  event.preventDefault();
  const key = $('api-key').value.trim();
  $('authorize-button').disabled = true;
  $('connection-error').hidden = true;
  try {
    const coverage = await api('/v1/coverage', {}, key);
    state.key = key;
    renderCoverage(coverage);
    $('connect-button').textContent = 'Ulandi ✓';
    $('api-key').value = '';
    $('connection-dialog').close();
    const pending = state.pending;
    state.pending = false;
    if (pending) await search();
  } catch (error) {
    $('connection-error').textContent = error.message;
    $('connection-error').hidden = false;
  } finally {$('authorize-button').disabled = false;}
});
fetch('/v1/health', {signal: AbortSignal.timeout(10000)}).then(response => {
  if (!response.ok) throw new Error('offline');
  return response.json();
}).then(health => {
  $('service-status').replaceChildren(element('i'), document.createTextNode(health.index_ready ? 'Backend onlayn' : 'Baza yuklanmagan'));
  $('service-status').classList.toggle('online', health.index_ready);
}).catch(() => {$('service-status').replaceChildren(element('i'), document.createTextNode('Backend oflayn'));});
