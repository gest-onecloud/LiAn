
const BACKEND = "https://lian-zfg8.onrender.com";
const $status = document.getElementById('status');
const $grid = document.getElementById('grid');
const $log = document.getElementById('log');
const $dateInput = document.getElementById('dateInput');

let allMatches = [];

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
  return `
  <div class="card">
    <div class="badge-row"><span class="tag">A - CALENDARIO</span><span class="league">${esc(m.league||'Futbol')} • ${esc(m.time||'')} • ${esc(m.date||'')}</span></div>
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

function renderAll(){
  if(allMatches.length===0){
    $grid.innerHTML=`<div class="card">No hay partidos. Sincroniza con ESPN.</div>`;
    return;
  }
  // A - Calendario (todos)
  // B - Individual (mismo que A por ahora)
  // C - Top Picks (confianza Alta/Media)
  const topPicks = allMatches.filter(m=>m.confidence==='Alta' || m.confidence==='Media').sort((a,b)=>Math.max(b.probabilities['1'],b.probabilities['2'])-Math.max(a.probabilities['1'],a.probabilities['2'])).slice(0,6);

  let html = `<div class="section-title">📅 A - CALENDARIO (${allMatches.length} partidos reales)</div>`;
  html += allMatches.map(cardA).join('');

  if(topPicks.length>0){
    html += `<div class="section-title">🏆 C - TOP PICKS (Alta/Media confianza)</div>`;
    html += topPicks.map(cardA).join('');

    // D - Combinadas: 0.70*0.65*0.60=27.3%
    if(topPicks.length>=3){
      const sel = topPicks.slice(0,3).map(m=>{
        const bestProb = Math.max(m.probabilities['1'], m.probabilities['2'], m.probabilities['X']);
        return {match: `${m.home} vs ${m.away}`, prob: bestProb/100};
      });
      const conjunta = sel.reduce((acc,s)=>acc*s.prob,1)*100;
      html += `<div class="section-title">🎲 D - COMBINADAS (Prob conjunta = ${conjunta.toFixed(1)}%)</div>`;
      html += `<div class="card combo"><div class="league">Formula: ${sel.map(s=>`${(s.prob*100).toFixed(1)}%`).join(' × ')} = ${conjunta.toFixed(2)}%</div>`;
      sel.forEach(s=>{ html+=`<div class="meta">• ${esc(s.match)} - ${(s.prob*100).toFixed(1)}%</div>`; });
      html+=`<div class="meta" style="margin-top:8px;color:#ffcc00">⚠️ Probabilidad != garantia. Conjunta baja con muchas selecciones.</div></div>`;
    }
  }

  // G - Resultados / Transparencia
  html += `<div class="section-title">📊 G - TRANSPARENCIA / RESULTADOS</div>`;
  html += `<div class="card"><div class="meta">Probabilidad != recomendacion segura.</div><div class="meta">Suma 1X2 ~100% (validado en cada tarjeta).</div><div class="meta">Fuente: ESPN_ALL + Ensemble Poisson 58% / ELO 16% / Forma 10% / MonteCarlo 6000 sims 16%</div><div class="meta">Actualizacion: ${new Date().toLocaleString()}</div><div class="meta">Version: V64.6.0 REAL - Paso 3 FINAL</div></div>`;

  $grid.innerHTML = html;
}

async function loadFast(){
  const date=$dateInput.value||new Date().toISOString().slice(0,10);
  $status.textContent=`Cargando ${date} + calculando Ensemble Poisson 58%...`;
  $grid.innerHTML='';
  try{
    const data=await api(`/api/calendar/fast?date=${date}`);
    allMatches = data.matches || [];
    $status.textContent=`${data.count} partidos reales de ${date} - ${data.source||''} - 7 tarjetas A-G`;
    renderAll();
  }catch(e){ $status.textContent=`Error: ${e.message}`; }
}
async function refresh(){
  const date=$dateInput.value||new Date().toISOString().slice(0,10);
  $status.textContent=`Sincronizando ${date} con ESPN (5s reales)...`;
  try{
    await api(`/api/calendar?date=${date}&refresh=1`);
    log('Sincronizacion iniciada, esperando 5s...');
    setTimeout(loadFast,5000);
  }catch(e){ $status.textContent=`Error sync: ${e.message}`; }
}
document.getElementById('loadBtn').addEventListener('click',loadFast);
document.getElementById('refreshBtn').addEventListener('click',refresh);
(async()=>{
  $dateInput.value=new Date().toISOString().slice(0,10);
  try{
    const h=await api('/api/health');
    $status.textContent=`API Conectada: ${h.version} - ${h.records} partidos en BD`;
    loadFast();
  }catch{ $status.textContent='API no conecta. Revisa Render.'; }
})();
