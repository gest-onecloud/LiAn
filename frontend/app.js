
const BACKEND = "https://lian-backend.onrender.com";
const $status = document.getElementById('status');
const $grid = document.getElementById('grid');
const $log = document.getElementById('log');
const $dateInput = document.getElementById('dateInput');

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
function card(m){
  const p = m.probabilities || {"1":0,"X":0,"2":0};
  const total = (p['1']+p['X']+p['2']).toFixed(1);
  const confColor = m.confidence==='Alta'?'#1ee07a':m.confidence==='Media'?'#ffcc00':'#ff8a8a';
  return `
  <div class="card">
    <div class="league">${esc(m.league||'Futbol')} • ${esc(m.time||'')} • ${esc(m.date||'')}</div>
    <div class="teams">${esc(m.home)} <span style="color:#8aa0c8">vs</span> ${esc(m.away)}</div>
    <div class="prob-row">
      <span class="prob">1: ${p['1']}%</span>
      <span class="prob">X: ${p['X']}%</span>
      <span class="prob">2: ${p['2']}%</span>
      <span class="total">Σ ${total}%</span>
    </div>
    <div class="meta">⭐ Favorito: <b>${esc(m.favorite||'')}</b> | xG: ${m.xg_home||0}-${m.xg_away||0}</div>
    <div class="meta">Confianza: <span style="color:${confColor};font-weight:700">${esc(m.confidence||'')}</span> • Evidencia: ${m.evidence||0} • Riesgo: ${esc(m.risk||'')} • Suf: ${esc(m.sufficiency||'')}</div>
    <div class="meta" style="margin-top:6px;color:#8aa0c8;font-size:11px">Fuente: ${esc(m.source||'')} • ${esc(m.status||'')}</div>
  </div>`;
}
async function loadFast(){
  const date=$dateInput.value||new Date().toISOString().slice(0,10);
  $status.textContent=`Cargando ${date} + calculando Poisson...`;
  $grid.innerHTML='';
  try{
    const data=await api(`/api/calendar/fast?date=${date}`);
    $status.textContent=`${data.count} partidos reales de ${date} - ${data.source||''}`;
    if(data.matches.length===0){
      $grid.innerHTML=`<div class="card">No hay partidos en BD para ${date}. Dale a "Sincronizar con ESPN".</div>`;
    }else{
      $grid.innerHTML=data.matches.map(card).join('');
    }
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
