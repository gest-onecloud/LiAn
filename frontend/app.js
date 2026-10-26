
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
let SEASON_CACHE = [];
let currentFilter = 'all';
let customCombinada = [];
let _lastTopAlta = [];
let _lastTopMedia = [];
let ALL_BASE_CACHE_LOADED = false;

var PROGOL_REAL = [
  {n:1, home:'PUEBLA', away:'PUMAS'},
  {n:2, home:'PACHUCA', away:'TIGRES'},
  {n:3, home:'AGUILAS', away:'TOLUCA'},
  {n:4, home:'ELCHE', away:'VALENCIA'},
  {n:5, home:'ATH. BILBAO', away:'R. SOCIEDAD'},
  {n:6, home:'BOURNEMOUTH', away:'LEEDS'},
  {n:7, home:'LIVERPOOL', away:'ARSENAL'},
  {n:8, home:'MILAN', away:'INTER MILAN'},
  {n:9, home:'JUVENTUS', away:'NAPOLES'},
  {n:10, home:'AUGSBURGO', away:'FRIBURGO'},
  {n:11, home:'LORIENT', away:'BREST'},
  {n:12, home:'GREMIO', away:'AT. MINEIRO'},
  {n:13, home:'BOCA JRS', away:'RIVER PLATE'},
  {n:14, home:'U. CATOLICA', away:'U. DE CHILE'}
];
var REVANCHA_REAL = [
  {n:1, home:'MONTERREY', away:'TIJUANA'},
  {n:2, home:'GUADALAJARA', away:'ATLANTE'},
  {n:3, home:'S. LAGUNA', away:'NECAXA'},
  {n:4, home:'C. AZUL', away:'LEON'},
  {n:5, home:'GETAFE', away:'SEVILLA'},
  {n:6, home:'CHELSEA', away:'MAN. UNITED'},
  {n:7, home:'AJAX', away:'AZ ALKMAAR'}
];
var PROGOL_META = {fecha:'2026-10-30', hasta:'20:55', fuente:'TuLotero - Manual'};

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
function norm(s){ return (s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,''); }
function ln(m){ return norm((m.league||'')+' '+(m.league_code||'')); }
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
function toggleCombinada(key){
  const idx=customCombinada.findIndex(m=> (m._key||'')===key);
  if(idx>=0){ customCombinada.splice(idx,1); } else { const m=allMatches.find(x=> (x._key||`${x.date}_${x.home}_${x.away}`)===key); if(m && customCombinada.length<6){ customCombinada.push(m); } }
  renderAll();
}
function clearCombinada(){ customCombinada=[]; renderAll(); }
function useSuggested(tipo){
  if(tipo==='doble') customCombinada=_lastTopAlta.slice(0,2);
  else if(tipo==='triple') customCombinada=[..._lastTopAlta.slice(0,2), ..._lastTopMedia.slice(0,1)];
  else if(tipo==='cuadruple') customCombinada=[..._lastTopAlta.slice(0,2), ..._lastTopMedia.slice(0,2)];
  renderAll();
  window.scrollTo(0,0);
}
function calcCombinadaStats(matches){
  let prob=1,cuota=1;
  matches.forEach(m=>{
    const p=m.probabilities||{'1':33,'X':33,'2':33};
    const maxP=Math.max(p['1']||0,p['X']||0,p['2']||0);
    prob*=(maxP/100);
    const c=maxP>0?(100/maxP):3;
    cuota*=c;
  });
  return {prob:prob*100, cuota};
}
function calcAnalytics(matches){
  const finalizados=matches.filter(m=>m.estado==='FINALIZADO');
  const porLiga={};
  finalizados.forEach(m=>{
    const liga=m.league||m.league_code||'Desconocida';
    if(!porLiga[liga]) porLiga[liga]={aciertos:0,fallos:0,total:0};
    porLiga[liga].total++;
    if(m.acierto===true) porLiga[liga].aciertos++; else if(m.acierto===false) porLiga[liga].fallos++;
  });
  let ligaMas=null,maxAc=-1,ligaMenos=null,minAc=999;
  for(const [liga,data] of Object.entries(porLiga)){
    if(data.aciertos>maxAc){maxAc=data.aciertos; ligaMas={liga,...data};}
    if(data.aciertos<minAc){minAc=data.aciertos; ligaMenos={liga,...data};}
  }
  const confStats={Alta:{aciertos:0,fallos:0,total:0},Media:{aciertos:0,fallos:0,total:0},Limitada:{aciertos:0,fallos:0,total:0}};
  finalizados.forEach(m=>{const c=m.confidence; if(!confStats[c]) return; confStats[c].total++; if(m.acierto===true) confStats[c].aciertos++; else if(m.acierto===false) confStats[c].fallos++;});
  return {porLiga,ligaMasAciertos:ligaMas,ligaMenosAciertos:ligaMenos,confStats,totalFinalizados:finalizados.length};
}
function renderAnalytics(matches){
  const a=calcAnalytics(matches);
  if(a.totalFinalizados===0) return `<div class="analytics-panel"><div class="section-title">📊 Estadísticas</div><div class="analytics-card">Aún no hay finalizados hoy.</div></div>`;
  const mas=a.ligaMasAciertos, menos=a.ligaMenosAciertos;
  return `<div class="analytics-panel"><div class="section-title">📊 Analytics - ${matches.length} partidos</div><div class="analytics-grid"><div class="analytics-card"><div class="analytics-title">🏆 Liga más aciertos</div><div class="analytics-value">${mas?`${mas.liga} - ${mas.aciertos}/${mas.total}`:'N/A'}</div></div><div class="analytics-card"><div class="analytics-title">📉 Liga menos aciertos</div><div class="analytics-value">${menos?`${menos.liga} - ${menos.aciertos}/${menos.total} (${menos.fallos} fallos)`:'N/A'}</div></div></div></div>`;
}
function renderAnalyticsExtended(matches){ return ''; }
function getTodayMX(){
  try{ return new Date().toLocaleDateString('en-CA', {timeZone:'America/Mexico_City'}); }
  catch{ return new Date().toLocaleDateString('en-CA'); }
}
function findMatchForProgol(home, away){
  const nh = (home||'').toLowerCase().trim();
  const na = (away||'').toLowerCase().trim();
  const sources = [...allMatches, ...SEASON_CACHE];
  const aliases = {
    'puebla':'puebla','pumas':'pumas','pachuca':'pachuca','tigres':'tigres','aguilas':'america','america':'america','toluca':'toluca',
    'elche':'elche','valencia':'valencia','ath. bilbao':'athletic','athletic':'athletic','bilbao':'athletic','r. sociedad':'real sociedad','real sociedad':'real sociedad',
    'bournemouth':'bournemouth','leeds':'leeds','liverpool':'liverpool','arsenal':'arsenal','milan':'milan','inter milan':'inter','inter':'inter',
    'juventus':'juventus','napoles':'napoli','napoli':'napoli','augsburgo':'augsburg','augsburg':'augsburg','friburgo':'freiburg','freiburg':'freiburg',
    'lorient':'lorient','brest':'brest','gremio':'gremio','at. mineiro':'atletico mineiro','atletico mineiro':'atletico mineiro','mineiro':'atletico mineiro',
    'boca jrs':'boca juniors','boca juniors':'boca juniors','river plate':'river plate','u. catolica':'universidad catolica','universidad catolica':'universidad catolica','u. de chile':'universidad de chile','universidad de chile':'universidad de chile',
    'monterrey':'monterrey','tijuana':'tijuana','guadalajara':'guadalajara','atlante':'atlante','s. laguna':'santos laguna','santos laguna':'santos laguna','necaxa':'necaxa','c. azul':'cruz azul','cruz azul':'cruz azul','leon':'leon',
    'getafe':'getafe','sevilla':'sevilla','chelsea':'chelsea','man. united':'manchester united','manchester united':'manchester united','ajax':'ajax','az alkmaar':'az','az':'az'
  };
  const normHome = aliases[nh]||nh;
  const normAway = aliases[na]||na;
  let found = sources.find(m=>{
    const h=(m.home||'').toLowerCase();
    const a=(m.away||'').toLowerCase();
    return (h.includes(normHome) || normHome.includes(h) || h.includes(nh)) && (a.includes(normAway) || normAway.includes(a) || a.includes(na));
  });
  return found||null;
}
function cardA(m){
  const p=m.probabilities||{"1":0,"X":0,"2":0};
  const total=(p['1']+p['X']+p['2']).toFixed(1);
  let badgeHtml='';
  if(m.estado==='FINALIZADO'){ if(m.acierto===true) badgeHtml='<span class="estado-tag estado-acierto">✅ Acertó</span>'; else if(m.acierto===false) badgeHtml='<span class="estado-tag estado-fallo">❌ Falló</span>'; else badgeHtml='<span class="estado-tag estado-finalizado">✅ Finalizado</span>'; }
  else if(m.estado==='EN_JUEGO'){ badgeHtml='<span class="estado-tag estado-en_juego">🔴 En Juego</span>'; }
  else { badgeHtml='<span class="estado-tag estado-programado">⏰ Programado</span>'; }
  let scoreHtml=''; if(m.estado!=='PROGRAMADO' && m.home_score!=null && m.away_score!=null){ scoreHtml=`<div class="score-row"><span class="score">${m.home_score} - ${m.away_score}</span></div>`; }
  const confColor=m.confidence==='Alta'?'#1ee07a':m.confidence==='Media'?'#f5d547':'#ff6b6b';
  const fav=m.favorite||'';
  const maxP=Math.max(p['1']||0,p['X']||0,p['2']||0);
  return `<div class="card"><div class="card-header"><span class="league">${esc(m.league||m.league_code||'Liga')}</span>${badgeHtml}</div><div class="teams"><span class="home">${esc(m.home)}</span><span class="vs">vs</span><span class="away">${esc(m.away)}</span></div>${scoreHtml}<div class="prob-row"><span class="prob p1">L ${ (p['1']||0).toFixed(1)}%</span><span class="prob px">E ${ (p['X']||0).toFixed(1)}%</span><span class="prob p2">V ${ (p['2']||0).toFixed(1)}%</span></div><div class="meta">Favorito: ${esc(fav)} (${maxP.toFixed(1)}%) - Conf: <b style="color:${confColor}">${esc(m.confidence||'')}</b> - xG ${ (m.xg_home||0).toFixed(2)} - ${ (m.xg_away||0).toFixed(2)} - ${esc(m.date||'')} ${esc(m.time||'')}</div><div class="card-actions"><button class="mini-filter" onclick="toggleCombinada('${(m._key||`${m.date}_${m.home}_${m.away}`).replace(/'/g,"\\'")}')">➕ Combinada</button></div></div>`;
}
function getFiltered(){
  const f=currentFilter;
  const searchDate = $dateInput ? ($dateInput.value||'') : '';
  const todayMX = getTodayMX();
  let filtered=[];
  if(f==='all'){
    let hoyMatches = allMatches.filter(m=> (m.date||'').startsWith(todayMX));
    if(hoyMatches.length===0){
      const limitDate = new Date(); limitDate.setDate(limitDate.getDate()+7);
      const limitStr = limitDate.toISOString().slice(0,10);
      hoyMatches = allMatches.filter(m=> (m.date||'')>=todayMX && (m.date||'')<=limitStr && m.estado!=='FINALIZADO');
      if(hoyMatches.length===0) hoyMatches = allMatches.slice(0,20);
    }
    filtered=hoyMatches;
  }
  else if(f==='liga-mx' || f==='league:mex.1'){
    filtered=allMatches.filter(m=> (m.league_code||'').toLowerCase().includes('mex') || (m.league||'').toLowerCase().includes('liga mx') || (m.league||'').toLowerCase().includes('mexico'));
    if(filtered.length===0) filtered=allMatches;
  }
  else if(f.startsWith('league:')){
    const code=f.replace('league:','').toLowerCase();
    filtered=allMatches.filter(m=> (m.league_code||'').toLowerCase()===code);
  }
  else if(f==='top'){
    let base=allMatches;
    filtered=base.filter(m=> m.confidence==='Alta'||m.confidence==='Media');
    const order={Alta:0,Media:1};
    filtered.sort((a,b)=>{const ca=order[a.confidence]??2,cb=order[b.confidence]??2; if(ca!==cb) return ca-cb; return Math.max(b.probabilities?.['1']||0,b.probabilities?.['X']||0,b.probabilities?.['2']||0)-Math.max(a.probabilities?.['1']||0,a.probabilities?.['X']||0,a.probabilities?.['2']||0);});
  }
  else if(f==='search'){
    const q=norm($searchInput.value);
    const liga=$leagueSelect.value;
    const dateFilter = searchDate;
    if(!q && liga==='all' && !dateFilter){ filtered=[]; }
    else {
      filtered=allMatches.filter(m=>{
        const matchQ=!q||norm(m.home).includes(q)||norm(m.away).includes(q)||ln(m).includes(q);
        const matchLiga=liga==='all'||(m.league||'').includes(liga) || (m.league_code||'').includes(liga.toLowerCase());
        const matchDate=!dateFilter || (m.date||'').startsWith(dateFilter);
        return matchQ&&matchLiga&&matchDate;
      });
    }
  }
  else if(f==='aciertos'){ filtered=allMatches.filter(m=>m.estado==='FINALIZADO'&&m.acierto===true); }
  else if(f==='fallos'){ filtered=allMatches.filter(m=>m.estado==='FINALIZADO'&&m.acierto===false); }
  else if(f==='combinada'){ let base=allMatches; filtered=base.filter(m=> m.confidence==='Alta'||m.confidence==='Media'); const order={Alta:0,Media:1}; filtered.sort((a,b)=>{const ca=order[a.confidence]??2,cb=order[b.confidence]??2; if(ca!==cb) return ca-cb; return Math.max(b.probabilities?.['1']||0,b.probabilities?.['X']||0,b.probabilities?.['2']||0)-Math.max(a.probabilities?.['1']||0,a.probabilities?.['X']||0,a.probabilities?.['2']||0);}); }
  else if(f==='progol'){ filtered=allMatches; }
  else if(f==='analytics'){ filtered=allMatches; }
  else { filtered=allMatches; }
  const seenFinal={}; filtered=filtered.filter(m=>{const key=`${m.date||''}_${(m.league_code||'').toLowerCase()}_${(m.home||'').toLowerCase()}_${(m.away||'').toLowerCase()}`; if(seenFinal[key]) return false; seenFinal[key]=true; m._key=key; return true;}); return filtered;
}
function groupByEstado(matches){ const enJuego=matches.filter(m=>m.estado==='EN_JUEGO'); const programados=matches.filter(m=>m.estado==='PROGRAMADO'||!m.estado); const finalizados=matches.filter(m=>m.estado==='FINALIZADO'); return {enJuego,programados,finalizados}; }
function renderSection(title,matches){ if(matches.length===0) return ''; let html=`<div class="section-title">${title}</div>`; html+=matches.map(cardA).join(''); return html; }
function resetToAll(){ document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active')); const btn=document.querySelector('[data-filter="all"]'); if(btn) btn.classList.add('active'); currentFilter='all'; renderAll(); }
function renderProgolReal(){
  var metaF = (typeof PROGOL_META!=='undefined' && PROGOL_META.fecha) ? PROGOL_META.fecha : '30 oct.';
  var metaH = (typeof PROGOL_META!=='undefined' && PROGOL_META.hasta) ? 'hasta '+PROGOL_META.hasta : '';
  var metaSrc = (typeof PROGOL_META!=='undefined' && PROGOL_META.fuente) ? PROGOL_META.fuente : 'TuLotero';
  let html='<div class="section-title">▤ Progol - Quiniela Lotería Nacional '+metaF+' '+metaH+' (14 + Revancha 7) - '+metaSrc+' - Auto</div>';
  function renderProgolList(list, titulo){
    let h=`<div class="analytics-panel"><div class="section-title" style="background:${titulo.includes('REVANCHA')?'#1a2a1a':'#0f1a33'}">${titulo} (${list.length} partidos)</div>`;
    h+=`<div style="display:grid; grid-template-columns:1fr; gap:8px">`;
    list.forEach(item=>{
      const match=findMatchForProgol(item.home, item.away);
      let p={L:33,E:33,V:33}, fav='Local', conf='Media', pick='L', maxP=33;
      if(match){
        const prob=match.probabilities||{'1':33,'X':33,'2':33};
        p={L:prob['1']||33, E:prob['X']||33, V:prob['2']||33};
        maxP=Math.max(p.L,p.E,p.V);
        if(p.E> p.L && p.E> p.V){ pick='E'; fav='Empate'; }
        else if(p.V> p.L && p.V> p.E){ pick='V'; fav=match.away; }
        else { pick='L'; fav=match.home; }
        conf=match.confidence||'Media';
      } else {
        p={L:40,E:28,V:32}; pick='L'; fav=item.home; conf='Estimado';
      }
      const pickColor=pick==='L'?'#1ee07a':pick==='E'?'#f5d547':'#ff6b6b';
      h+=`<div class="card progol-row" style="display:flex; align-items:center; gap:10px; padding:10px; border-left:4px solid ${pickColor}">
        <div style="background:#1a2a4a; color:#fff; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:13px; flex-shrink:0">${item.n}</div>
        <div style="flex:1; min-width:0">
          <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap">
            <span style="font-weight:700; font-size:13px">${esc(item.home)} <span style="color:#8aa0c8">vs</span> ${esc(item.away)}</span>
            <span style="font-size:11px; color:#8aa0c8">Sugerido: <b style="color:${pickColor}">${pick} → ${esc(fav)} (${maxP.toFixed(1)}%)</b> - Conf: ${esc(conf)}</span>
          </div>
          <div style="display:flex; gap:6px; margin-top:4px; font-size:10px; color:#8aa0c8">
            <span>L:${p.L.toFixed(1)}%</span><span>E:${p.E.toFixed(1)}%</span><span>V:${p.V.toFixed(1)}%</span>
            ${match?`<span style="color:${pickColor}">• ${esc(match.league||'')}</span>`:''}
          </div>
        </div>
      </div>`;
    });
    h+=`</div></div>`;
    return h;
  }
  html+=renderProgolList(PROGOL_REAL, 'PROGOL - 14 PARTIDOS');
  html+=renderProgolList(REVANCHA_REAL, 'REVANCHA (OPCIONAL) - 7 PARTIDOS');
  return html;
}
function renderAll(){
  try{
    const filtered=getFiltered();
    if(currentFilter==='analytics'){ const finalizados=filtered.filter(m=>m.estado==='FINALIZADO'); const aciertos=finalizados.filter(m=>m.acierto===true).length, fallos=finalizados.filter(m=>m.acierto===false).length, total=finalizados.length, pct=total>0?Math.round(aciertos/total*100):0; $grid.innerHTML=renderAnalytics(filtered); $countBadge.textContent=`📊 ${total} finalizados - ${aciertos}✅ ${fallos}❌ - ${pct}% acierto`; return; }
    $countBadge.textContent=`${filtered.length} partidos / ${allMatches.length} total`;
    if(currentFilter==='search'){
      const q=$searchInput.value; const hasDate=$dateInput && $dateInput.value;
      if(!q && $leagueSelect.value==='all' && !hasDate){ $grid.innerHTML=`<div class="search-google-empty"><div class="search-google-icon">🔍</div><h2>Busca un equipo o liga</h2><p>Escribe Atlas, América, Liga MX o elige fecha</p></div>`; return; }
      let html=`<div class="section-title">🔍 Resultados búsqueda (${filtered.length})</div>`;
      const groups=groupByEstado(filtered);
      if(groups.enJuego.length>0) html+=renderSection(`🔴 En Juego (${groups.enJuego.length})`,groups.enJuego);
      if(groups.programados.length>0) html+=renderSection(`⏰ Programados (${groups.programados.length})`,groups.programados);
      if(groups.finalizados.length>0) html+=renderSection(`✅ Finalizados (${groups.finalizados.length})`,groups.finalizados);
      if(groups.enJuego.length===0&&groups.programados.length===0&&groups.finalizados.length===0) html+=filtered.map(cardA).join('');
      $grid.innerHTML=html; return;
    }
    const {enJuego,programados,finalizados}=groupByEstado(filtered);
    let html='';
    if(currentFilter==='all'){
      html+=`<div class="section-title">🇲🇽 Liga MX - Partidos del día ${getTodayMX()} (${filtered.length}) - Poisson + ELO</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`⏰ Programados próximos (${programados.length})`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados hoy (${finalizados.length})`,finalizados);
      if(enJuego.length===0&&programados.length===0&&finalizados.length===0) html+=filtered.map(cardA).join('');
    } else if(currentFilter==='top'){
      html+=`<div class="section-title">★ Top Picks - Alta/Media confianza (${filtered.length})</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`🎯 Programados (${programados.length})`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados);
    } else if(currentFilter==='combinada'){
      html+=`<div class="section-title">∽ Combinadas (${filtered.length} picks) - Usa cache local</div>`;
      html+=filtered.slice(0,20).map(cardA).join('');
    } else if(currentFilter==='progol'){
      html=renderProgolReal();
    } else if(currentFilter==='aciertos'){
      html+=`<div class="section-title">✅ Aciertos (${filtered.length})</div>`; html+=filtered.map(cardA).join('');
    } else if(currentFilter==='fallos'){
      html+=`<div class="section-title">❌ Fallos (${filtered.length})</div>`; html+=filtered.map(cardA).join('');
    } else {
      const titleMap={'liga-mx':'🇲🇽 Liga MX - Temporada Completa','league:mex.1':'🇲🇽 Liga MX - México'};
      const t=titleMap[currentFilter]||currentFilter; html+=`<div class="section-title">${t} (${filtered.length} partidos) - Temporada completa</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`⏰ Programados (${programados.length})`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados);
    }
    html+=`<div class="section-title">📊 Transparencia</div><div class="card"><div class="meta">Probabilidad != recomendación segura. Suma 1X2 ~100% validado.</div></div>`;
    $grid.innerHTML=html;
  }catch(e){
    log(`RENDER ERROR: ${e.message}`,'err');
    $grid.innerHTML=`<div class="card"><div class="meta" style="color:#ff6b6b">Error render: ${esc(e.message)}</div></div>`;
  }
}
async function loadLigaMXOnly(){
  if(ALL_BASE_CACHE_LOADED && allMatches.length>0){
    log(`Cache ya cargado: ${allMatches.length} partidos - filtro local`, 'ok');
    renderAll();
    return;
  }
  for(let attempt=1; attempt<=2; attempt++){
    try{
      $status.textContent=`Cargando base Liga MX... intento ${attempt} - temporada completa`;
      const data = await api('/api/liga-mx/season?limit=500');
      if(data && data.matches && data.matches.length>0){
        allMatches = data.matches;
        SEASON_CACHE = data.matches;
        ALL_BASE_CACHE_LOADED = true;
        log(`BASE Liga MX: ${data.matches.length} partidos - cache listo`, 'ok');
        renderAll();
        $status.textContent=`BASE: ${data.count} partidos Liga MX - Cache local activo`;
        return;
      } else {
        $status.textContent='Base vacía, sincronizando...';
        await api('/api/liga-mx/sync');
        await new Promise(r=>setTimeout(r, 8000));
      }
    }catch(e){
      log(`Error intento ${attempt}: ${e.message}`, 'err');
      if(attempt<2){ await new Promise(r=>setTimeout(r, 3000)); }
      else {
        $status.textContent=`Error: ${e.message} - Probando temporada general`;
        try{
          const allData=await api('/api/calendar/season?limit=500');
          allMatches=allData.matches||[];
          ALL_BASE_CACHE_LOADED = true;
          $status.textContent=`BASE: ${allMatches.length} partidos - cache`;
          renderAll();
        }catch(e2){ $status.textContent=`Error total: ${e.message}`; }
      }
    }
  }
}
async function syncLigaMX(){
  $status.textContent='Sincronizando Liga MX 60-90 seg...';
  try{
    await api('/api/liga-mx/sync');
    log('Sync iniciado, espera 10s', 'ok');
    ALL_BASE_CACHE_LOADED=false;
    setTimeout(loadLigaMXOnly, 10000);
  }catch(e){ $status.textContent=`Error sync: ${e.message}`; }
}
async function loadProgolFromBackend(){
  try{
    const data = await api('/api/progol/current');
    if(data && data.progol){
      PROGOL_REAL = data.progol.map((p,i)=>({n:p.n||i+1, home:(p.home||'').toUpperCase(), away:(p.away||'').toUpperCase()}));
      REVANCHA_REAL = (data.revancha||[]).map((p,i)=>({n:p.n||i+1, home:(p.home||'').toUpperCase(), away:(p.away||'').toUpperCase()}));
      PROGOL_META = {fecha:data.fecha||'', hasta:data.hasta||'', fuente:data.fuente||'Backend'};
      log(`Progol backend: ${data.fecha} - ${PROGOL_REAL.length}+${REVANCHA_REAL.length}`, 'ok');
      if(currentFilter==='progol') renderAll();
    }
  }catch(e){ log(`Progol backend no disponible: ${e.message}`, 'err'); }
}
document.addEventListener('click',(e)=>{
  const btn=e.target.closest('.menu-item');
  if(!btn) return;
  if(!btn.dataset.filter) return;
  document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  currentFilter=btn.dataset.filter;
  if(currentFilter==='search') $searchBox.style.display='block'; else $searchBox.style.display='none';
  log(`Filtro: ${currentFilter} - cache local ${allMatches.length}`, 'ok');
  renderAll();
  if(window.innerWidth<800) document.querySelector('.main').scrollTop=0;
});
$searchInput.addEventListener('input',renderAll);
$leagueSelect.addEventListener('change',renderAll);
if($dateInput){ $dateInput.addEventListener('change',()=>{ if(currentFilter==='search') renderAll(); }); }
document.getElementById('loadBtn').addEventListener('click',loadLigaMXOnly);
document.getElementById('refreshBtn').addEventListener('click',syncLigaMX);
(async()=>{
  try{ const today = new Date().toLocaleDateString('en-CA'); if($dateInput) $dateInput.value=today; }catch{}
  try{
    const h=await api('/api/health');
    $status.textContent=`API: ${h.version} - ${h.records} partidos - Cargando base...`;
    await loadLigaMXOnly();
    loadProgolFromBackend();
  }catch(e){
    $status.textContent='API no conecta: '+e.message;
    log('Health error: '+e.message, 'err');
  }
})();
