
const BACKEND = "https://lian-zfg8.onrender.com";
const $status = document.getElementById('status');
const $grid = document.getElementById('grid');
const $log = document.getElementById('log');
const $dateInput = document.getElementById('dateInput');
const $countBadge = document.getElementById('countBadge');
const $searchBox = document.getElementById('searchBox');
const $searchInput = document.getElementById('searchInput');
const $leagueSelect = document.getElementById('leagueSelect');

let allMatches = [];
let currentFilter = 'all';

function log(msg, cls=''){
  const d=document.createElement('div');
  d.textContent=`[${new Date().toLocaleTimeString()}] ${msg}`;
  if(cls) d.className=cls;
  $log.prepend(d);
}
function esc(s){
  if(!s) return '';
  const div=document.createElement('div');
  div.textContent=s;
  return div.innerHTML;
}
async function api(path){
  const url=BACKEND+path;
  log(`GET ${url}`);
  try{
    const r=await fetch(url,{mode:'cors'});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const j=await r.json();
    log(`OK ${path} -> ${j.count||j.records||'ok'}`, 'ok');
    return j;
  }catch(e){
    log(`ERROR ${path}: ${e.message}`, 'err');
    throw e;
  }
}
function cardA(m){
  const p = m.probabilities || {"1":0,"X":0,"2":0};
  const total = (p['1']+p['X']+p['2']).toFixed(1);
  const confColor = m.confidence==='Alta'?'#1ee07a':m.confidence==='Media'?'#ffcc00':'#ff8a8a';
  const ligaEmoji = m.league_code==='mex.1'?'🇲🇽':m.league_code==='usa.1'?'🇺🇸':m.league_code==='eng.1'?'🏴󠁧󠁢󠁥󠁮󠁧󠁿':m.league_code?.includes('champions')?'🏆':'⚽';
  return `
  <div class="card" data-league="${esc(m.league||'')}" data-home="${esc(m.home||'')}" data-away="${esc(m.away||'')}">
    <div class="badge-row"><span class="tag">${ligaEmoji} ${esc(m.league_code||'')}</span><span class="league">${esc(m.league||'Futbol')} • ${esc(m.time||'')} • ${esc(m.date||'')}</span></div>
    <div class="teams">${esc(m.home)} <span style="color:#8aa0c8">vs</span> ${esc(m.away)}</div>
    <div class="prob-row">
      <span class="prob">1: ${p['1']}%</span>
      <span class="prob">X: ${p['X']}%</span>
      <span class="prob">2: ${p['2']}%</span>
      <span class="total">Σ ${total}%</span>
    </div>
    <div class="meta">⭐ Favorito: <b>${esc(m.favorite||'')}</b> | xG: ${m.xg_home||0}-${m.xg_away||0}</div>
    <div class="meta">Conf: <span style="color:${confColor};font-weight:700">${esc(m.confidence||'')}</span> • Ev: ${m.evidence||0} • Riesgo: ${esc(m.risk||'')} • Suf: ${esc(m.sufficiency||'')}</div>
    <div class="meta" style="font-size:11px;color:#8aa0c8">Fuente: ${esc(m.source||'')} • ${esc(m.status||'')}</div>
    <details class="explain"><summary>🔍 Explicabilidad (F)</summary><ul>${(m.explicabilidad||[]).map(e=>`<li>${esc(e)}</li>`).join('')}</ul><div class="transp">⚠️ ${esc(m.transparencia||'')}</div></details>
  </div>`;
}

function getFiltered(){
  let filtered = allMatches;
  if(currentFilter==='top'){
    filtered = allMatches.filter(m=>m.confidence==='Alta' || m.confidence==='Media');
  }else if(currentFilter==='liga-mx'){
    filtered = allMatches.filter(m=>(m.league||'').toLowerCase().includes('mx') || m.league_code==='mex.1');
  }else if(currentFilter==='mls'){
    filtered = allMatches.filter(m=>(m.league||'').toLowerCase().includes('mls') || m.league_code==='usa.1');
  }else if(currentFilter==='champions'){
    filtered = allMatches.filter(m=>(m.league||'').toLowerCase().includes('champions') || (m.league_code||'').includes('champions'));
  }else if(currentFilter==='europa'){
    filtered = allMatches.filter(m=>['eng.1','esp.1','ita.1','ger.1','fra.1'].includes(m.league_code));
  }else if(currentFilter==='search'){
    const q = ($searchInput.value||'').toLowerCase();
    const liga = $leagueSelect.value;
    filtered = allMatches.filter(m=>{
      const matchQ = !q || m.home.toLowerCase().includes(q) || m.away.toLowerCase().includes(q);
      const matchLiga = liga==='all' || (m.league||'').includes(liga);
      return matchQ && matchLiga;
    });
  }else if(currentFilter==='combinada'){
    filtered = allMatches.filter(m=>m.confidence==='Alta' || m.confidence==='Media').slice(0,6);
  }else if(currentFilter==='progol'){
    filtered = allMatches.slice(0,14); // 14 partidos para progol
  }
  return filtered;
}

function renderAll(){
  const filtered = getFiltered();
  $countBadge.textContent = `${filtered.length} partidos / ${allMatches.length} total`;

  if(filtered.length===0){
    $grid.innerHTML=`<div class="card">No hay partidos para este filtro. Prueba otro filtro o sincroniza.</div>`;
    return;
  }

  let html = '';
  if(currentFilter==='all'){
    html += `<div class="section-title">⊙ Partidos del día (${filtered.length} partidos - 15 ligas mundiales)</div>`;
    html += filtered.map(cardA).join('');
  }else if(currentFilter==='top'){
    html += `<div class="section-title">★ Top Picks - Alta/Media confianza (${filtered.length})</div>`;
    html += filtered.map(cardA).join('');
  }else if(currentFilter==='combinada'){
    html += `<div class="section-title">∽ Combinadas (${filtered.length} selecciones)</div>`;
    html += filtered.map(cardA).join('');
    if(filtered.length>=2){
      const sel = filtered.slice(0,3).map(m=>{
        const bestProb = Math.max(m.probabilities['1'], m.probabilities['2'], m.probabilities['X']);
        return {match: `${m.home} vs ${m.away}`, prob: bestProb/100};
      });
      const conjunta = sel.reduce((acc,s)=>acc*s.prob,1)*100;
      html += `<div class="card combo"><div class="league">Fórmula: ${sel.map(s=>`${(s.prob*100).toFixed(1)}%`).join(' × ')} = ${conjunta.toFixed(2)}%</div>`;
      sel.forEach(s=>{ html+=`<div class="meta">• ${esc(s.match)} - ${(s.prob*100).toFixed(1)}%</div>`; });
      html+=`<div class="meta" style="margin-top:8px;color:#ffcc00">⚠️ Probabilidad != garantía. Conjunta baja con muchas selecciones.</div></div>`;
    }
  }else if(currentFilter==='progol'){
    html += `<div class="section-title">▤ Progol - 14 partidos (quiniela mexicana)</div>`;
    html += filtered.map((m,i)=>`<div class="card progol"><div class="progol-num">${i+1}</div>`+cardA(m)+`</div>`).join('');
  }else if(currentFilter==='liga-mx'){
    html += `<div class="section-title">🇲🇽 Liga MX (${filtered.length} partidos)</div>`;
    html += filtered.map(cardA).join('');
  }else if(currentFilter==='mls'){
    html += `<div class="section-title">🇺🇸 MLS (${filtered.length} partidos)</div>`;
    html += filtered.map(cardA).join('');
  }else if(currentFilter==='champions'){
    html += `<div class="section-title">🏆 Champions League (${filtered.length} partidos)</div>`;
    html += filtered.map(cardA).join('');
  }else if(currentFilter==='europa'){
    html += `<div class="section-title">🏅 Top 5 Europa (Premier, LaLiga, Serie A, Bundesliga, Ligue 1) - ${filtered.length}</div>`;
    html += filtered.map(cardA).join('');
  }else if(currentFilter==='search'){
    html += `<div class="section-title">🔍 Búsqueda: "${esc($searchInput.value||'')}" en ${esc($leagueSelect.value)} - ${filtered.length} resultados</div>`;
    html += filtered.map(cardA).join('');
  }

  html += `<div class="section-title">📊 Transparencia</div>`;
  html += `<div class="card"><div class="meta">Probabilidad != recomendación segura. Suma 1X2 ~100% validado.</div><div class="meta">Fuente: ESPN_MULTI_15LIGAS + Ensemble 58%/16%/10%/16% 6000 sims</div><div class="meta">Ligas: Premier, LaLiga, Serie A, Bundesliga, Ligue1, Liga MX, MLS, Brasileirao, Argentina, Champions, Europa, Conference, Concachampions</div><div class="meta">Versión: V64.6.0 Paso5 Multi-Liga Mundial</div></div>`;

  $grid.innerHTML = html;
}

async function loadFast(){
  const date=$dateInput.value||new Date().toISOString().slice(0,10);
  $status.textContent=`Cargando ${date} - 15 ligas...`;
  try{
    const data=await api(`/api/calendar/fast?date=${date}`);
    allMatches = data.matches || [];
    $status.textContent=`${data.count} partidos reales de ${date} - ${data.source||''}`;
    renderAll();
  }catch(e){ $status.textContent=`Error: ${e.message}`; }
}
async function refresh(){
  const date=$dateInput.value||new Date().toISOString().slice(0,10);
  $status.textContent=`Sincronizando ${date} con 15 ligas ESPN...`;
  try{
    await api(`/api/calendar?date=${date}&refresh=1`);
    log('Sincronizando 15 ligas, esperando 8s...');
    setTimeout(loadFast,8000);
  }catch(e){ $status.textContent=`Error sync: ${e.message}`; }
}

// Menu lateral
document.querySelectorAll('.menu-item').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    if(currentFilter==='search'){
      $searchBox.style.display='block';
    }else{
      $searchBox.style.display='none';
    }
    renderAll();
  });
});
$searchInput.addEventListener('input', renderAll);
$leagueSelect.addEventListener('change', renderAll);

document.getElementById('loadBtn').addEventListener('click',loadFast);
document.getElementById('refreshBtn').addEventListener('click',refresh);
(async()=>{
  $dateInput.value=new Date().toISOString().slice(0,10);
  try{
    const h=await api('/api/health');
    $status.textContent=`API: ${h.version} - ${h.records} partidos`;
    loadFast();
  }catch{ $status.textContent='API no conecta.'; }
})();
