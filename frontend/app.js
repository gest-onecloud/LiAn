const BACKEND = "https://lian-backend.onrender.com";
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
let CACHE_VERSION = 'V115-2863-FORCE'; // Force cache bust when backend changes

var PROGOL_REAL = [
  {n:1, home:'PUEBLA', away:'PUMAS'},{n:2, home:'PACHUCA', away:'TIGRES'},{n:3, home:'AGUILAS', away:'TOLUCA'},{n:4, home:'ELCHE', away:'VALENCIA'},{n:5, home:'ATH. BILBAO', away:'R. SOCIEDAD'},{n:6, home:'BOURNEMOUTH', away:'LEEDS'},{n:7, home:'LIVERPOOL', away:'ARSENAL'},{n:8, home:'MILAN', away:'INTER MILAN'},{n:9, home:'JUVENTUS', away:'NAPOLES'},{n:10, home:'AUGSBURGO', away:'FRIBURGO'},{n:11, home:'LORIENT', away:'BREST'},{n:12, home:'GREMIO', away:'AT. MINEIRO'},{n:13, home:'BOCA JRS', away:'RIVER PLATE'},{n:14, home:'U. CATOLICA', away:'U. DE CHILE'}
];
var REVANCHA_REAL = [
  {n:1, home:'MONTERREY', away:'TIJUANA'},{n:2, home:'GUADALAJARA', away:'ATLANTE'},{n:3, home:'S. LAGUNA', away:'NECAXA'},{n:4, home:'C. AZUL', away:'LEON'},{n:5, home:'GETAFE', away:'SEVILLA'},{n:6, home:'CHELSEA', away:'MAN. UNITED'},{n:7, home:'AJAX', away:'AZ ALKMAAR'}
];
var PROGOL_META = {fecha:'2026-10-30', hasta:'20:55', fuente:'TuLotero'};

function log(m,c=''){const d=document.createElement('div');d.textContent='['+new Date().toLocaleTimeString()+'] '+m;if(c)d.className=c;if($log)$log.prepend(d);}
function esc(s){if(!s)return '';const div=document.createElement('div');div.textContent=s;return div.innerHTML;}
function norm(s){return (s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');}
function ln(m){return norm((m.league||'')+' '+(m.league_code||''));}
async function api(path){const url=BACKEND+path;log('GET '+url);try{const r=await fetch(url,{mode:'cors'});if(!r.ok)throw new Error('HTTP '+r.status);const j=await r.json();log('OK '+path+' -> '+(j.count||j.records||'ok'),'ok');return j;}catch(e){log('ERROR '+path+': '+e.message,'err');throw e;}}
function getTodayMX(){try{return new Date().toLocaleDateString('en-CA',{timeZone:'America/Mexico_City'});}catch{return new Date().toLocaleDateString('en-CA');}}

function cardA(m){
  const p=m.probabilities||{'1':0,'X':0,'2':0};
  const total=((p['1']||0)+(p['X']||0)+(p['2']||0)).toFixed(1);
  let badge='';
  if(m.estado==='FINALIZADO'){if(m.acierto===true)badge='<span class="badge badge-acierto">✅ Acertó</span>';else if(m.acierto===false)badge='<span class="badge badge-fallo">❌ Falló</span>';else badge='<span class="badge badge-final">Finalizado</span>';}
  else if(m.estado==='EN_JUEGO')badge='<span class="badge badge-vivo">🔴 En Juego</span>';
  else badge='<span class="badge badge-prog">⏰ Programado</span>';
  const fecha=(m.date||'').slice(0,10);const hora=(m.time||'').slice(0,5);const liga=(m.league||m.league_code||'Liga').toUpperCase();
  let scoreBox='';if(m.home_score!=null&&m.away_score!=null)scoreBox='<div class="score-box">'+m.home_score+' - '+m.away_score+'</div>';else scoreBox='<div class="score-box score-vs">VS</div>';
  const fav=m.favorite||'';const conf=m.confidence||'';let dot='';if(conf==='Alta')dot='<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#1ee07a;margin-left:4px"></span>';else if(conf==='Media')dot='<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#f5d547;margin-left:4px"></span>';else if(conf==='Limitada')dot='<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#ff6b6b;margin-left:4px"></span>';
  return '<div class="card-compact"><div class="card-top"><span class="card-league">'+esc(liga)+' • '+esc(hora)+' • '+esc(fecha)+'</span>'+badge+'</div><div class="card-teams"><span>'+esc(m.home)+'</span><span class="vs-small"> vs </span><span>'+esc(m.away)+'</span></div>'+scoreBox+'<div class="card-probs"><span>L: '+(p['1']||0).toFixed(1)+'%</span><span>E: '+(p['X']||0).toFixed(1)+'%</span><span>V: '+(p['2']||0).toFixed(1)+'%</span><span class="sum">Σ '+total+'%</span></div><div class="card-bottom"><span class="fav">★ '+esc(fav)+'</span><span class="conf">Conf: '+esc(conf)+dot+'</span></div></div>';
}

function getFiltered(){
  const f=currentFilter;const todayMX=getTodayMX();let filtered=[];
  if(f==='all'){
    let hoy=allMatches.filter(function(m){return (m.date||'').startsWith(todayMX);});
    if(hoy.length===0){
      const limit=new Date();limit.setDate(limit.getDate()+7);
      const limitStr=limit.toISOString().slice(0,10);
      hoy=allMatches.filter(function(m){const d=(m.date||'').slice(0,10);return d>=todayMX&&d<=limitStr;});
    }
    if(hoy.length===0)hoy=allMatches.slice(0,24);
    filtered=hoy;
  } else if(f==='liga-mx'||f==='league:mex.1'){
    filtered=allMatches.filter(function(m){const lc=(m.league_code||'').toLowerCase();const l=(m.league||'').toLowerCase();return lc.includes('mex')||l.includes('liga mx')||l.includes('mexico')||l.includes('méxico');});
    if(filtered.length===0)filtered=allMatches.slice(0,30);
  } else if(f.indexOf('league:')===0){
    const code=f.replace('league:','').toLowerCase();
    filtered=allMatches.filter(function(m){return (m.league_code||'').toLowerCase()===code||(m.league||'').toLowerCase().indexOf(code)>=0;});
    if(filtered.length===0)filtered=allMatches.slice(0,30);
  } else if(f==='top'){
    filtered=allMatches.filter(function(m){return m.confidence==='Alta'||m.confidence==='Media';});
    filtered.sort(function(a,b){const o={Alta:0,Media:1};const ca=o[a.confidence]!=null?o[a.confidence]:2;const cb=o[b.confidence]!=null?o[b.confidence]:2;if(ca!==cb)return ca-cb;const pa=Math.max((a.probabilities&&a.probabilities['1']||0),(a.probabilities&&a.probabilities['X']||0),(a.probabilities&&a.probabilities['2']||0));const pb=Math.max((b.probabilities&&b.probabilities['1']||0),(b.probabilities&&b.probabilities['X']||0),(b.probabilities&&b.probabilities['2']||0));return pb-pa;});
  } else if(f==='search'){
    const qInput=document.getElementById('topSearchInput');
    const topQ=qInput?norm(qInput.value):'';const q2=norm(($searchInput.value||''));const finalQ=topQ||q2;
    const ligaEl=document.getElementById('topLeagueSelect');const liga=(ligaEl?ligaEl.value:$leagueSelect.value||'all').toLowerCase();
    const fromEl=document.getElementById('topDateFrom');const toEl=document.getElementById('topDateTo');
    const fromD=fromEl?fromEl.value:'';const toD=toEl?toEl.value:'';
    if(!finalQ&&liga==='all'&&!fromD&&!toD){filtered=[];}
    else{
      filtered=allMatches.filter(function(m){
        const matchQ=!finalQ||norm(m.home).indexOf(finalQ)>=0||norm(m.away).indexOf(finalQ)>=0||ln(m).indexOf(finalQ)>=0;
        let matchLiga=true;if(liga!=='all'){const le=(m.league||'').toLowerCase();const lc=(m.league_code||'').toLowerCase();matchLiga=le.indexOf(liga)>=0||lc.indexOf(liga)>=0||ln(m).indexOf(liga)>=0;}
        let matchDate=true;if(fromD||toD){const d=(m.date||'').slice(0,10);if(fromD&&toD)matchDate=d>=fromD&&d<=toD;else if(fromD)matchDate=d>=fromD;else if(toD)matchDate=d<=toD;}
        return matchQ&&matchLiga&&matchDate;
      });
      filtered.sort(function(a,b){return (b.date||'').localeCompare(a.date||'');});
    }
  } else if(f==='aciertos'){filtered=allMatches.filter(function(m){return m.estado==='FINALIZADO'&&m.acierto===true;});}
  else if(f==='fallos'){filtered=allMatches.filter(function(m){return m.estado==='FINALIZADO'&&m.acierto===false;});}
  else if(f==='combinada'){filtered=allMatches.filter(function(m){return m.confidence==='Alta'||m.confidence==='Media';}).slice(0,20);}
  else if(f==='progol'){filtered=allMatches;}
  else if(f==='analytics'){filtered=allMatches;}
  else {filtered=allMatches;}
  const seen={};filtered=filtered.filter(function(m){const k=(m.date||'')+'_'+((m.league_code||'').toLowerCase())+'_'+((m.home||'').toLowerCase())+'_'+((m.away||'').toLowerCase());if(seen[k])return false;seen[k]=true;m._key=k;return true;});
  return filtered;
}
function groupByEstado(matches){const enJuego=matches.filter(function(m){return m.estado==='EN_JUEGO';});const programados=matches.filter(function(m){return m.estado==='PROGRAMADO'||!m.estado;});const finalizados=matches.filter(function(m){return m.estado==='FINALIZADO';});return {enJuego:enJuego,programados:programados,finalizados:finalizados};}
function renderSection(title,matches){if(matches.length===0)return '';return '<div class="section-title">'+title+'</div><div class="cards-grid">'+matches.map(cardA).join('')+'</div>';}
function findMatchForProgol(home,away){const nh=(home||'').toLowerCase();const na=(away||'').toLowerCase();const src=allMatches.concat(SEASON_CACHE);for(let i=0;i<src.length;i++){const m=src[i];const h=(m.home||'').toLowerCase();const a=(m.away||'').toLowerCase();if((h.indexOf(nh)>=0||nh.indexOf(h)>=0)&&(a.indexOf(na)>=0||na.indexOf(a)>=0))return m;}return null;}
function renderProgolReal(){
  let html='<div class="section-title">▤ Progol - '+PROGOL_META.fecha+' hasta '+PROGOL_META.hasta+' - '+PROGOL_META.fuente+'</div>';
  function listProgol(list,titulo){
    let h='<div class="analytics-panel"><div class="section-title" style="background:'+(titulo.indexOf('REVANCHA')>=0?'#1a2a1a':'#0f1a33')+'">'+titulo+' ('+list.length+')</div><div style="display:grid;gap:8px">';
    for(let i=0;i<list.length;i++){const it=list[i];const m=findMatchForProgol(it.home,it.away);let p={L:33,E:33,V:33};let fav=it.home;let conf='Media';let pick='L';let maxP=33;if(m){const pr=m.probabilities||{'1':33,'X':33,'2':33};p={L:pr['1']||33,E:pr['X']||33,V:pr['2']||33};maxP=Math.max(p.L,p.E,p.V);if(p.E>p.L&&p.E>p.V){pick='E';fav='Empate';}else if(p.V>p.L&&p.V>p.E){pick='V';fav=m.away;}else {pick='L';fav=m.home;}conf=m.confidence||'Media';}const col=pick==='L'?'#1ee07a':pick==='E'?'#f5d547':'#ff6b6b';h+='<div class="card progol-row" style="display:flex;gap:10px;padding:10px;border-left:4px solid '+col+'"><div style="background:#1a2a4a;color:#fff;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:12px">'+it.n+'</div><div style="flex:1"><div style="display:flex;justify-content:space-between;gap:8px"><span style="font-weight:700;font-size:13px">'+esc(it.home)+' vs '+esc(it.away)+'</span><span style="font-size:11px;color:'+col+'"><b>'+pick+' → '+esc(fav)+' ('+maxP.toFixed(1)+'%)</b> - '+esc(conf)+'</span></div><div style="font-size:10px;color:#8aa0c8;margin-top:2px">L:'+p.L.toFixed(1)+'% E:'+p.E.toFixed(1)+'% V:'+p.V.toFixed(1)+'% '+(m?'• '+esc(m.league||''):'')+'</div></div></div>';}
    h+='</div></div>';return h;
  }
  html+=listProgol(PROGOL_REAL,'PROGOL - 14 PARTIDOS');html+=listProgol(REVANCHA_REAL,'REVANCHA - 7 PARTIDOS');return html;
}

function updateSearchResultsOnly(){
  try{
    const filtered=getFiltered();
    const qEl=document.getElementById('topSearchInput');const q=(qEl?qEl.value:'').trim();
    const fromEl=document.getElementById('topDateFrom');const toEl=document.getElementById('topDateTo');
    const ligaEl=document.getElementById('topLeagueSelect');const liga=ligaEl?ligaEl.value:'all';
    const fromV=fromEl?fromEl.value:'';const toV=toEl?toEl.value:'';
    if($countBadge)$countBadge.textContent=filtered.length+' partidos / '+allMatches.length+' total';
    const badge=document.getElementById('searchCountBadge');if(badge)badge.textContent=filtered.length+' / '+allMatches.length;
    const container=document.getElementById('searchResults');if(!container){renderAll();return;}
    let html='';
    if(!q&&liga==='all'&&!fromV&&!toV){
      html='<div class="search-empty" style="text-align:center;padding:50px 20px;border:1px dashed #1e3a6a;border-radius:12px;background:#0a1228"><div style="font-size:48px">🔍</div><h2 style="color:#e6edf3;margin:12px 0">Busca un equipo o liga</h2><p style="color:#8aa0c8">Escribe "Atlas", "América", "Liga MX" o elige liga y rango<br>Tienes '+allMatches.length+' partidos en cache temporada completa</p></div>';
      container.innerHTML=html;return;
    }
    const rangeTxt=(fromV||toV)?' del '+(fromV||'inicio')+' al '+(toV||'hoy'):'';html+='<div class="section-title">🔍 "'+esc(q)+'" '+(liga!=='all'?esc(liga):'')+rangeTxt+' ('+filtered.length+')</div>';
    const g=groupByEstado(filtered);if(g.enJuego.length>0)html+=renderSection('🔴 En Juego ('+g.enJuego.length+')',g.enJuego);if(g.programados.length>0)html+=renderSection('⏰ Programados ('+g.programados.length+')',g.programados);if(g.finalizados.length>0)html+=renderSection('✅ Finalizados ('+g.finalizados.length+')',g.finalizados);if(filtered.length===0)html+='<div class="card"><div class="meta">No hay partidos para "'+esc(q)+'" '+esc(liga)+' '+rangeTxt+'. Prueba sin fechas.</div></div>';container.innerHTML=html;
  }catch(e){console.error(e);log('Search render err: '+e.message,'err');}
}

function renderAll(){
  try{
    const filtered=getFiltered();
    if($countBadge)$countBadge.textContent=filtered.length+' partidos / '+allMatches.length+' total';
    if(currentFilter==='search'){$grid.style.display='block'; $grid.style.width='100%';
      const exists=document.getElementById('searchBarContainer');
      if(!exists){
        const q=($searchInput.value||'').trim();const ligaVal=$leagueSelect.value||'all';
        let html='<div id="searchFilterWrapper" class="search-filter-wrapper" style="width:100%;display:block;margin-bottom:20px"><div id="searchBarContainer" class="card search-filter-card"><input id="topSearchInput" type="text" placeholder="Buscar: América, Atlas, Pumas, Liga MX..." value="'+esc(q)+'" class="search-main-input"><div class="search-filters-grid"><select id="topLeagueSelect" class="search-select"><option value="all" '+(ligaVal==='all'?'selected':'')+'>Todas las ligas</option><option value="mex" '+(ligaVal.toLowerCase().indexOf('mex')>=0?'selected':'')+'>Liga MX</option><option value="arg" '+(ligaVal.toLowerCase().indexOf('arg')>=0?'selected':'')+'>Argentina</option><option value="bra" '+(ligaVal.toLowerCase().indexOf('bra')>=0?'selected':'')+'>Brasil</option><option value="eng" '+(ligaVal.toLowerCase().indexOf('eng')>=0?'selected':'')+'>Premier</option><option value="esp" '+(ligaVal.toLowerCase().indexOf('esp')>=0?'selected':'')+'>España</option><option value="ita" '+(ligaVal.toLowerCase().indexOf('ita')>=0?'selected':'')+'>Italia</option></select><input id="topDateFrom" type="date" class="search-date" title="Desde"><input id="topDateTo" type="date" class="search-date" title="Hasta"></div><div class="search-actions"><button id="topSearchBtn" class="btn-search">Buscar</button><button id="topClearBtn" class="btn-clear">Limpiar</button><span id="searchCountBadge" class="search-badge"></span></div><div class="search-tip">Tip: America = toda su temporada. Base: '+allMatches.length+' partidos</div></div></div></div><div id="searchResults" class="search-results-full" style="width:100%;display:block;clear:both;margin-top:20px"></div>';
        $grid.innerHTML=html;
        setTimeout(function(){
          const topS=document.getElementById('topSearchInput');const topFrom=document.getElementById('topDateFrom');const topTo=document.getElementById('topDateTo');const topL=document.getElementById('topLeagueSelect');
          const upd=function(){if(topS)$searchInput.value=topS.value;if(topL)$leagueSelect.value=topL.value;updateSearchResultsOnly();};
          if(topS){topS.addEventListener('input',upd);topS.focus();}
          if(topFrom)topFrom.addEventListener('change',upd);if(topTo)topTo.addEventListener('change',upd);if(topL)topL.addEventListener('change',upd);
          const btn=document.getElementById('topSearchBtn');if(btn)btn.addEventListener('click',upd);
          const clr=document.getElementById('topClearBtn');if(clr)clr.addEventListener('click',function(){if(topS)topS.value='';if(topFrom)topFrom.value='';if(topTo)topTo.value='';if(topL)topL.value='all';$searchInput.value='';$leagueSelect.value='all';updateSearchResultsOnly();if(topS)topS.focus();});
          updateSearchResultsOnly();
        },0);
        return;
      } else {updateSearchResultsOnly();return;}
    }
    if(currentFilter==='analytics'){$grid.style.display=''; $grid.innerHTML='<div class="analytics-panel"><div class="section-title">📊 Estadísticas - '+allMatches.length+' partidos</div><div class="card">Base: '+allMatches.length+' partidos temporada</div></div>';return;}
    $grid.style.display=''; const g=groupByEstado(filtered);let html='';
    if(currentFilter==='all'){html+='<div class="section-title">🇲🇽 Partidos del día '+getTodayMX()+' ('+filtered.length+') - Poisson + ELO - Base '+allMatches.length+'</div>';}
    else if(currentFilter==='top'){html+='<div class="section-title">★ Top Picks ('+filtered.length+')</div>';}
    else if(currentFilter==='aciertos'){html+='<div class="section-title">✅ Aciertos ('+filtered.length+')</div>';$grid.innerHTML=html+'<div class="cards-grid">'+filtered.map(cardA).join('')+'</div>';return;}
    else if(currentFilter==='fallos'){html+='<div class="section-title">❌ Fallos ('+filtered.length+')</div>';$grid.innerHTML=html+'<div class="cards-grid">'+filtered.map(cardA).join('')+'</div>';return;}
    else if(currentFilter==='progol'){$grid.innerHTML=renderProgolReal();return;}
    else if(currentFilter==='combinada'){html+='<div class="section-title">∽ Combinadas ('+filtered.length+')</div>';$grid.innerHTML=html+'<div class="cards-grid">'+filtered.slice(0,20).map(cardA).join('')+'</div>';return;}
    else {html+='<div class="section-title">'+esc(currentFilter)+' ('+filtered.length+') - Temporada completa</div>';}
    if(g.enJuego.length>0)html+=renderSection('🔴 En Juego ('+g.enJuego.length+')',g.enJuego);
    if(g.programados.length>0)html+=renderSection('⏰ Programados ('+g.programados.length+')',g.programados);
    if(g.finalizados.length>0)html+=renderSection('✅ Finalizados ('+g.finalizados.length+')',g.finalizados);
    if(g.enJuego.length===0&&g.programados.length===0&&g.finalizados.length===0){if(filtered.length>0)html+='<div class="cards-grid">'+filtered.map(cardA).join('')+'</div>';else html+='<div class="card"><div class="meta">No hay partidos para '+getTodayMX()+'. Base: '+allMatches.length+' partidos. Usa Buscar.</div></div>';}
    html+='<div class="section-title">📊 Transparencia</div><div class="card"><div class="meta">Probabilidad != recomendación segura. Σ 1X2 ~100% validado.</div></div>';$grid.innerHTML=html;
  }catch(e){log('RENDER ERROR: '+e.message,'err');$grid.innerHTML='<div class="card"><div class="meta" style="color:#ff6b6b">Error: '+esc(e.message)+'</div></div>';}
}
async function loadLigaMXOnly(){
  // Force fresh if backend changed (check localStorage version)
  const storedVer = localStorage.getItem('lian_cache_version');
  if(storedVer !== CACHE_VERSION){
    localStorage.removeItem('lian_season_cache');
    localStorage.removeItem('lian_cache_version');
    ALL_BASE_CACHE_LOADED = false;
    allMatches = [];
    log('Cache version changed '+storedVer+' -> '+CACHE_VERSION+', limpiando cache','ok');
  }
  if(ALL_BASE_CACHE_LOADED&&allMatches.length>0){log('Cache '+allMatches.length+' partidos - filtro local','ok');renderAll();return;}
  try{
    $status.textContent='Cargando base Liga MX... temporada completa';
    const data=await api('/api/liga-mx/season?limit=500');
    if(data&&data.matches&&data.matches.length>0){allMatches=data.matches;SEASON_CACHE=data.matches;ALL_BASE_CACHE_LOADED=true;localStorage.setItem('lian_cache_version', CACHE_VERSION);log('BASE '+data.matches.length+' partidos - cache listo','ok');renderAll();$status.textContent='BASE: '+data.count+' partidos Liga MX - Cache local activo';return;}
  }catch(e){log('Error base: '+e.message,'err');}
  try{const allData=await api('/api/calendar/season?limit=500');allMatches=allData.matches||[];ALL_BASE_CACHE_LOADED=true;$status.textContent='BASE: '+allMatches.length+' partidos - cache';renderAll();}catch(e2){$status.textContent='Error total: '+e2.message;}
}
async function syncLigaMX(){$status.textContent='Sincronizando Liga MX 60-90 seg...';try{await api('/api/liga-mx/sync');log('Sync iniciado, espera 10s','ok');ALL_BASE_CACHE_LOADED=false;setTimeout(loadLigaMXOnly,10000);}catch(e){$status.textContent='Error sync: '+e.message;}}
async function loadProgolFromBackend(){try{const data=await api('/api/progol/current');if(data&&data.progol){PROGOL_REAL=data.progol.map(function(p,i){return {n:p.n||i+1,home:(p.home||'').toUpperCase(),away:(p.away||'').toUpperCase()};});REVANCHA_REAL=(data.revancha||[]).map(function(p,i){return {n:p.n||i+1,home:(p.home||'').toUpperCase(),away:(p.away||'').toUpperCase()};});PROGOL_META={fecha:data.fecha||'',hasta:data.hasta||'',fuente:data.fuente||'Backend'};log('Progol backend: '+data.fecha+' - '+PROGOL_REAL.length+'+'+REVANCHA_REAL.length,'ok');if(currentFilter==='progol')renderAll();}}catch(e){log('Progol no disponible: '+e.message,'err');}}
document.addEventListener('click',function(e){const btn=e.target.closest('.menu-item');if(!btn||!btn.dataset.filter)return;document.querySelectorAll('.menu-item').forEach(function(b){b.classList.remove('active');});btn.classList.add('active');currentFilter=btn.dataset.filter;if($searchBox)$searchBox.style.display='none';log('Filtro: '+currentFilter+' - cache '+allMatches.length,'ok');renderAll();if(window.innerWidth<800){const main=document.querySelector('.main');if(main)main.scrollTop=0;}});
if($searchInput)$searchInput.addEventListener('input',function(){if(currentFilter==='search')updateSearchResultsOnly();else renderAll();});
if($leagueSelect)$leagueSelect.addEventListener('change',function(){if(currentFilter==='search')updateSearchResultsOnly();else renderAll();});
if($dateInput)$dateInput.addEventListener('change',function(){if(currentFilter==='search')updateSearchResultsOnly();});
const loadBtn=document.getElementById('loadBtn');if(loadBtn)loadBtn.addEventListener('click',loadLigaMXOnly);
const refreshBtn=document.getElementById('refreshBtn');if(refreshBtn)refreshBtn.addEventListener('click',syncLigaMX);
(function(){try{if($dateInput)$dateInput.value='';}catch(e){}api('/api/health').then(function(h){$status.textContent='API: '+h.version+' - '+h.records+' partidos - Cargando base...';return loadLigaMXOnly();}).then(function(){loadProgolFromBackend();}).catch(function(e){$status.textContent='API no conecta: '+e.message;log('Health error: '+e.message,'err');});})();
