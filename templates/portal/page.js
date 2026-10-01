(function(){
'use strict';
var D = JSON.parse(document.getElementById('prep-data').textContent);
var STAGES = D.stages || {}, SETUP = D.setup || {steps: [], has: {}}, DOCS = D.documents || [], OUTLINE = D.outline || [], CONTENT = D.content || {}, DECK = D.deck || null, COMPANIES = D.companies || [], REPORT = D.report || {};
/* Course languages (chosen at the start of the wizard, main one first). P is the main one: it holds
   title/summary and content/<section>.<P>.md; another language L holds title_L/summary_L and *.L.md.
   One language — no switcher. */
var P = D.lang || 'en', LANGS = D.langs || [P];
[P, 'en'].concat(LANGS).forEach(function(l){ CONTENT[l] = CONTENT[l] || {}; });
var DAY = 86400000, STEPS = [0, 1, 3, 7, 16], NOW = function(){ return Date.now(); };

/* ---------- UI strings ---------- */
var I18N = D.ui || {};   // UI strings: templates/portal/i18n.json (+ prep/i18n.<lang>.json), inserted by build_page.py

/* ---------- utilities ---------- */
function $(id){ return document.getElementById(id); }
function el(tag, cls, text){ var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function shuffle(a){ for (var i = a.length - 1; i > 0; i--){ var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
function lsGet(k, d){ try { var v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
function lsSet(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
function bar(parts){ var b = el('div', 'bar'); parts.forEach(function(p){ if (p[1] > 0){ var i = el('i', p[0]); i.style.width = (p[1] * 100) + '%'; b.appendChild(i); } }); return b; }

/* ---------- state (separate from content, keyed by id) ---------- */
var ui = {lang: (function(l){ return LANGS.indexOf(l) >= 0 ? l : P; })(lsGet('prep.lang', P)), tab: lsGet('prep.tab', 'plan'), theme: lsGet('prep.theme', ''), status: 'all', pri: 0, vac: false, q: '', dir: lsGet('prep.dir', 'mix'), size: lsGet('prep.size', 20)};
var S = {done: {}, skip: {}, collapsed: {}, expanded: {}, goals: {}, startedAt: null};   // expanded: open section cards      // doc prep/state
var T = {};
var GOAL = (function(v){ return v >= 1 && v <= 200 ? v : 20; })(+lsGet('prep.goal', 20));   // new words a day; stored in trainer/state.goal                                                        // doc trainer/state: id -> {b,d,s}
var V = {};                                                        // coll vocab: batchKey -> {known,unknown}
var db = null, api = false, dirty = {}, timer = null;   // api: local server (tools/serve.py)
/* seen[doc]: the doc was read and existed. A doc this tab never saw is re-read and merged before
   writing — an old tab must never overwrite real progress with its empty state. */
var seen = {S: false, T: false};
if (D.i18n && P !== 'ru' && P !== 'en') I18N[P] = Object.assign({}, I18N.en, D.i18n);   // prep/i18n.<lang>.json
function L(){ return I18N[ui.lang] || I18N.en; }
function tt(node){ return (ui.lang !== P && node['title_' + ui.lang]) ? node['title_' + ui.lang] : node.title; }

/* Data from the artifact db arrives frozen (Object.freeze): writing into it throws in strict mode
   and kills the click handler. Everything read from storage is copied first. */
function clone(x){ return x == null ? x : JSON.parse(JSON.stringify(x)); }
function blankS(){ return {done: {}, skip: {}, collapsed: {}, expanded: {}, goals: {}, startedAt: null}; }
/* A date as milliseconds, or null. Accepts ms, seconds and ISO strings; anything before 2015 or in the
   future (true → 1 → 1 January 1970, a typo) is not a date. Never let such a value into the forecast. */
var MIN_TS = Date.UTC(2015, 0, 1);
function toTs(v){
  if (typeof v === 'string'){ v = /^\d+$/.test(v) ? +v : Date.parse(v); }
  if (typeof v !== 'number' || !isFinite(v)) return null;
  if (v > 1e9 && v < 1e11) v *= 1000;   // seconds
  return v >= MIN_TS && v <= NOW() + DAY ? v : null;
}
function asS(x){
  var s = Object.assign(blankS(), clone(x) || {});
  ['done', 'skip', 'collapsed', 'expanded', 'goals'].forEach(function(k){ if (!s[k] || typeof s[k] !== 'object' || Array.isArray(s[k])) s[k] = {}; });
  // older pages kept dates apart (doneAt) or as true/ISO strings: a mark keeps its real date or stays "date unknown" (true)
  var at = (s.doneAt && typeof s.doneAt === 'object') ? s.doneAt : {};
  Object.keys(s.done).forEach(function(id){ if (!s.done[id]) { delete s.done[id]; return; } s.done[id] = toTs(s.done[id]) || toTs(at[id]) || true; });
  delete s.doneAt;
  s.startedAt = toTs(s.startedAt);
  return s;
}
/* remote progress + what this tab did: a mark set anywhere survives */
function mergeS(remote, local){
  var r = asS(remote), l = asS(local);
  ['done', 'skip', 'collapsed', 'expanded', 'goals'].forEach(function(k){ r[k] = Object.assign({}, r[k], l[k]); });
  r.startedAt = Math.min(r.startedAt || Infinity, l.startedAt || Infinity); if (r.startedAt === Infinity) r.startedAt = null;
  return r;
}
/* a double click is two clicks: ignore the second one instead of toggling back */
function tooSoon(x){ var n = Date.now(); if (x._t && n - x._t < 350) return true; x._t = n; return false; }
function setSync(msg){ var s = $('sync'); if (s) s.textContent = msg || ''; }
function save(which){
  dirty[which] = true;
  lsSet('prep.fallback', {S: S, T: T});
  if (!db && !api) return;
  clearTimeout(timer);
  timer = setTimeout(flush, 800);
}
function post(path, body){ return fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }); }
async function flush(){
  if (!db && !api) return;
  var d = dirty; dirty = {};
  try {
    if (api){
      if (d.S) await post('/api/state', S);
      if (d.T) await post('/api/trainer', {items: T, updated: NOW(), goal: GOAL});
    } else {
      if (d.S){
        if (!seen.S){ var rs = await db.doc('prep/state').get(); if (rs.exists){ S = mergeS(rs.data(), S); render(); } seen.S = true; }
        await db.doc('prep/state').set(clone(S));
      }
      if (d.T){
        if (!seen.T){ var rt = await db.doc('trainer/state').get(); if (rt.exists && rt.data().items) T = Object.assign(clone(rt.data().items), T); seen.T = true; }
        await db.doc('trainer/state').set({items: clone(T), updated: NOW(), goal: GOAL});
      }
    }
    setSync(L().saved);
  } catch (e){ setSync(L().local); }
}
async function saveVocab(key, rec){
  V[key] = rec; lsSet('prep.vocab', V);
  try {
    if (api) await post('/api/vocab', V);
    else if (db) await db.collection('vocab').doc(key).set(rec);
    setSync(L().saved);
  } catch (e){ setSync(L().local); }
}
async function sendInbox(rec){
  if (api) return post('/api/inbox', rec);
  if (db) return db.collection('inbox').add(rec);
  throw new Error('offline');
}
/* download a file: the artifact's downloads capability, otherwise a plain link */
async function download(filename, data, type){
  try {
    var dl = window.claude && window.claude.use ? await window.claude.use('downloads') : null;
    if (dl){ await dl.save({filename: filename, data: data}); return; }
  } catch (e){}
  var url = URL.createObjectURL(new Blob([data], {type: type || 'text/plain;charset=utf-8'}));
  var a = el('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function(){ URL.revokeObjectURL(url); }, 2000);
}
/* Clipboard: the async API is often blocked inside an artifact frame, so fall back to a hidden
   textarea + execCommand, and only then to a download. */
function copyFallback(text){
  var ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', '');
  ta.style.position = 'fixed'; ta.style.top = '0'; ta.style.left = '0'; ta.style.opacity = '0';
  document.body.appendChild(ta); ta.focus(); ta.select(); ta.setSelectionRange(0, text.length);
  var ok = false; try { ok = document.execCommand('copy'); } catch (e){}
  ta.remove(); return ok;
}
async function copyText(text, btn){
  var ok = false;
  try { if (navigator.clipboard && window.isSecureContext !== false){ await navigator.clipboard.writeText(text); ok = true; } } catch (e){}
  if (!ok) ok = copyFallback(text);
  if (!ok){ download('text.txt', text); return; }
  var t = btn.dataset.label || btn.textContent; btn.dataset.label = t; btn.textContent = '✓ ' + L().copied;
  setTimeout(function(){ btn.textContent = t; }, 1500);
}
/* Rendered lesson HTML → Markdown-like plain text, ready to paste into a chat. */
function toText(node){
  var out = [];
  function inline(x){
    if (x.nodeType === 3) return x.nodeValue;
    if (x.nodeType !== 1) return '';
    var tag = x.tagName, inner = Array.prototype.map.call(x.childNodes, inline).join('');
    if (tag === 'CODE') return '`' + x.textContent + '`';
    if (tag === 'B' || tag === 'STRONG') return '**' + inner + '**';
    if (tag === 'EM' || tag === 'I') return '*' + inner + '*';
    if (tag === 'BR') return '\n';
    if (tag === 'BUTTON') return '';
    return inner;
  }
  function block(x, depth){
    if (x.nodeType === 3){ var s = x.nodeValue.trim(); if (s) out.push(s); return; }
    if (x.nodeType !== 1 || x.tagName === 'BUTTON' || x.classList.contains('fallback')) return;
    var tag = x.tagName;
    if (/^H[1-6]$/.test(tag)){ out.push('', '#'.repeat(Math.min(6, +tag[1])) + ' ' + x.textContent.trim()); return; }
    if (tag === 'P'){ out.push('', inline(x).trim()); return; }
    if (tag === 'PRE'){ out.push('', '```', x.textContent.replace(/\s+$/, ''), '```'); return; }
    if (tag === 'UL' || tag === 'OL'){
      out.push('');
      Array.prototype.forEach.call(x.children, function(li, i){
        if (li.tagName !== 'LI') return;
        var sum = li.querySelector('summary'), body = sum ? sum.parentNode.querySelector('div') : null;
        var head = sum ? '**' + inline(sum).trim() + '**' : Array.prototype.filter.call(li.childNodes, function(c){ return !(c.nodeType === 1 && /^(UL|OL)$/.test(c.tagName)); }).map(inline).join('').trim();
        if (body) head += ' ' + inline(body).trim();
        out.push('  '.repeat(depth) + (tag === 'OL' ? (i + 1) + '. ' : '- ') + head.replace(/\s*\n\s*/g, ' '));
        Array.prototype.forEach.call(li.children, function(c){ if (/^(UL|OL)$/.test(c.tagName)){ var keep = out.length; block(c, depth + 1); if (out[keep] === '') out.splice(keep, 1); } });
      });
      return;
    }
    if (tag === 'TABLE'){
      out.push('');
      Array.prototype.forEach.call(x.querySelectorAll('tr'), function(tr, i){
        var cells = Array.prototype.map.call(tr.children, function(c){ return inline(c).trim().replace(/\|/g, '\\|'); });
        out.push('| ' + cells.join(' | ') + ' |');
        if (i === 0) out.push('|' + cells.map(function(){ return ' --- '; }).join('|') + '|');
      });
      return;
    }
    if (tag === 'BLOCKQUOTE'){ out.push('', '> ' + inline(x).trim()); return; }
    Array.prototype.forEach.call(x.childNodes, function(c){ block(c, depth); });
  }
  block(node, 0);
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}
window.addEventListener('pagehide', function(){ flush(); });

/* ---------- tree model ---------- */
var BY_ID = {}, PARENT = {};
(function index(nodes, parent){ nodes.forEach(function(n){ BY_ID[n.id] = n; PARENT[n.id] = parent; if (n.children) index(n.children, n.id); }); })(OUTLINE, null);
function isLeaf(n){ return !n.children || !n.children.length; }
function leaves(n, out){ out = out || []; if (isLeaf(n)){ if (n.kind !== 'stage' && n.kind !== 'cross') out.push(n); } else n.children.forEach(function(c){ leaves(c, out); }); return out; }
function progress(n){
  var ls = leaves(n).filter(function(x){ return !S.skip[x.id]; });
  var d = ls.filter(function(x){ return S.done[x.id]; }).length;
  return {done: d, total: ls.length};
}
function allLeaves(){ var o = []; OUTLINE.forEach(function(n){ leaves(n, o); }); return o; }

/* ---------- header ---------- */
function renderHead(){
  $('title').textContent = ui.lang === 'en' && D.title_en ? D.title_en : D.title;
  document.title = $('title').textContent;
  document.documentElement.lang = ui.lang;
  document.querySelectorAll('[data-lang]').forEach(function(b){ b.setAttribute('aria-pressed', String(b.dataset.lang === ui.lang)); });
  var tabs = $('tabs'); tabs.innerHTML = '';
  var list = [['plan', L().plan]];
  var pa = SETUP.profile_answers || {}, train = pa['english-train'];
  var wantEn = train ? train === 'full' : (pa['interview-language'] && pa['interview-language'] !== 'native');
  if ((DECK && DECK.words && DECK.words.length) || wantEn){ list.push(['vocab', L().vocab]); list.push(['trainer', L().trainer]); }
  list.push(['companies', L().companies]);
  list.push(['docs', L().docs]);
  if (!list.some(function(x){ return x[0] === ui.tab; })) ui.tab = 'plan';
  list.forEach(function(x){
    var b = el('button', null, x[1]); b.type = 'button'; b.setAttribute('role', 'tab'); b.setAttribute('aria-selected', String(ui.tab === x[0]));
    b.onclick = function(){ ui.tab = x[0]; lsSet('prep.tab', ui.tab); render(); scrollTo(0, 0); };
    tabs.appendChild(b);
  });
}

/* ---------- study tracks ----------
   Kinds of work with their own unit and daily goal (profiles → tracks): theory, coding problems,
   system design, soft skills, words. A topic belongs to the track of its section (top-level stage or
   cross-cutting section) unless the outline node says `track:`. Goals: S.goals[id] over the profile's
   default; words use the trainer goal. No mixed overall percent: readiness is the date of the slowest track. */
var TRACKS = (D.tracks || []).filter(function(x){ return x && x.id; }), TRACK_BY_SEC = {};
TRACKS.forEach(function(tr){ (tr.sections || []).forEach(function(s){ TRACK_BY_SEC[s] = tr.id; }); });
var TOPIC_TRACKS = TRACKS.filter(function(tr){ return tr.kind !== 'words'; });
function trackOf(n){
  for (var x = n; x; x = BY_ID[PARENT[x.id]]){ if (x.track) return x.track; if (!PARENT[x.id] && TRACK_BY_SEC[x.id]) return TRACK_BY_SEC[x.id]; }
  return TOPIC_TRACKS.length ? TOPIC_TRACKS[0].id : null;
}
function trackGoal(tr){ if (tr.kind === 'words') return GOAL; var g = +(S.goals || {})[tr.id]; return g >= 1 ? g : (tr.goal || 1); }
function trackName(tr){ return ui.lang !== P && tr.title_en ? tr.title_en : tr.title; }
function trackUnit(tr){ return ui.lang !== P && tr.unit_en ? tr.unit_en : tr.unit; }
function trackStats(tr){
  var goal = trackGoal(tr), t0 = today0(), by = {};
  if (tr.kind === 'words'){
    if (!DECK || !(DECK.words || []).length) return null;
    by = newWordsByDay();
    var fw = deckForecasts(decks());
    var known = knownSet(), ws = (DECK.words || []).filter(function(w){ return !known[w.id]; });
    var started = ws.filter(function(w){ return cardState(w).s; }).length;
    return {tr: tr, goal: goal, today: by[t0] || 0, by: by, total: ws.length, done: started, rest: ws.length - started,
            days: fw.all ? fw.all.learn : null};
  }
  var ls = allLeaves().filter(function(n){ return !S.skip[n.id] && trackOf(n) === tr.id; });
  if (!ls.length) return null;
  var done = 0;
  ls.forEach(function(n){ var v = S.done[n.id]; if (!v) return; done++; var ts = toTs(v); if (ts){ var d = new Date(ts); d.setHours(0, 0, 0, 0); by[d.getTime()] = (by[d.getTime()] || 0) + 1; } });
  var rest = ls.length - done;
  return {tr: tr, goal: goal, today: by[t0] || 0, by: by, total: ls.length, done: done, rest: rest, days: rest ? Math.ceil(rest / goal) : 0};
}
function allTrackStats(){ return TRACKS.map(trackStats).filter(Boolean); }
function drawTracks(list){
  var Lx = L(), box = el('div', 'tracks'), t0 = today0();
  list.forEach(function(s){
    var tr = s.tr, words = tr.kind === 'words';
    var c = el('button', 'track' + (ui.track === tr.id ? ' on' : '') + (s.today >= s.goal ? ' met' : '')); c.type = 'button';
    c.title = words ? Lx.trainerTitle : Lx.trkFilter;
    var top = el('div', 'track-top');
    top.appendChild(ring(72, s.today / s.goal, s.today + '/' + s.goal, trackName(tr)));
    var cap = el('div', 'track-cap'); cap.appendChild(el('b', null, trackName(tr)));
    cap.appendChild(el('span', 'meta', Lx.trkToday + ': ' + s.today + ' / ' + s.goal + ' ' + trackUnit(tr)));
    top.appendChild(cap); c.appendChild(top);
    var wk = el('div', 'track-week');
    for (var i = 6; i >= 0; i--){ var day = t0 - i * DAY, n = s.by[day] || 0;
      var dot = el('i', n >= s.goal ? 'full' : (n ? 'part' : '')); dot.title = new Date(day).toLocaleDateString(ui.lang === 'en' ? 'en-GB' : ui.lang, {weekday: 'short', day: 'numeric'}) + ': ' + n; wk.appendChild(dot); }
    c.appendChild(wk);
    var pb = el('div', 'bar'), pi = el('i', 'd'); pi.style.width = (s.total ? s.done / s.total * 100 : 0) + '%'; pb.appendChild(pi); c.appendChild(pb);
    var fx = s.rest === 0 ? Lx.trkDone : (s.days == null ? Lx.trEtaUnknown
      : Lx.trkLeft + ' ' + s.rest + ' · ≈ ' + fmtDay(NOW() + s.days * DAY));
    c.appendChild(el('div', 'track-eta', s.done + ' / ' + s.total + ' · ' + fx));
    c.onclick = function(){
      if (words){ ui.tab = 'trainer'; lsSet('prep.tab', 'trainer'); render(); scrollTo(0, 0); return; }
      ui.track = ui.track === tr.id ? null : tr.id; rerenderKeepScroll();
    };
    box.appendChild(c);
  });
  // goals: one slider per track
  var det = el('details', 'track-goals'); det.appendChild(el('summary', null, Lx.trkGoals));
  list.forEach(function(s){
    var tr = s.tr, lab = el('label', 'goal-adj'), val = el('b', null, s.goal + ' ' + trackUnit(tr));
    lab.appendChild(el('span', null, trackName(tr) + ': ')); lab.appendChild(val);
    var rg = el('input'); rg.type = 'range'; rg.min = 1; rg.max = tr.kind === 'words' ? 50 : Math.max(30, s.goal); rg.step = 1; rg.value = s.goal;
    rg.oninput = function(){ val.textContent = rg.value + ' ' + trackUnit(tr); };
    rg.onchange = function(){ var v = +rg.value;
      if (tr.kind === 'words'){ GOAL = v; lsSet('prep.goal', GOAL); save('T'); }
      else { S.goals = S.goals || {}; S.goals[tr.id] = v; save('S'); }
      rerenderKeepScroll(); };
    lab.appendChild(rg); det.appendChild(lab);
  });
  box.appendChild(det);
  return box;
}

/* ---------- plan stats ---------- */
function planStats(){
  var all = allLeaves(), act = all.filter(function(x){ return !S.skip[x.id]; });
  var done = act.filter(function(x){ return S.done[x.id]; });
  var p1 = act.filter(function(x){ return (x.priority || 2) === 1; }), p1d = p1.filter(function(x){ return S.done[x.id]; });
  // only real dates count: a mark without a date (true) or a broken one must not pull the start to 1970
  var times = done.map(function(x){ return toTs(S.done[x.id]); }).filter(function(v){ return v != null; }).sort(function(a, b){ return a - b; });
  // with a known start, every mark counts since then; without it, only dated marks since the first of them
  // (otherwise undated old marks plus today's first tick would look like 100 topics a day)
  var st0 = toTs(S.startedAt), start, count;
  if (st0 && (!times.length || st0 <= times[0])){ start = st0; count = done.length; }
  else if (times.length){ start = times[0]; count = times.length; }
  var dated = !!start, days = dated ? Math.max(1, Math.ceil((NOW() - start) / DAY)) : 0;
  var pace = dated ? count / days : 0;
  return {all: all.length, act: act.length, done: done.length, p1: p1.length, p1d: p1d.length,
          skipped: all.length - act.length, withMat: all.filter(function(x){ return CONTENT[P][x.id] || CONTENT.en[x.id]; }).length,
          days: days, pace: pace, dated: dated, counted: count || 0, rest: act.length - done.length, restP1: p1.length - p1d.length};
}
function fmtDay(ts){ return new Date(ts).toLocaleDateString(ui.lang === 'en' ? 'en-GB' : ui.lang, {day: 'numeric', month: 'long'}); }
function plural(n, one, few, many){ if (ui.lang !== 'ru') return one; var m = n % 10, h = n % 100; return m === 1 && h !== 11 ? one : (m >= 2 && m <= 4 && (h < 10 || h >= 20) ? few : many); }
function trainerSummary(){
  if (!DECK) return null;
  seedFacets();
  var known = knownSet(), items = [];
  (DECK.words || []).forEach(function(w){ if (!known[w.id]) items.push(w); });
  ['verbs', 'phrases', 'answers'].forEach(function(k){ (DECK[k] || []).forEach(function(x){ items.push(x); }); });
  var c = {d: 0, c: 0, l: 0, n: 0}, due = 0, reps = 0, t0 = new Date(); t0.setHours(0, 0, 0, 0);
  Object.keys(T).forEach(function(id){ reps += (T[id] && T[id].n) || 0; });
  items.forEach(function(it){ var st = cardState(it); if (isDue(it)) due++;
    if (!st.s){ c.n++; return; } if (st.b >= 4) c.d++; else if (st.b >= 2) c.c++; else c.l++; });
  return {total: items.length, due: due, c: c, reps: reps, today: todayReps(),
          words: (DECK.words || []).length, verbs: (DECK.verbs || []).length};
}

/* ---------- Plan tab ---------- */
function filtering(){ return !!(ui.q || ui.status !== 'all' || ui.pri || ui.vac || ui.track); }
function matches(n){
  var sk = !!S.skip[n.id], dn = !!S.done[n.id];
  if (ui.status === 'todo' && (dn || sk)) return false;
  if (ui.status === 'done' && !dn) return false;
  if (ui.status === 'skip' && !sk) return false;
  if (ui.pri && (n.priority || 2) !== ui.pri) return false;
  if (ui.vac && n.origin !== 'vacancy') return false;
  if (ui.track && trackOf(n) !== ui.track) return false;
  if (!ui.q) return true;
  var q = ui.q.toLowerCase();
  var txt = [n.title, n.title_en, n.summary, n.summary_en, (CONTENT[P][n.id] || ''), (CONTENT.en[n.id] || '')].join(' ').toLowerCase();
  return txt.indexOf(q) >= 0;
}
function visible(n){ return isLeaf(n) ? matches(n) : n.children.some(visible); }
function badges(n, host){
  if (n.priority){ host.appendChild(el('span', 'badge pri' + n.priority, L()['pri' + n.priority])); }
  if (n.origin && n.origin !== 'profile'){ host.appendChild(el('span', 'badge origin' + (n.origin === 'vacancy' ? ' vac' : (n.origin === 'resume' ? ' mine' : '')), L().origin[n.origin] || n.origin)); }
  var w = (REPORT.weak || {})[n.id];
  if (w){ host.appendChild(el('span', 'badge weak', L().weak + ' ×' + w)); }
}
function placeholder(main, text){ var c = el('div', 'card ph'); c.appendChild(el('div', 'ph-icon', '◌')); c.appendChild(el('p', null, text)); main.appendChild(c); }
function renderSetup(main){
  var c = el('section', 'card setup');
  c.appendChild(el('h2', 'sec', L().setupTitle));
  c.appendChild(el('p', 'meta', L().setupIntro));
  var ol = el('ol', 'steps');
  (SETUP.steps || []).forEach(function(st){
    var cur = SETUP.current && (SETUP.current === st.id);
    var li = el('li', 'st-' + (cur ? 'current' : st.status));
    li.appendChild(el('span', 'mark', cur ? '●' : ({done: '✓', skipped: '–', todo: '○'}[st.status] || '○')));
    li.appendChild(el('span', null, ui.lang === 'en' ? st.title_en : st.title));
    ol.appendChild(li);
  });
  c.appendChild(ol);
  var ans = SETUP.answers || {}, keys = Object.keys(ans);
  if (keys.length){
    var dl = el('div', 'answers');
    keys.forEach(function(k){ var v = ans[k]; var r = el('div'); r.appendChild(el('b', null, k + ': ')); r.appendChild(document.createTextNode(Array.isArray(v) ? v.join(', ') : String(v))); dl.appendChild(r); });
    c.appendChild(dl);
  }
  main.appendChild(c);
}
function renderPlan(main){
  if (!SETUP.finished) renderSetup(main);
  var st = planStats(), Lx = L();
  /* header */
  var hero = el('section', 'hero');
  if (D.eyebrow) hero.appendChild(el('div', 'eyebrow', D.eyebrow));
  hero.appendChild(el('h1', null, ui.lang === 'en' && D.heading_en ? D.heading_en : (D.heading || D.title)));
  var intro = ui.lang === 'en' && D.intro_en ? D.intro_en : D.intro; if (intro) hero.appendChild(el('p', 'intro', intro));
  if (st.all){ hero.appendChild(el('p', 'note', Lx.matReady + ' ' + st.withMat + ' ' + Lx.of + ' ' + st.all + ' ' + Lx.topicsWord + '.'));
    if (st.skipped) hero.appendChild(el('p', 'note', Lx.excluded + ': ' + st.skipped + ' (' + Lx.notCounted + ').')); }
  main.appendChild(hero);
  if (!OUTLINE.length){ placeholder(main, Lx.phPlan); return; }
  /* three stats cards */
  var stats = el('div', 'stats');
  function statCard(a, b, pctv, label, color){
    var c = el('div', 'stat'), n = el('div', 'num'); n.appendChild(document.createTextNode(String(a))); n.appendChild(el('small', null, '/ ' + b));
    n.appendChild(el('em', null, Math.round(pctv * 100) + '%')); c.appendChild(n); c.appendChild(el('div', 'lbl', label));
    var br = bar([[color, pctv]]); c.appendChild(br); return c; }
  stats.appendChild(statCard(st.done, st.act, st.act ? st.done / st.act : 0, Lx.statAll, 'c'));
  stats.appendChild(statCard(st.p1d, st.p1, st.p1 ? st.p1d / st.p1 : 0, Lx.statMain, 'l'));
  // readiness: when every track is done at its daily goal — the slowest track decides
  var fc = el('div', 'stat'), tsl = allTrackStats(), slow = null;
  tsl.forEach(function(s){ if (s.days != null && s.rest > 0 && (!slow || s.days > slow.days)) slow = s; });
  if (slow){
    var n3 = el('div', 'num'); n3.appendChild(document.createTextNode(String(slow.days))); n3.appendChild(el('small', null, plural(slow.days, Lx.day1, Lx.day2, Lx.day5)));
    n3.appendChild(el('em', null, Lx.until + ' ' + fmtDay(NOW() + slow.days * DAY))); fc.appendChild(n3);
    fc.appendChild(el('div', 'lbl', Lx.trkReadyLbl));
    fc.appendChild(el('div', 'sub', Lx.trkSlowest.charAt(0).toUpperCase() + Lx.trkSlowest.slice(1) + ': ' + trackName(slow.tr) + ' (' + Lx.trkLeft + ' ' + slow.rest + ' ' + trackUnit(slow.tr) + ', ' + slow.goal + ' ' + Lx.perDay.replace(/^\S+\s/, '') + ')'));
  } else if (st.act && !st.rest){ fc.appendChild(el('div', 'num', '✓')); fc.appendChild(el('div', 'lbl', Lx.allDone2)); }
  else { fc.appendChild(el('div', 'num', '—')); fc.appendChild(el('div', 'lbl', Lx.trkReadyLbl)); fc.appendChild(el('div', 'sub', tsl.length ? Lx.trEtaUnknown : Lx.trkNoGoal)); }
  stats.appendChild(fc); main.appendChild(stats);
  /* tracks: a ring per kind of work, then the word trainer */
  if (tsl.length) main.appendChild(drawTracks(tsl));
  /* trainer */
  var tr = trainerSummary();
  if (tr && tr.total){
    var tc = el('button', 'train-card'); tc.type = 'button';
    var top = el('div', 'train-top'), left = el('div');
    left.appendChild(el('h3', null, Lx.trainerTitle));
    left.appendChild(el('div', 'meta', Lx.trainerDesc.replace('{w}', tr.words).replace('{v}', tr.verbs)));
    var big = el('div', 'big', String(tr.due)); big.appendChild(el('small', null, Lx.due)); top.appendChild(left); top.appendChild(big); tc.appendChild(top);
    tc.appendChild(bar([['d', tr.c.d / tr.total], ['c', tr.c.c / tr.total], ['l', tr.c.l / tr.total]]));
    var lg = el('div', 'legend-row');
    [['--done', Lx.learned, tr.c.d], ['--consolidating', Lx.consolidating, tr.c.c], ['--learning', Lx.learning, tr.c.l], ['--notstarted', Lx.notStarted, tr.c.n]].forEach(function(x){
      var sp = el('span'); var i = el('i'); i.style.background = 'var(' + x[0] + ')'; sp.appendChild(i); sp.appendChild(document.createTextNode(x[1])); sp.appendChild(el('b', null, String(x[2]))); lg.appendChild(sp); });
    tc.appendChild(lg);
    tc.appendChild(el('div', 'meta', Lx.cardsTotal + ': ' + tr.total + ' · ' + Lx.repsAll + ': ' + tr.reps + ' · ' + Lx.today + ': ' + tr.today));
    var tf = deckForecasts(decks()), titems = []; decks().forEach(function(dk){ titems = titems.concat(dk.items); });
    tc.appendChild(el('div', 'meta', Lx.trOverall + ' ' + Math.round(progressOf(titems) * 100) + '%' +
      ' · ' + Lx.trPaceGoal + ': ' + GOAL + ' ' + Lx.trNewPerDay + ' · ' + Lx.trWords + ': ' + etaText(tf.all)));
    tc.onclick = function(){ ui.tab = 'trainer'; lsSet('prep.tab', 'trainer'); render(); scrollTo(0, 0); };
    main.appendChild(tc);
  }

  /* prep order */
  var order = (D.order && D.order.length) ? D.order : OUTLINE.map(function(n){ return tt(n); });
  main.appendChild(el('div', 'kicker', Lx.orderTitle));
  var ol = el('ol', 'order'); order.forEach(function(t, i){ var li = el('li'); li.appendChild(el('b', null, String(i + 1))); li.appendChild(document.createTextNode(t)); ol.appendChild(li); }); main.appendChild(ol);
  /* labels */
  main.appendChild(el('div', 'kicker', Lx.tagsTitle));
  var lt = el('div', 'legend-tags');
  [['pri1', Lx.pri1, Lx.tagMain], ['pri2', Lx.pri2, Lx.tagImportant], ['pri3', Lx.pri3, Lx.tagOptional], ['origin vac', Lx.origin.vacancy, Lx.tagVac], ['origin mine', Lx.origin.resume, Lx.tagMine]].forEach(function(x){
    var sp = el('span'); sp.appendChild(el('span', 'badge ' + x[0], x[1])); sp.appendChild(document.createTextNode(x[2])); lt.appendChild(sp); });
  main.appendChild(lt);
  /* filters */
  var f = el('div', 'filters');
  var sInp = el('input'); sInp.type = 'search'; sInp.placeholder = Lx.searchPh; sInp.value = ui.q;
  sInp.oninput = function(){ ui.q = sInp.value.trim(); drawTree(); }; f.appendChild(sInp);
  function segs(key, opts){ var g = el('div', 'segs'); opts.forEach(function(o){ var b = el('button', null, o[1]); b.type = 'button'; b.setAttribute('aria-pressed', String(ui[key] === o[0]));
    b.onclick = function(){ ui[key] = o[0]; g.querySelectorAll('button').forEach(function(x){ x.setAttribute('aria-pressed', 'false'); }); b.setAttribute('aria-pressed', 'true'); drawTree(); }; g.appendChild(b); }); return g; }
  f.appendChild(segs('status', [['all', Lx.fAll], ['todo', Lx.fTodo], ['done', Lx.fDone], ['skip', Lx.fSkip]]));
  f.appendChild(segs('pri', [[0, Lx.fAny], [1, Lx.fMain], [2, Lx.fImportant], [3, Lx.fOptional]]));
  var vt = el('button', 'vac-toggle', Lx.fVac); vt.type = 'button'; vt.setAttribute('aria-pressed', String(ui.vac));
  vt.onclick = function(){ ui.vac = !ui.vac; vt.setAttribute('aria-pressed', String(ui.vac)); drawTree(); }; f.appendChild(vt);
  if (ui.track){ var atr = TRACKS.filter(function(x){ return x.id === ui.track; })[0];
    var tb = el('button', 'vac-toggle', '× ' + (atr ? trackName(atr) : ui.track)); tb.type = 'button'; tb.setAttribute('aria-pressed', 'true');
    tb.onclick = function(){ ui.track = null; rerenderKeepScroll(); }; f.appendChild(tb); }
  main.appendChild(f);
  var sl = el('div', 'save-line'); var sy = el('span', 'sync'); sy.id = 'sync'; sl.appendChild(el('span', 'dot')); sl.appendChild(sy); main.appendChild(sl);
  /* table of contents + tree */
  var grid = el('div', 'plan-grid');
  var toc = el('nav', 'toc'); toc.id = 'toc'; grid.appendChild(toc);
  var right = el('div');
  var th = el('div', 'tree-head');
  [['expand', true], ['collapse', false]].forEach(function(x){ var b = el('button', null, Lx[x[0]]); b.type = 'button';
    b.onclick = function(){ cardsOf().forEach(function(c){ if (x[1]) S.expanded[c.id] = true; else delete S.expanded[c.id]; }); save('S'); drawTree(); }; th.appendChild(b); });
  right.appendChild(th);
  var tree = el('div'); tree.id = 'tree'; right.appendChild(tree);
  grid.appendChild(right); main.appendChild(grid);
  drawTree();
}
/* Structure: the top level (a stage or a cross-cutting section) is a group caption;
   its children are thick section cards; topics directly inside a stage form one card named after the stage. */
function cardsOf(){
  var out = [];
  OUTLINE.forEach(function(top){
    var direct = (top.children || []).filter(isLeaf);
    if (direct.length || !(top.children || []).length) out.push({id: top.id, title: tt(top), node: top, items: direct, top: top});
    (top.children || []).filter(function(c){ return !isLeaf(c); }).forEach(function(c){ out.push({id: c.id, title: tt(c), node: c, items: c.children || [], top: top}); });
  });
  return out;
}
function cardProgress(card){ var ls = []; card.items.forEach(function(n){ leaves(n, ls); }); var a = ls.filter(function(x){ return !S.skip[x.id]; });
  return {done: a.filter(function(x){ return S.done[x.id]; }).length, total: a.length}; }
function drawTree(){
  var tree = $('tree'); if (!tree) return; tree.innerHTML = '';
  var toc = $('toc'); if (toc) toc.innerHTML = '';
  var cards = cardsOf(), f = filtering(), any = false, lastTop = null;
  cards.forEach(function(card){
    var items = card.items.filter(visible);
    if (f && !items.length) return;
    any = true;
    if (card.top !== lastTop){
      lastTop = card.top; var tp = progress(card.top);
      var gl = el('h2', 'group-label');
      if (card.top.kind === 'stage' && card.top.order) gl.appendChild(el('span', null, String(card.top.order).padStart(2, '0')));
      gl.appendChild(el('span', null, tt(card.top))); gl.appendChild(el('span', 'cnt', tp.done + ' / ' + tp.total)); tree.appendChild(gl);
      if (toc) toc.appendChild(el('h4', null, tt(card.top)));
    }
    var p = cardProgress(card), full = p.total && p.done === p.total;
    var open = f || !!S.expanded[card.id];
    var sec = el('section', 'pcard' + (open ? ' open' : '') + (full ? ' full' : '')); sec.id = 'card-' + card.id;
    var hd = el('button', 'phead'); hd.type = 'button'; hd.setAttribute('aria-expanded', String(open));
    var pt = el('span', 'pt', card.title); if (card.node !== card.top) badges(card.node, pt);
    hd.appendChild(pt); hd.appendChild(el('span', 'pc', p.done + ' / ' + p.total)); hd.appendChild(el('span', 'chev', '›'));
    sec.appendChild(hd);
    var pb = el('div', 'pbar'), pi = el('i'); pi.style.width = (p.total ? p.done / p.total * 100 : 0) + '%'; pb.appendChild(pi); sec.appendChild(pb);
    var body = el('div', 'pbody'); body.hidden = !open;
    var filled = false;
    function fill(){ if (filled) return; filled = true; items.forEach(function(n){ body.appendChild(drawNode(n, 1)); }); }
    if (open) fill();
    // Toggle in place: never rebuild the tree from inside the click (the clicked button would be removed
    // from the page during its own handler — WebKit then shows nothing).
    hd.addEventListener('click', function(){
      if (tooSoon(hd) || filtering()) return;   // while filtering every card is open anyway
      var o = !S.expanded[card.id];
      if (o){ S.expanded[card.id] = true; fill(); } else delete S.expanded[card.id];
      body.hidden = !o; sec.classList.toggle('open', o); hd.setAttribute('aria-expanded', String(o));
      save('S');
    });
    sec.appendChild(body); tree.appendChild(sec);
    if (toc){ var a = el('a', full ? 'full' : null); a.href = '#card-' + card.id; a.appendChild(document.createTextNode(card.title)); a.appendChild(el('span', null, p.done + '/' + p.total));
      a.onclick = function(e){ e.preventDefault(); if (!S.expanded[card.id]) hd.click(); sec.scrollIntoView({behavior: 'smooth', block: 'start'}); }; toc.appendChild(a); }
  });
  if (!any) tree.appendChild(el('div', 'empty', L().nothing));
}
function drawNode(n, depth){
  if (isLeaf(n) && n.kind !== 'stage' && n.kind !== 'cross') return drawLeaf(n);
  var wrap = el('section', 'node lvl' + depth);
  var row = el('div', 'row');
  var open = filtering() ? true : !S.collapsed[n.id];
  var caret = el('button', 'caret', '▸'); caret.type = 'button'; caret.setAttribute('aria-expanded', String(open)); caret.setAttribute('aria-label', tt(n));
  var t = el('div', 'ntitle');
  if (n.kind === 'stage' && n.order) t.appendChild(el('span', 'stage-no', String(n.order).padStart(2, '0')));
  t.appendChild(el('b', null, tt(n)));
  if (n.kind === 'cross') t.appendChild(el('span', 'badge cross-tag', '◇'));
  badges(n, t);
  var p = progress(n);
  var nb = el('div', 'nbar'); nb.appendChild(bar([['d', p.total ? p.done / p.total : 0]]));
  row.appendChild(caret); row.appendChild(t); row.appendChild(nb); row.appendChild(el('span', 'count', p.done + '/' + p.total));
  wrap.appendChild(row);
  var kids = el('div', 'children'); kids.hidden = !open;
  var filled = false;
  function fill(){ if (filled) return; filled = true; (n.children || []).filter(visible).forEach(function(c){ kids.appendChild(drawNode(c, depth + 1)); }); }
  if (open) fill();
  wrap.appendChild(kids);
  // The toggle is the whole group row: arrow, name, bar, counter, empty space. Done in place, no tree rebuild.
  function toggle(e){
    if ((e && tooSoon(row)) || filtering()) return;
    open = !open;
    if (open){ delete S.collapsed[n.id]; fill(); } else S.collapsed[n.id] = true;
    kids.hidden = !open; caret.setAttribute('aria-expanded', String(open)); row.setAttribute('aria-expanded', String(open)); wrap.classList.toggle('open', open);
    save('S');
  }
  row.classList.add('group-row');
  row.setAttribute('role', 'button'); row.tabIndex = 0; row.setAttribute('aria-expanded', String(open));
  row.addEventListener('click', function(e){ if (e.target.closest('input,a,.leaf-acts')) return; toggle(e); });
  row.addEventListener('keydown', function(e){ if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); toggle(); } });
  caret.tabIndex = -1;
  return wrap;
}
function drawLeaf(n){
  var li = el('div', 'node leaf' + (S.done[n.id] ? ' done' : '') + (S.skip[n.id] ? ' skipped' : ''));
  var row = el('div', 'row');
  var cb = el('input'); cb.type = 'checkbox'; cb.checked = !!S.done[n.id]; cb.disabled = !!S.skip[n.id]; cb.setAttribute('aria-label', tt(n));
  cb.onchange = function(){ if (cb.checked){ S.done[n.id] = NOW(); if (!S.startedAt && Object.keys(S.done).length === 1) S.startedAt = NOW(); } else delete S.done[n.id]; save('S'); rerenderKeepScroll(); };
  var t = el('div', 'ntitle'); t.appendChild(el('b', null, tt(n))); badges(n, t);
  var ask = ui.lang !== P && n['summary_' + ui.lang] ? n['summary_' + ui.lang] : n.summary; if (ask) t.appendChild(el('span', 'ask', ask));
  var acts = el('div', 'leaf-acts');
  function actBtn(label, icon){ var b = el('button'); b.type = 'button'; b.setAttribute('aria-label', label); b.title = label;
    b.appendChild(el('span', 'full', label)); b.appendChild(el('span', 'short', icon)); return b; }
  var mb = actBtn(L().material, '▤');
  var sb = actBtn(S.skip[n.id] ? L().unskip : L().skip, S.skip[n.id] ? '↺' : '⊘');
  sb.onclick = function(e){ e.stopPropagation(); if (S.skip[n.id]) delete S.skip[n.id]; else { S.skip[n.id] = true; delete S.done[n.id]; } save('S'); rerenderKeepScroll(); };
  acts.appendChild(mb); acts.appendChild(sb);
  row.appendChild(cb); row.appendChild(t); row.appendChild(acts); li.appendChild(row);
  var mat = null;
  function openMat(){
    if (mat){ mat.remove(); mat = null; return; }
    mat = el('div', 'material');
    var html = CONTENT[ui.lang] && CONTENT[ui.lang][n.id], other = ui.lang === P ? (LANGS[1] || P) : P;
    if (!html && CONTENT[other] && CONTENT[other][n.id]){ mat.appendChild(el('div', 'fallback', L().noTranslation)); html = CONTENT[other][n.id]; }
    var body = el('div'); body.innerHTML = html || '<p class="empty">' + L().noMaterial + '</p>';
    body.querySelectorAll('mark.vfy').forEach(function(m){ m.title = L().vfMark; m.setAttribute('aria-label', L().vfMark); });
    var vf = (D.verified || {})[n.id];
    if (html && vf){   // fact-check badge: checked against sources, with date and count, or a warning
      var cls = vf.s === 'ok' ? 'ok' : (vf.s === 'none' ? 'none' : 'warn');
      var txt = vf.s === 'ok' ? '✓ ' + L().vfOk : vf.s === 'open' ? '⚠ ' + L().vfOpen + (vf.o ? ' (' + vf.o + ')' : '') : vf.s === 'stale' ? '⚠ ' + L().vfStale : '○ ' + L().vfNone;
      if (vf.d && vf.s !== 'none') txt += ' · ' + fmtDate(vf.d) + (vf.n ? ' · ' + vf.n + ' ' + L().vfSources : '');
      var badge = el('span', 'vf-badge ' + cls, txt);
    }
    if (html){
      // copy the whole lesson — title, the "what they'll ask" line and the text — to paste into a new chat
      var bar = el('div', 'mat-tools'); bar.appendChild(badge || el('span')); var cp = el('button', 'chip', '⧉ ' + L().copy); cp.type = 'button';
      cp.onclick = function(e){
        e.stopPropagation();
        var ask = ui.lang !== P && n['summary_' + ui.lang] ? n['summary_' + ui.lang] : n.summary;
        copyText('# ' + tt(n) + (ask ? '\n\n' + ask : '') + '\n\n' + toText(body), cp);
      };
      bar.appendChild(cp); mat.appendChild(bar);
    }
    mat.appendChild(body);
    if (html && other !== ui.lang && CONTENT[other] && CONTENT[other][n.id] && CONTENT[ui.lang][n.id]){
      var ob = el('button', 'chip', L().otherLang); ob.type = 'button'; var shown = null;
      ob.onclick = function(){ if (shown){ shown.remove(); shown = null; return; } shown = el('div', 'other'); shown.innerHTML = CONTENT[other][n.id]; mat.appendChild(shown); };
      mat.appendChild(ob);
    }
    li.appendChild(mat);
  }
  mb.onclick = function(e){ e.stopPropagation(); openMat(); };
  t.style.cursor = 'pointer';
  t.addEventListener('click', function(){ if (tooSoon(t)) return; openMat(); });
  return li;
}

/* word popup card for [[term]] */
var WORD_BY_EN = {}; if (DECK) (DECK.words || []).forEach(function(w){ WORD_BY_EN[w.en.toLowerCase()] = w; });
document.addEventListener('click', function(e){
  var a = e.target.closest && e.target.closest('a.term'); var pop = $('pop');
  if (!a){ if (!pop.contains(e.target)) pop.hidden = true; return; }
  e.preventDefault();
  var w = WORD_BY_EN[(a.dataset.term || '').toLowerCase()]; if (!w) return;
  pop.innerHTML = '';
  pop.appendChild(el('h4', null, w.en)); if (w.forms) pop.appendChild(el('div', 'hint', w.forms));
  pop.appendChild(el('div', null, w.ru)); if (w.note) pop.appendChild(el('div', 'note', w.note));
  (w.ex || []).slice(0, 2).forEach(function(x){ var d = el('div', 'ex', x.en); d.appendChild(el('span', null, x.ru)); pop.appendChild(d); });
  var r = a.getBoundingClientRect(); pop.hidden = false;
  pop.style.left = Math.max(8, Math.min(r.left, innerWidth - pop.offsetWidth - 8)) + 'px';
  pop.style.top = (r.bottom + 6 + pop.offsetHeight > innerHeight ? r.top - pop.offsetHeight - 6 : r.bottom + 6) + 'px';
});

/* ---------- Vocabulary tab (the "I know" check) ---------- */
var VB = 50;
function vkey(i){ return 'b' + (i + 1); }
/* Quick frequency-based check: band = band from rank_words.py (by zipf).
   10 words per band, spread evenly by rank; knows >= 9 → the whole band is known.
   Stored in V as batch 'q<band>': {known, unknown, band, pass}. Redo: {reset:true}. */
var QN = 10, QPASS = 0.9;
function wBand(w){ if (w.band) return w.band; if (w.zipf == null) return 0; var z = w.zipf; return z >= 5 ? 1 : z >= 4 ? 2 : z >= 3 ? 3 : 4; }
function qDone(b){ var r = V['q' + b]; return !!(r && !r.reset); }
function qSample(list){ if (list.length <= QN) return list.slice(); var out = []; for (var i = 0; i < QN; i++) out.push(list[Math.floor((i + 0.5) * list.length / QN)]); return out; }
function quickBands(words){
  var by = {}; words.forEach(function(w){ var b = wBand(w); if (b){ (by[b] = by[b] || []).push(w); } });
  return Object.keys(by).map(Number).sort().filter(function(b){ return by[b].length >= QN * 2; }).map(function(b){ return {b: b, words: by[b]}; });
}
function renderQuick(main, bands){
  var sec = el('div', 'card qcheck'); sec.appendChild(el('h3', null, L().qTitle)); sec.appendChild(el('p', 'meta', L().qIntro));
  var open = bands.filter(function(x){ return !qDone(x.b); })[0];
  bands.forEach(function(x){
    var r = V['q' + x.b], row = el('div', 'qrow');
    row.appendChild(el('b', null, L().qBand + ' ' + x.b + ' · ' + L()['band' + x.b]));
    row.appendChild(el('span', 'meta', x.words.length + ' ' + L().qWords));
    if (qDone(x.b)){
      row.appendChild(el('span', r.pass ? 'tag ok' : 'tag', r.pass ? L().qPass : L().qFail));
      var redo = el('button', 'linkbtn', L().qRedo); redo.type = 'button';
      redo.onclick = async function(){ await saveVocab('q' + x.b, {reset: true, known: [], unknown: [], at: NOW()}); render(); };
      row.appendChild(redo);
    }
    sec.appendChild(row);
  });
  if (open){
    var marks = {}, box = el('div', 'qbox');
    qSample(open.words).forEach(function(w){
      var r = el('label', 'vrow'); var c = el('input'); c.type = 'checkbox'; marks[w.id] = c;
      r.appendChild(c); r.appendChild(el('span', 'en', w.en)); box.appendChild(r);   // no translation: this is a check, not a hint
    });
    sec.appendChild(el('p', 'meta', L().qBand + ' ' + open.b + ' · ' + L()['band' + open.b] + ' — ' + L().qHint));
    sec.appendChild(box);
    var acts = el('div', 'acts'), go = el('button', 'btn primary', L().qCheck + ' ' + open.b); go.type = 'button';
    go.onclick = async function(){
      var ids = Object.keys(marks), kn = ids.filter(function(id){ return marks[id].checked; });
      var pass = kn.length >= Math.ceil(ids.length * QPASS);
      var known = pass ? open.words.map(function(w){ return w.id; }).filter(function(id){ return !marks[id] || marks[id].checked; }) : kn;
      var unknown = ids.filter(function(id){ return !marks[id].checked; });
      await saveVocab('q' + open.b, {band: open.b, pass: pass, known: known, unknown: unknown, at: NOW()});
      render();
    };
    var skip = el('button', 'btn', L().qSkip); skip.type = 'button';
    skip.onclick = async function(){ for (var i = 0; i < bands.length; i++) if (!qDone(bands[i].b)) await saveVocab('q' + bands[i].b, {band: bands[i].b, pass: false, skipped: true, known: [], unknown: [], at: NOW()}); render(); };
    acts.appendChild(go); acts.appendChild(skip); sec.appendChild(acts);
  }
  main.appendChild(sec);
  return !!open;
}
function renderVocab(main){
  var all = (DECK.words || []).slice().sort(function(a, b){ return a.rank - b.rank; });
  var bands = quickBands(all);
  if (bands.some(function(x){ return !qDone(x.b); })){ main.appendChild(el('p', 'meta', L().vocabIntro)); renderQuick(main, bands); return; }   // quick check first, then batches
  var decided = {}; Object.keys(V).forEach(function(k){ if (k.charAt(0) === 'q' && !V[k].reset){ (V[k].known || []).concat(V[k].unknown || []).forEach(function(id){ decided[id] = true; }); } });
  var words = all.filter(function(w){ return !decided[w.id]; });
  var batches = []; for (var i = 0; i < words.length; i += VB) batches.push(words.slice(i, i + VB));
  var known = knownSet(), seen = {}; Object.keys(V).forEach(function(k){ if (V[k].reset) return; (V[k].known || []).concat(V[k].unknown || []).forEach(function(id){ seen[id] = true; }); });
  var checkedN = Object.keys(seen).length;
  var cur = batches.findIndex(function(_, i){ return !V[vkey(i)]; }); if (cur < 0) cur = 0;
  if (ui.vb != null) cur = ui.vb;
  main.appendChild(el('p', 'meta', L().vocabIntro));
  var kn = Object.keys(known).length, N = all.length;
  if (bands.length) renderQuick(main, bands);
  var line = el('div', 'progress-line'); line.appendChild(el('span', null, L().checked + ' ' + checkedN + ' / ' + N));
  line.appendChild(el('span', null, L().know + ' ' + kn + ' · ' + L().learn + ' ' + (checkedN - kn))); main.appendChild(line);
  main.appendChild(bar([['d', N ? kn / N : 0], ['l', N ? (checkedN - kn) / N : 0]]));
  var nav = el('div', 'toolbar'); nav.style.marginTop = '14px';
  batches.forEach(function(_, i){ var c = el('button', 'chip', L().batch + ' ' + (i + 1) + (V[vkey(i)] ? ' ✓' : '')); c.type = 'button'; c.setAttribute('aria-pressed', String(i === cur)); c.onclick = function(){ ui.vb = i; render(); }; nav.appendChild(c); });
  main.appendChild(nav);
  var box = el('div', 'card'), marks = {};
  (batches[cur] || []).forEach(function(w){
    var r = el('label', 'vrow'); var c = el('input'); c.type = 'checkbox'; c.checked = !!known[w.id]; marks[w.id] = c;
    r.appendChild(c); r.appendChild(el('span', 'en', w.en)); r.appendChild(el('span', 'ru', w.ru)); box.appendChild(r);
  });
  main.appendChild(box);
  var acts = el('div', 'acts'); var sv = el('button', 'btn primary', L().saveBatch); sv.type = 'button';
  sv.onclick = async function(){
    var rec = {known: [], unknown: [], at: NOW()};
    Object.keys(marks).forEach(function(id){ (marks[id].checked ? rec.known : rec.unknown).push(id); });
    ui.vb = Math.min(cur + 1, batches.length - 1);
    await saveVocab(vkey(cur), rec);
    render(); scrollTo(0, 0);
  };
  acts.appendChild(sv); main.appendChild(acts);
}
function knownSet(){ var k = {}; Object.keys(V).forEach(function(b){ if (V[b].reset) return; (V[b].known || []).forEach(function(id){ k[id] = true; }); }); return k; }

/* ---------- Trainer tab (Leitner) ----------
   As in the work portal: decks by importance — "Words 1–50", "51–100"…
   Numbering follows the list of what the person is learning: known words (marked on
   the "Vocabulary" tab) are removed, the rest go by rank and are cut into 50s.
   Progress is tied to the card id, so re-slicing does not lose it.
   Within a deck cards go from more to less important; within a session they are shuffled. */
var play = null, TRB = 50;
function ruPlural(n, one, few, many){ var a = n % 10, b = n % 100; return a === 1 && b !== 11 ? one : a >= 2 && a <= 4 && (b < 12 || b > 14) ? few : many; }
function nCards(n){ return n + ' ' + (ui.lang === 'ru' ? ruPlural(n, 'карточка', 'карточки', 'карточек') : n === 1 && ui.lang === 'en' ? 'card' : L().cards); }
function wordDecks(){
  seedFacets();
  var known = knownSet();
  var learn = (DECK.words || []).filter(function(w){ return !known[w.id]; }).sort(function(a, b){ return a.rank - b.rank; });
  var n = Math.ceil(learn.length / TRB), out = [];
  for (var i = 0; i < n; i++){
    var items = learn.slice(i * TRB, (i + 1) * TRB);
    out.push({key: 'w' + (i + 1), grp: L().trByImportance, kind: 'word', items: items,
              title: L().trWords + ' ' + (i * TRB + 1) + '–' + (i * TRB + items.length),
              desc: L().group + ' ' + (i + 1) + ' ' + L().of + ' ' + n});
  }
  return out;
}
function decks(){
  var out = wordDecks();
  if ((DECK.verbs || []).length) out.push({key: 'verbs', grp: L().trOther, kind: 'verb', items: DECK.verbs, title: L().verbs, desc: L().verbsDesc});
  if ((DECK.phrases || []).length) out.push({key: 'phrases', grp: L().trOther, kind: 'phrase', items: DECK.phrases, title: L().phrases, desc: L().phrasesDesc});
  if ((DECK.answers || []).length) out.push({key: 'answers', grp: L().trOther, kind: 'answer', items: DECK.answers, title: L().answers, desc: L().answersDesc});
  return out;
}
/* A word is asked from four sides, each with its own Leitner box (key "id|side"):
   pick-en  given the word in the explanation language → pick the English one of 6;
   pick-ru  given the English word → pick the translation of 6;
   say-en   given the word in the explanation language → recall the English, self-assess;
   say-ru   given the English word → recall the translation, self-assess.
   In a session the sides of one word are mixed with other words and never back to back;
   picking comes before recalling. A word is "learned" when all four sides are learned. */
var FACETS = ['pick-en', 'pick-ru', 'say-en', 'say-ru'];
function isWord(it){ return /^w:/.test(it.id || ''); }
function fid(it, f){ return it.id + '|' + f; }
function facetDue(it, f){ var s = T[fid(it, f)]; return !s || !s.d || s.d <= NOW(); }
function seedFacets(){
  // progress from older versions (one box per word) is carried over to all four sides
  (DECK && DECK.words || []).forEach(function(w){ var old = T[w.id];
    if (old && !FACETS.some(function(f){ return T[fid(w, f)]; })) FACETS.forEach(function(f){ T[fid(w, f)] = {b: old.b || 0, d: old.d || 0, s: !!old.s}; }); });
}
function cardState(it){
  if (!isWord(it)){ var st = T[it.id]; return {b: st && st.s ? st.b : 0, s: !!(st && st.s)}; }
  var m = 4, seen = false;
  FACETS.forEach(function(f){ var st = T[fid(it, f)]; if (st && st.s) seen = true; m = Math.min(m, st && st.s ? st.b : 0); });
  return {b: m, s: seen};
}
function isDue(it){ if (isWord(it)) return FACETS.some(function(f){ return facetDue(it, f); }); var s = T[it.id]; return !s || !s.d || s.d <= NOW(); }
function deckStats(items){
  var s = {learned: 0, firm: 0, learning: 0, fresh: 0, total: 0, due: 0};
  items.forEach(function(it){ var st = cardState(it); s.total++; if (isDue(it)) s.due++;
    if (!st.s){ s.fresh++; return; } if (st.b >= 4) s.learned++; else if (st.b >= 2) s.firm++; else s.learning++; });
  return s;
}
function mix(items){ var s = deckStats(items), n = s.total || 1; return [['d', s.learned / n], ['c', s.firm / n], ['l', s.learning / n]]; }
function trLegend(s){
  var lg = el('div', 'tr-legend');
  [['--done', L().learned, s.learned], ['--consolidating', L().consolidating, s.firm], ['--learning', L().learning, s.learning], ['--notstarted', L().notStarted, s.fresh]].forEach(function(x){
    var w = el('span'), i = el('em'); i.style.background = 'var(' + x[0] + ')'; w.appendChild(i); w.appendChild(document.createTextNode(x[1] + ' ')); w.appendChild(el('b', null, x[2])); lg.appendChild(w);
  });
  return lg;
}
function todayReps(){ var t0 = new Date(), n = 0; t0.setHours(0, 0, 0, 0); Object.keys(T).forEach(function(id){ var st = T[id]; if (st && st.l >= t0.getTime()) n += st.t || 0; }); return n; }
/* ---------- daily goal: new words a day ----------
   A word counts on the day it was first shown (earliest side). Ring for today, seven small rings
   for the week, a streak of days with the goal met, a slider to change the goal. */
function today0(){ var d = new Date(); d.setHours(0, 0, 0, 0); return d.getTime(); }
function newWordsByDay(){
  var m = {};
  (DECK && DECK.words || []).forEach(function(w){ var f = firstSeen(w); if (f == null) return; var d = new Date(f); d.setHours(0, 0, 0, 0); m[d.getTime()] = (m[d.getTime()] || 0) + 1; });
  return m;
}
function newWordsOn(day){ return newWordsByDay()[day] || 0; }
function ring(size, frac, label, sub, cls){
  var NS = 'http://www.w3.org/2000/svg', sw = Math.max(4, Math.round(size / 9)), r = (size - sw) / 2, c = 2 * Math.PI * r;
  var svg = document.createElementNS(NS, 'svg'); svg.setAttribute('width', size); svg.setAttribute('height', size); svg.setAttribute('viewBox', '0 0 ' + size + ' ' + size);
  svg.setAttribute('class', 'ring' + (frac >= 1 ? ' full' : '') + (cls ? ' ' + cls : '')); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', label + (sub ? ' ' + sub : ''));
  function circ(k){ var e = document.createElementNS(NS, 'circle'); e.setAttribute('cx', size / 2); e.setAttribute('cy', size / 2); e.setAttribute('r', r); e.setAttribute('fill', 'none'); e.setAttribute('stroke-width', sw); e.setAttribute('class', k); return e; }
  svg.appendChild(circ('ring-bg'));
  var fg = circ('ring-fg'); fg.setAttribute('stroke-linecap', 'round'); fg.setAttribute('stroke-dasharray', c);
  fg.setAttribute('stroke-dashoffset', c * (1 - Math.max(0, Math.min(1, frac)))); fg.setAttribute('transform', 'rotate(-90 ' + size / 2 + ' ' + size / 2 + ')');
  if (frac > 0) svg.appendChild(fg);
  var tx = document.createElementNS(NS, 'text'); tx.setAttribute('x', '50%'); tx.setAttribute('y', '50%'); tx.setAttribute('text-anchor', 'middle'); tx.setAttribute('dominant-baseline', 'central'); tx.setAttribute('class', 'ring-t'); tx.textContent = label; svg.appendChild(tx);
  return svg;
}
function goalStreak(by){
  var n = 0, d = today0();
  if ((by[d] || 0) < GOAL) d -= DAY;   // today not finished yet does not break the streak
  while ((by[d] || 0) >= GOAL){ n++; d -= DAY; }
  return n;
}
function drawGoal(compact){
  var by = newWordsByDay(), t0 = today0(), done = by[t0] || 0;
  var box = el('div', 'goal' + (compact ? ' compact' : ''));
  var big = el('div', 'goal-ring');
  big.appendChild(ring(compact ? 64 : 132, done / GOAL, done + '/' + GOAL, L().goalToday));
  var cap = el('div', 'goal-cap');
  cap.appendChild(el('b', null, done >= GOAL ? '✓ ' + L().goalDone : L().goalToday + ': ' + done + ' / ' + GOAL));
  if (done < GOAL) cap.appendChild(el('span', 'meta', L().goalLeft + ' ' + (GOAL - done)));
  var stk = goalStreak(by); if (stk) cap.appendChild(el('span', 'goal-streak', '🔥 ' + L().goalStreak + ': ' + stk + ' ' + plural(stk, L().day1, L().day2, L().day5)));
  big.appendChild(cap); box.appendChild(big);
  if (compact) return box;
  var wk = el('div', 'goal-week'); wk.appendChild(el('div', 'goal-wk-h', L().goalWeek));
  var row = el('div', 'goal-days');
  for (var i = 6; i >= 0; i--){
    var day = t0 - i * DAY, n = by[day] || 0, cell = el('div', 'goal-day' + (i === 0 ? ' today' : ''));
    cell.appendChild(ring(40, n / GOAL, String(n), ''));
    cell.appendChild(el('span', null, new Date(day).toLocaleDateString(ui.lang === 'en' ? 'en-GB' : ui.lang, {weekday: 'short'})));
    row.appendChild(cell);
  }
  wk.appendChild(row); box.appendChild(wk);
  // goal slider
  var adj = el('label', 'goal-adj'), val = el('b', null, GOAL + ' ' + L().goalWordsDay);
  adj.appendChild(el('span', null, L().goalLabel + ': ')); adj.appendChild(val);
  var rg = el('input'); rg.type = 'range'; rg.min = 5; rg.max = 50; rg.step = 5; rg.value = Math.min(50, Math.max(5, GOAL)); rg.setAttribute('aria-label', L().goalLabel);
  rg.oninput = function(){ val.textContent = rg.value + ' ' + L().goalWordsDay; };
  rg.onchange = function(){ GOAL = +rg.value; lsSet('prep.goal', GOAL); save('T'); rerenderKeepScroll(); };
  adj.appendChild(rg); box.appendChild(adj);
  return box;
}

/* ---------- trainer forecast ----------
   Pace = new cards started per day over the last 14 days. Word decks are started in order (the
   "by importance" round goes from the top), so deck k starts when all fresh words before it are started.
   A started side still needs its remaining intervals (STEPS[b+1..3]) to reach box 4; a fresh one 1+3+7 days.
   Optimistic: assumes no mistakes. */
var TAIL = STEPS[1] + STEPS[2] + STEPS[3];
function cardKeys(it){ return isWord(it) ? FACETS.map(function(f){ return fid(it, f); }) : [it.id]; }
function firstSeen(it){
  var m = null; cardKeys(it).forEach(function(k){ var s = T[k]; if (s && s.s){ var v = toTs(s.f) || toTs(s.l); if (v && (m == null || v < m)) m = v; } }); return m;
}
function itemLeft(it){   // days until this card is learned, if it has been started
  var mx = 0;
  cardKeys(it).forEach(function(k){ var s = T[k], left;
    if (!s || !s.s) left = TAIL;
    else if (s.b >= 4) left = 0;
    else { left = Math.max(0, ((s.d || NOW()) - NOW()) / DAY); for (var b = s.b + 1; b <= 3; b++) left += STEPS[b]; }
    if (left > mx) mx = left; });
  return mx;
}
function itemPct(it){ var ks = cardKeys(it), sum = 0; ks.forEach(function(k){ var s = T[k]; if (s && s.s) sum += Math.min(s.b || 0, 4); }); return sum / (4 * ks.length); }
function progressOf(items){ if (!items.length) return 0; var s = 0; items.forEach(function(it){ s += itemPct(it); }); return s / items.length; }
function paceOf(items){
  var starts = items.map(firstSeen).filter(function(v){ return v != null; });
  if (!starts.length) return 0;
  var from = Math.max(Math.min.apply(null, starts), NOW() - 14 * DAY);
  var n = starts.filter(function(v){ return v >= from; }).length, days = Math.max(1, Math.ceil((NOW() - from) / DAY));
  return n / days;
}
function etaOf(items, pace, freshBefore){
  var fresh = 0, left = 0;
  items.forEach(function(it){ if (!cardState(it).s) fresh++; else left = Math.max(left, itemLeft(it)); });
  if (fresh && !(pace > 0)) return null;
  var start = fresh ? (freshBefore + fresh) / pace : 0;
  return {fresh: fresh, start: Math.ceil(start), learn: Math.ceil(Math.max(left, fresh ? start + TAIL : 0))};
}
function etaText(e){
  if (!e) return L().trEtaUnknown;
  if (!e.learn) return L().trAllLearned;
  var parts = [];
  if (e.fresh) parts.push(L().trStartIn + ' ' + e.start + ' ' + plural(e.start, L().day1, L().day2, L().day5));
  parts.push(L().trLearnBy + ' ' + fmtDay(NOW() + e.learn * DAY));
  return parts.join(' · ');
}
/* every deck with its forecast; word decks share one pace and go in order */
function deckForecasts(all){
  var words = []; all.forEach(function(dk){ if (dk.kind === 'word') words = words.concat(dk.items); });
  var actual = paceOf(words), wp = GOAL > 0 ? GOAL : actual, before = 0, out = {};   // words: by the daily goal
  all.forEach(function(dk){
    if (dk.kind === 'word'){ var e = etaOf(dk.items, wp, before); out[dk.key] = e; if (e) before += e.fresh; }
    else out[dk.key] = etaOf(dk.items, paceOf(dk.items), 0);
  });
  return {pace: wp, actual: actual, decks: out, words: words, all: etaOf(words, wp, 0)};
}
function renderTrainer(main){
  if (play) return renderPlay(main);
  var all = decks(), tot = {learned: 0, firm: 0, learning: 0, fresh: 0};
  all.forEach(function(dk){ var s = deckStats(dk.items); Object.keys(tot).forEach(function(k){ tot[k] += s[k]; }); });
  main.appendChild(el('h2', 'tr-h', L().trTitle));
  main.appendChild(el('p', 'meta tr-intro', L().trIntro));
  if ((DECK.words || []).length) main.appendChild(drawGoal(false));
  var stats = el('div', 'tr-stats');
  [[tot.learned, L().trLearned], [tot.firm + tot.learning, L().trInProgress], [tot.fresh, L().trToStart], [todayReps(), L().trToday]].forEach(function(x){
    var c = el('div', 'tr-stat'); c.appendChild(el('b', null, x[0])); c.appendChild(el('span', null, x[1])); stats.appendChild(c);
  });
  main.appendChild(stats);
  var fcs = deckForecasts(all), everything = []; all.forEach(function(dk){ everything = everything.concat(dk.items); });
  var ov = el('div', 'tr-overall');
  ov.appendChild(el('div', 'tr-ov-h', L().trOverall + ' ' + Math.round(progressOf(everything) * 100) + '%'));
  var ob = el('div', 'bar tr-ov-bar'), oi = el('i', 'd'); oi.style.width = Math.round(progressOf(everything) * 100) + '%'; ob.appendChild(oi); ov.appendChild(ob);
  var lines = [];
  lines.push(L().trPaceGoal + ': ' + GOAL + ' ' + L().trNewPerDay + (fcs.actual > 0 ? ' (' + L().trPaceActual + ' ' + (Math.round(fcs.actual * 10) / 10) + ')' : ''));
  lines.push(L().trWords + ': ' + etaText(fcs.all));
  ov.appendChild(el('div', 'meta', lines.join(' · ')));
  ov.appendChild(el('div', 'tr-note-s', L().trEtaNote));
  main.appendChild(ov);
  // Main button: time is limited, so one session "by importance":
  // first what is due for review, from more to less important, then new words from the top of the list.
  var sm = smartDeck(), ss = deckStats(sm.items);
  if (sm.items.length){
    var inRound = smartQueue(sm.items, ui.size).length;
    if (!inRound){ sm.extra = true; }   // goal met and no reviews due: offer an explicit extra round
    var big = el('button', 'tr-smart' + (sm.extra ? ' extra' : '')); big.type = 'button';
    var r = el('div', 'row'), l = el('div'); l.appendChild(el('h3', null, sm.extra ? L().goalDone + ' · ' + L().goalExtra : L().trSmart)); l.appendChild(el('p', null, L().trSmartDesc));
    var go = el('div', 'go'); go.appendChild(el('b', null, sm.extra ? Math.min(ui.size, smartQueue(sm.items, ui.size, true).length) : inRound)); go.appendChild(document.createTextNode(L().trSmartGo));
    r.appendChild(l); r.appendChild(go); big.appendChild(r);
    big.onclick = function(){ startRound(sm); };
    main.appendChild(big);
  }
  var list = el('div', 'tr-decks'), grp = null;
  all.forEach(function(dk){
    if (dk.grp !== grp){ grp = dk.grp; list.appendChild(el('div', 'tr-grp', grp)); }
    var s = deckStats(dk.items), b = el('button', 'tr-deck' + (s.learned === s.total ? ' done' : '')); b.type = 'button';
    var row = el('div', 'row'), left = el('div');
    left.appendChild(el('h3', null, dk.title)); left.appendChild(el('p', null, dk.desc + ' · ' + nCards(s.total)));
    var go = el('div', 'go' + (s.due ? '' : ' zero')); go.appendChild(el('b', null, s.due)); go.appendChild(document.createTextNode(s.due ? L().due : L().allDone));
    row.appendChild(left); row.appendChild(go); b.appendChild(row);
    b.appendChild(bar(mix(dk.items))); b.appendChild(trLegend(s));
    b.appendChild(el('div', 'tr-eta', L().trProgress + ' ' + Math.round(progressOf(dk.items) * 100) + '% · ' + etaText(fcs.decks[dk.key])));
    b.onclick = function(){ startRound(dk); };
    list.appendChild(b);
  });
  main.appendChild(list);
  var opts = el('div', 'tr-opts');
  var lab = el('label', null, L().size + ' '), sel = el('select');
  [10, 20, 30, 50].forEach(function(v){ var o = el('option', null, String(v)); o.value = v; o.selected = v === ui.size; sel.appendChild(o); });
  sel.onchange = function(){ ui.size = +sel.value; lsSet('prep.size', ui.size); }; lab.appendChild(sel); opts.appendChild(lab);
  // no direction choice: a word is asked from all four sides
  var rs = el('button', 'linkbtn', L().trReset); rs.type = 'button'; var armed = false;
  rs.onclick = function(){
    if (!armed){ armed = true; rs.textContent = L().trResetSure; setTimeout(function(){ armed = false; rs.textContent = L().trReset; }, 4000); return; }
    T = {}; save('T'); flush(); render();
  };
  opts.appendChild(rs);
  main.appendChild(opts);
}
function smartDeck(){
  var items = []; wordDecks().forEach(function(dk){ items = items.concat(dk.items); });
  return {key: 'smart', kind: 'word', items: items, title: L().trSmart, smart: true};
}
function facetQueue(words, n){
  // words in order of importance → sides that are due
  var per = [], total = 0;
  for (var i = 0; i < words.length && total < n; i++){
    var fs = FACETS.filter(function(f){ return facetDue(words[i], f); });
    if (fs.length){ per.push({w: words[i], fs: fs}); total += fs.length; }
  }
  // random, but: a word's sides go in order (pick → recall), the same word never twice in a row,
  // and words with more sides left are picked more often, so no single-word "tail" is left at the end
  var q = [], last = null;
  while (per.some(function(x){ return x.fs.length; })){
    var cand = per.filter(function(x){ return x.fs.length && x.w !== last; });
    if (!cand.length) cand = per.filter(function(x){ return x.fs.length; });
    var pool = []; cand.forEach(function(x){ for (var r = 0; r < x.fs.length; r++) pool.push(x); });
    var pick = pool[Math.floor(Math.random() * pool.length)];
    q.push({it: pick.w, f: pick.fs.shift()}); last = pick.w;
  }
  return q;
}
function smartQueue(items, n, extra){
  // 1) due for review (already seen), by importance; 2) new, by importance
  var byRank = function(a, b){ return (a.rank || 0) - (b.rank || 0); };
  var rev = items.filter(function(it){ return cardState(it).s && isDue(it); }).sort(byRank);
  var fresh = items.filter(function(it){ return !cardState(it).s; }).sort(byRank);
  // the daily goal caps new words; an explicit "extra round" lifts the cap
  if (!extra) fresh = fresh.slice(0, Math.max(0, GOAL - newWordsOn(today0())));
  return facetQueue(rev.concat(fresh), n);
}
function startRound(dk){
  var q;
  if (dk.kind === 'word'){
    q = dk.smart ? smartQueue(dk.items, ui.size, dk.extra)
                 : facetQueue(dk.items.filter(isDue).sort(function(a, b){ return (a.rank || 0) - (b.rank || 0); }), ui.size);
    if (!q.length){ var any = shuffle(dk.items.slice()).slice(0, 3); q = []; FACETS.forEach(function(f){ any.forEach(function(w){ q.push({it: w, f: f}); }); }); }
  } else {
    var list = dk.items.filter(isDue).sort(function(a, b){ return (a.rank || 0) - (b.rank || 0); }).slice(0, ui.size);
    if (!list.length) list = shuffle(dk.items.slice()).slice(0, 10);
    q = shuffle(list).map(function(it){ return {it: it, f: null}; });
  }
  play = {deck: dk, queue: q, idx: 0, right: 0, wrong: 0, shown: false, picked: null};
  render(); scrollTo(0, 0);
}
function prompt(it, kind, f){
  if (kind === 'verb') return {lbl: L().qForms, q: it.inf, hint: it.ru, a: it.inf + ' — ' + it.past + ' — ' + it.pp, forms: true};
  if (kind === 'answer') return {lbl: L().qSay, q: it.prompt_ru, a: it.en, small: true};
  if (kind === 'phrase') return {lbl: L().qSay, q: it.ru, a: it.en, small: true};
  var enA = it.en + (it.forms ? ' (' + it.forms + ')' : '');
  if (f === 'pick-en') return {lbl: L().qPickEn, q: it.ru, a: enA, pick: 'en'};
  if (f === 'pick-ru') return {lbl: L().qPickRu, q: it.en, hint: it.forms || '', a: it.ru, pick: 'ru'};
  if (f === 'say-en') return {lbl: L().qSay, q: it.ru, a: enA};
  return {lbl: L().qMeaning, q: it.en, hint: it.forms || '', a: it.ru};
}
function entryId(e){ return e.f ? fid(e.it, e.f) : e.it.id; }
function grade(ok){
  var e = play.queue[play.idx], key = entryId(e), s = T[key] || {b: 0, d: 0, s: false};
  if (!s.f) s.f = NOW();   // first time this card was shown — for the pace
  s.s = true; s.n = (s.n || 0) + 1;
  var t0 = new Date(); t0.setHours(0, 0, 0, 0); s.t = (s.l && s.l >= t0.getTime() ? (s.t || 0) : 0) + 1; s.l = NOW();
  if (ok){ s.b = Math.min(s.b + 1, 4); s.d = NOW() + STEPS[s.b] * DAY; play.right++; }
  else { s.b = 0; s.d = NOW(); play.wrong++; play.queue.push(e); }   // mistake → to the end of this same session
  T[key] = s; save('T');
  play.idx++; play.shown = false; play.picked = null; play.opts = null; render();
}
function renderPlay(main){
  var p = play, box = el('div', 'tr-play');
  var hud = el('div', 'tr-hud'), close = el('button', 'btn', '← ' + L().toDecks); close.type = 'button';
  close.onclick = function(){ play = null; flush(); render(); }; hud.appendChild(close);
  if (p.idx < p.queue.length){
    hud.appendChild(el('span', 'tr-pill', (p.idx + 1) + ' / ' + p.queue.length));
    hud.appendChild(el('span', 'tr-pill g', '✓ ' + p.right)); hud.appendChild(el('span', 'tr-pill r', '✗ ' + p.wrong));
  }
  box.appendChild(hud);
  if (p.idx >= p.queue.length){
    var c = el('div', 'tr-done');
    c.appendChild(el('h3', null, L().endTitle));
    c.appendChild(el('p', null, L().right + ': ' + p.right + ' · ' + L().wrong + ': ' + p.wrong));
    var left = p.deck.items.filter(isDue).length;
    c.appendChild(el('p', 'meta', left ? L().dueNow + ': ' + left : L().allDoneTomorrow));
    var a = el('div', 'tr-acts');
    var again = el('button', 'btn primary', left ? L().again : L().random); again.type = 'button'; again.onclick = function(){ startRound(p.deck); };
    var back = el('button', 'btn', L().toDecks); back.type = 'button'; back.onclick = function(){ play = null; flush(); render(); };
    a.appendChild(again); a.appendChild(back); c.appendChild(a); box.appendChild(c); main.appendChild(box); flush(); return;
  }
  box.appendChild(bar([['d', p.idx / p.queue.length]]));
  var e = p.queue[p.idx], it = e.it, kind = p.deck.kind, pr = prompt(it, kind, e.f);
  var fresh = !!pr.pick;   // the "pick of 6" side
  var c = el('div', 'tr-box');
  c.appendChild(el('div', 'tr-lbl', pr.lbl));
  c.appendChild(el('div', 'tr-q' + (pr.small ? ' small' : ''), pr.q));
  if (pr.hint) c.appendChild(el('div', 'tr-hint', pr.hint));
  if (p.shown){
    var ans = el('div', 'tr-ans');
    ans.appendChild(el('div', pr.forms ? 'tr-forms' : 'tr-a' + (pr.small ? ' small' : ''), pr.a));
    if (it.note) ans.appendChild(el('div', 'tr-note', it.note));
    var ex = Array.isArray(it.ex) && it.ex.length ? it.ex[Math.floor(Math.random() * it.ex.length)] : null;
    if (ex){ var x = el('div', 'tr-ex'); x.appendChild(el('b', null, ex.en)); x.appendChild(document.createElement('br')); x.appendChild(document.createTextNode(ex.ru || '')); ans.appendChild(x); }
    else if (typeof it.ex === 'string'){ var x2 = el('div', 'tr-ex'); x2.appendChild(el('b', null, it.ex)); ans.appendChild(x2); }
    c.appendChild(ans);
  }
  box.appendChild(c);
  var below = el('div');
  if (fresh){
    // new word: pick the translation of 6, distractors from the same deck
    if (!p.opts){ var pool = p.deck.items.filter(function(w){ return w.id !== it.id; }); if (pool.length < 5) pool = (DECK.words || []).filter(function(w){ return w.id !== it.id; });
      p.opts = shuffle(shuffle(pool.slice()).slice(0, 5).concat([it])); }
    var ch = el('div', 'tr-choices');
    p.opts.forEach(function(o){
      var b = el('button', 'tr-choice', pr.pick === 'en' ? o.en : o.ru); b.type = 'button';
      if (p.picked){ b.disabled = true; if (o.id === it.id) b.className = 'tr-choice ok'; else if (o.id === p.picked) b.className = 'tr-choice no'; }
      b.onclick = function(){ p.picked = o.id; p.shown = true; render(); };
      ch.appendChild(b);
    });
    below.appendChild(ch);
    if (p.shown){ var nx = el('button', 'btn primary wide', L().next); nx.type = 'button'; nx.dataset.key = 'next'; nx.onclick = function(){ grade(p.picked === it.id); }; var a1 = el('div', 'tr-acts'); a1.appendChild(nx); below.appendChild(a1); }
    below.appendChild(el('p', 'tr-keys', p.shown ? L().keysNext : L().keysPick));
  } else if (!p.shown){
    var a2 = el('div', 'tr-acts'), sb = el('button', 'btn primary wide', L().show); sb.type = 'button'; sb.dataset.key = 'show';
    sb.onclick = function(){ p.shown = true; render(); }; a2.appendChild(sb); below.appendChild(a2);
    below.appendChild(el('p', 'tr-keys', L().keysShow));
  } else {
    var a3 = el('div', 'tr-acts');
    var m = el('button', 'btn bad', L().missed); m.type = 'button'; m.dataset.key = 'bad'; m.onclick = function(){ grade(false); };
    var g = el('button', 'btn good', L().got); g.type = 'button'; g.dataset.key = 'good'; g.onclick = function(){ grade(true); };
    a3.appendChild(m); a3.appendChild(g); below.appendChild(a3);
    below.appendChild(el('p', 'tr-keys', L().keysGrade));
  }
  box.appendChild(below);
  main.appendChild(box);
}
document.addEventListener('keydown', function(ev){
  if (!play || ui.tab !== 'trainer' || /INPUT|SELECT|TEXTAREA/.test((ev.target || {}).tagName || '')) return;
  var q = function(k){ return document.querySelector('.tr-play [data-key="' + k + '"]'); };
  if (ev.key === 'Escape'){ play = null; flush(); render(); return; }
  if (ev.key === ' ' || ev.key === 'Enter'){ var b = q('good') || q('next') || q('show'); if (b){ ev.preventDefault(); b.click(); } }
  else if (ev.key === '1' && q('bad')) q('bad').click();
  else if (ev.key === '2' && q('good')) q('good').click();
});

/* ---------- Interviews tab ---------- */
function fmtDate(d){ if (!d) return ''; var x = new Date(d + 'T00:00:00'); return isNaN(x) ? d : x.toLocaleDateString(ui.lang === 'en' ? 'en-GB' : ui.lang, {day: 'numeric', month: 'short'}); }
function renderCompanies(main){
  var up = REPORT.upcoming || [];
  if (up.length){
    main.appendChild(el('h2', 'sec', L().upcoming));
    var u = el('div', 'upcoming');
    up.forEach(function(x){ var sn = BY_ID[x.stage] || STAGES[x.stage]; var r = el('div', 'card'); r.appendChild(el('b', null, fmtDate(x.date) + (x.time ? ' ' + x.time : '') + ' · ' + x.company)); r.appendChild(el('span', 'meta', ' — ' + (x.title || (sn ? tt(sn) : x.stage)))); u.appendChild(r); });
    main.appendChild(u);
  }
  var weak = REPORT.weak_list || [];
  if (weak.length){
    main.appendChild(el('h2', 'sec', L().weakTopics));
    var w = el('div', 'card');
    weak.forEach(function(x){ var n = BY_ID[x.topic]; var r = el('div', null); r.appendChild(el('b', null, n ? tt(n) : x.topic)); r.appendChild(el('span', 'meta', ' — ' + x.companies.join(', ') + ' · ×' + x.score)); w.appendChild(r); });
    main.appendChild(w);
  }
  main.appendChild(el('h2', 'sec', L().companies));
  if (!COMPANIES.length) main.appendChild(el('p', 'meta', L().noCompanies));
  else {
    // one line over all companies: how many, in progress, offers, rejections
    var cnt = {run: 0, ok: 0, bad: 0};
    COMPANIES.forEach(function(co){ cnt[coOutcome(co).k]++; });
    var sm = el('div', 'co-summary');
    sm.appendChild(el('span', null, COMPANIES.length + ' ' + L().coSummary));
    [['run', L().coInProgress], ['ok', L().coSuccess], ['bad', L().coFail]].forEach(function(x){ if (cnt[x[0]]) sm.appendChild(el('span', 'oc ' + x[0], cnt[x[0]] + ' ' + x[1])); });
    main.appendChild(sm);
  }
  COMPANIES.forEach(function(co){ main.appendChild(drawCompany(co)); });
  main.appendChild(el('h2', 'sec', L().addEntry));
  main.appendChild(drawForm());
}
/* company outcome: offer/accepted — success; rejected or a failed stage — failure; withdrawn/paused — closed */
function coOutcome(co){
  var s = co.status, st = co.stages || [];
  if (s === 'offer' || s === 'accepted') return {k: 'ok', label: L().cst[s] || s};
  if (s === 'rejected' || st.some(function(x){ return x.status === 'failed'; })) return {k: 'bad', label: L().cst.rejected || s};
  if (s === 'withdrawn' || s === 'paused') return {k: 'off', label: L().cst[s] || s};
  return {k: 'run', label: L().cst[s] || s};
}
var STAGE_ICON = {passed: '✓', failed: '✕', scheduled: '●', expected: '○', cancelled: '–', skipped: '–'};
function drawCompany(co){
  var oc = coOutcome(co), st = (co.stages || []);
  var counted = st.filter(function(x){ return x.status !== 'cancelled' && x.status !== 'skipped'; });
  var passed = counted.filter(function(x){ return x.status === 'passed'; }).length;
  var key = 'co:' + co.id;
  // open by default while the process is running; finished companies start collapsed
  var open = S.expanded[key] != null ? !!S.expanded[key] : oc.k === 'run';
  var c = el('section', 'pcard co ' + oc.k + (open ? ' open' : ''));
  var hd = el('button', 'phead'); hd.type = 'button'; hd.setAttribute('aria-expanded', String(open));
  var pt = el('span', 'pt', co.name); hd.appendChild(pt);
  hd.appendChild(el('span', 'oc ' + oc.k, oc.label));
  hd.appendChild(el('span', 'pc', passed + ' / ' + counted.length));
  hd.appendChild(el('span', 'chev', '›'));
  c.appendChild(hd);
  // progress bar by stage: passed · failed · scheduled · still ahead
  var pb = el('div', 'co-bar');
  counted.forEach(function(x){ pb.appendChild(el('i', 's-' + x.status)); });
  if (!counted.length) pb.appendChild(el('i', 's-expected'));
  c.appendChild(pb);
  var body = el('div', 'pbody'); body.hidden = !open; c.appendChild(body);
  var filled = false;
  function fill(){
    if (filled) return; filled = true;
    var v = co.vacancy || {}; var meta = [v.title, v.salary, v.format].filter(Boolean).join(' · '); if (meta) body.appendChild(el('div', 'meta', meta));
    var nx = st.filter(function(x){ return x.status === 'scheduled' || x.status === 'expected'; })[0];
    if (nx && oc.k === 'run'){ var sn0 = BY_ID[nx.stage] || STAGES[nx.stage];
      var nl = el('div', 'co-next'); nl.appendChild(el('b', null, L().coNext + ': '));
      nl.appendChild(document.createTextNode((nx.title || (sn0 ? tt(sn0) : nx.stage)) + (nx.date ? ' · ' + fmtDate(nx.date) : '') + (nx.time ? ' ' + nx.time : '')));
      body.appendChild(nl); }
    var dg = DOCS.filter(function(g){ return g.id === co.id; })[0];
    if (dg){ var lk = el('button', 'chip', L().docs + ': ' + dg.docs.map(function(x){ return x.kind === 'cv' ? L().cv : L().cover; }).join(', ') + ' →'); lk.type = 'button'; lk.style.marginTop = '8px'; lk.onclick = function(){ ui.tab = 'docs'; lsSet('prep.tab', 'docs'); render(); scrollTo(0, 0); }; body.appendChild(lk); }
    body.appendChild(el('h4', null, L().coMap + ' · ' + L().done + ' ' + passed + ' ' + L().of + ' ' + counted.length));
    if (!st.length) body.appendChild(el('p', 'meta', L().coNoStages));
    // stage map: a vertical stepper, click a stage for its questions and notes
    var map = el('ol', 'co-map');
    st.forEach(function(x, i){
      var li = el('li', 'step ' + x.status), b = el('button', 'step-head'); b.type = 'button'; b.setAttribute('aria-expanded', 'false');
      b.appendChild(el('span', 'dot', STAGE_ICON[x.status] || String(i + 1)));
      var sn = BY_ID[x.stage] || STAGES[x.stage], tx = el('span', 'step-t');
      tx.appendChild(el('b', null, x.title || (sn ? tt(sn) : x.stage)));
      tx.appendChild(el('span', 'st', (L().st[x.status] || x.status) + (x.date ? ' · ' + fmtDate(x.date) : '') + (x.time ? ' ' + x.time : '')));
      b.appendChild(tx); li.appendChild(b);
      var det = el('div', 'step-d'); det.hidden = true; var dFilled = false;
      b.onclick = function(){
        if (!dFilled){ dFilled = true;
          if ((x.questions || []).length){ det.appendChild(el('h4', null, L().questions)); var ul = el('ul');
            x.questions.forEach(function(q){ var qi = el('li', null, q.q); if (q.went) qi.appendChild(el('span', 'badge ' + (q.went === 'bad' ? 'weak' : 'origin'), L().went[q.went])); if (q.note) qi.appendChild(el('div', 'meta', q.note)); ul.appendChild(qi); });
            det.appendChild(ul); }
          [['feelings', x.feelings], ['feedback', x.feedback], ['next', x.next]].forEach(function(y){ if (y[1]){ var p = el('p'); p.appendChild(el('b', null, L()[y[0]] + ': ')); p.appendChild(document.createTextNode(y[1])); det.appendChild(p); } });
          if (!det.childNodes.length) det.appendChild(el('p', 'meta', '—'));
        }
        det.hidden = !det.hidden; b.setAttribute('aria-expanded', String(!det.hidden));
      };
      li.appendChild(det); map.appendChild(li);
    });
    body.appendChild(map);
    if ((co.log || []).length){
      var hs = el('details', 'co-log'); hs.appendChild(el('summary', null, L().history + ' · ' + co.log.length));
      var ul = el('ul', 'log');
      co.log.slice().reverse().forEach(function(e){ var li = el('li'); li.appendChild(el('b', null, fmtDate(e.date) + ' · ' + (L().kinds[e.kind] || e.kind) + (e.with ? ' · ' + e.with : '') + ' — '));
        li.appendChild(document.createTextNode(e.text));
        if (e.facts){ li.appendChild(el('div', 'facts', Object.keys(e.facts).map(function(k){ return k + ': ' + e.facts[k]; }).join(' · '))); }
        ul.appendChild(li); });
      hs.appendChild(ul); hs.open = oc.k === 'run'; body.appendChild(hs);
    }
  }
  if (open) fill();
  hd.addEventListener('click', function(){   // in place, like the plan cards
    if (tooSoon(hd)) return;
    var o = body.hidden; if (o) fill();
    S.expanded[key] = o; body.hidden = !o; c.classList.toggle('open', o); hd.setAttribute('aria-expanded', String(o));
    save('S');
  });
  return c;
}
function drawForm(){
  var f = el('form', 'card form');
  function field(label, input, full){ var l = el('label', full ? 'full' : null, label); l.appendChild(input); f.appendChild(l); return input; }
  var cs = el('select'); COMPANIES.forEach(function(c){ var o = el('option', null, c.name); o.value = c.id; cs.appendChild(o); }); var on = el('option', null, L().newCompany); on.value = '__new'; cs.appendChild(on);
  field(L().company, cs);
  var nn = el('input'); nn.placeholder = L().company; var nl = field(L().newCompany, nn); nl.parentNode.hidden = COMPANIES.length > 0;
  cs.onchange = function(){ nl.parentNode.hidden = cs.value !== '__new'; };
  var ks = el('select'); Object.keys(L().kinds).forEach(function(k){ var o = el('option', null, L().kinds[k]); o.value = k; ks.appendChild(o); }); field(L().kind, ks);
  var dt = el('input'); dt.type = 'date'; dt.value = new Date().toISOString().slice(0, 10); field(L().date, dt);
  var tx = el('textarea'); tx.rows = 4; tx.required = true; field(L().text, tx, true);
  var sb = el('button', 'btn primary full', L().submit); sb.type = 'submit'; f.appendChild(sb);
  var msg = el('p', 'meta full'); f.appendChild(msg);
  f.onsubmit = async function(e){
    e.preventDefault(); if (!tx.value.trim()) return;
    var rec = {company: cs.value === '__new' ? '' : cs.value, company_name: cs.value === '__new' ? nn.value.trim() : cs.options[cs.selectedIndex].text,
      kind: ks.value, date: dt.value, text: tx.value.trim(), created: NOW()};
    try { await sendInbox(rec); tx.value = ''; msg.textContent = L().inboxOk; }
    catch (err){ msg.textContent = err && err.message ? err.message : L().local; }
  };
  return f;
}

/* ---------- Documents tab ---------- */
function renderDocs(main){
  if (!DOCS.length){ placeholder(main, L().phDocs); return; }
  DOCS.forEach(function(g){
    main.appendChild(el('h2', 'sec', g.id === 'general' ? L().myCv : g.name));
    var grid = el('div', 'grid');
    g.docs.forEach(function(d){
      var c = el('article', 'card doc');
      if (d.kind === 'cv'){
        c.appendChild(el('h3', null, L().cv + ' · ' + d.lang.toUpperCase()));
        if (d.error){ c.appendChild(el('p', 'note', d.error)); grid.appendChild(c); return; }
        if (d.title) c.appendChild(el('div', 'meta', d.title));
        var a = el('div', 'acts left');
        var open = el('button', 'btn primary', L().open); open.type = 'button';
        open.onclick = function(){ if (api) window.open(d.href, '_blank'); else { var w = window.open('', '_blank'); if (w){ w.document.write(d.html); w.document.close(); } else download(d.file + '.html', d.html, 'text/html'); } };
        a.appendChild(open);
        if (api && d.pdf){ var pdf = el('a', 'btn', 'PDF'); pdf.href = d.pdf; pdf.download = d.file + '.pdf'; a.appendChild(pdf); }
        else { var pr = el('button', 'btn', L().printPdf); pr.type = 'button'; pr.onclick = function(){ var w = window.open(api ? d.href : '', '_blank'); if (!w) return download(d.file + '.html', d.html, 'text/html'); if (!api){ w.document.write(d.html); w.document.close(); } setTimeout(function(){ try { w.print(); } catch (e){} }, 600); }; a.appendChild(pr); }
        var h = el('button', 'btn', 'HTML'); h.type = 'button'; h.onclick = function(){ download(d.file + '.html', d.html, 'text/html'); }; a.appendChild(h);
        var m = el('button', 'btn', 'Markdown'); m.type = 'button'; m.onclick = function(){ download(d.file + '.md', d.md); }; a.appendChild(m);
        c.appendChild(a);
      } else {
        c.appendChild(el('h3', null, L().cover + ' · ' + d.lang.toUpperCase()));
        c.appendChild(el('div', 'meta', d.words + ' ' + L().words));
        var body = el('div', 'cover'); body.innerHTML = d.html; c.appendChild(body);
        var a2 = el('div', 'acts left');
        var cp = el('button', 'btn primary', L().copy); cp.type = 'button'; cp.onclick = function(){ copyText(d.md, cp); }; a2.appendChild(cp);
        var t = el('button', 'btn', '.txt'); t.type = 'button'; t.onclick = function(){ download(d.file + '.txt', d.md); }; a2.appendChild(t);
        var md = el('button', 'btn', '.md'); md.type = 'button'; md.onclick = function(){ download(d.file + '.md', d.md); }; a2.appendChild(md);
        c.appendChild(a2);
      }
      grid.appendChild(c);
    });
    main.appendChild(grid);
  });
}

function rerenderKeepScroll(){ var y = scrollY; render(); scrollTo(0, y); }

/* ---------- common render ---------- */
function render(){
  renderHead();
  var main = $('main'); main.innerHTML = '';
  if (ui.tab === 'vocab') DECK && DECK.words && DECK.words.length ? renderVocab(main) : placeholder(main, L().phVocab);
  else if (ui.tab === 'trainer') DECK && DECK.words && DECK.words.length ? renderTrainer(main) : placeholder(main, L().phTrainer);
  else if (ui.tab === 'companies') renderCompanies(main);
  else if (ui.tab === 'docs') renderDocs(main);
  else renderPlan(main);
}
(function(){ var box = $('langs'); if (LANGS.length < 2){ box.hidden = true; return; }   // English only: nothing to switch to
  LANGS.forEach(function(l){ var b = el('button', null, l.toUpperCase()); b.type = 'button'; b.dataset.lang = l; b.title = (D.lang_names || {})[l] || l;
    b.onclick = function(){ ui.lang = l; lsSet('prep.lang', ui.lang); render(); }; box.appendChild(b); }); })();
function applyTheme(){ if (ui.theme) document.documentElement.setAttribute('data-theme', ui.theme); else document.documentElement.removeAttribute('data-theme'); }
$('theme').onclick = function(){ var dark = ui.theme ? ui.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches; ui.theme = dark ? 'light' : 'dark'; lsSet('prep.theme', ui.theme); applyTheme(); };
applyTheme();

/* default state: everything collapsed except the first stage */
/* cards are collapsed by default */
var fb = lsGet('prep.fallback', null); if (fb){ S = asS(fb.S); T = fb.T || T; } V = lsGet('prep.vocab', {});
render();

/* ---------- storage: local server → artifact db → this browser only ---------- */
(async function(){
  var local = /^https?:$/.test(location.protocol) && /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);
  if (local){
    try {
      var ping = await fetch('/api/ping', {cache: 'no-store'});
      if (ping.ok){
        api = true;
        var st = await (await fetch('/api/state')).json(); if (st && st.done) S = asS(st);
        var tr = await (await fetch('/api/trainer')).json(); if (tr && tr.items) T = tr.items; if (tr && tr.goal >= 1) GOAL = +tr.goal;
        var vc = await (await fetch('/api/vocab')).json(); if (vc && typeof vc === 'object') V = vc;
        render(); setSync(L().live);
        liveReload();
        return;
      }
    } catch (e){}
  }
  try {
    var h = window.claude && window.claude.use ? await window.claude.use('db') : null;
    if (!h){ setSync(L().local); return; }
    // read everything first; only then enable writes (db = h), so nothing is written unread
    var s = await h.doc('prep/state').get();
    var t = await h.doc('trainer/state').get();
    var v = await h.collection('vocab').get();
    if (s.exists){ S = mergeS(s.data(), dirty.S ? S : null); seen.S = true; }
    if (t.exists && t.data().items){ T = Object.assign(clone(t.data().items), dirty.T ? T : {}); seen.T = true; if (t.data().goal >= 1 && !dirty.T) GOAL = +t.data().goal; }
    V = {}; v.docs.forEach(function(d){ V[d.id] = clone(d.data()); });
    db = h;
    render(); setSync(L().saved);
    if (dirty.S || dirty.T) flush();
  } catch (e){ db = null; setSync(L().local); }
})();

/* auto-refresh: the agent rebuilt the page → version.json changed → reload in place */
function liveReload(){
  var y = sessionStorage.getItem('prep.scroll'); if (y){ sessionStorage.removeItem('prep.scroll'); setTimeout(function(){ scrollTo(0, +y); }, 50); }
  setInterval(async function(){
    try {
      var v = await (await fetch('version.json', {cache: 'no-store'})).json();
      if (v.id && v.id !== (D.build || {}).id && !play){
        await flush();
        try { sessionStorage.setItem('prep.scroll', String(scrollY)); } catch (e){}
        location.reload();
      }
    } catch (e){}
  }, 2500);
}
})();
