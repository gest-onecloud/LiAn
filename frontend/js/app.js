// App V121.2 - Fix se queda cargando, fast sin MC6000, futuros 14d
async function loadLigaMXOnly(){
  const storedVer = localStorage.getItem('lian_cache_version');
  if(storedVer !== CONFIG.CACHE_VERSION){
    localStorage.removeItem('lian_season_cache');
    localStorage.removeItem('lian_cache_version');
    ALL_BASE_CACHE_LOADED = false;
    allMatches = [];
    log('Cache version changed '+storedVer+' -> '+CONFIG.CACHE_VERSION+', limpiando cache','ok');
  }
  if(ALL_BASE_CACHE_LOADED&&allMatches.length>0){
    log('Cache '+allMatches.length+' partidos - filtro local','ok');
    renderAll();
    loadFuture14Days();
    return;
  }
  try{
    const $status=document.getElementById('status');
    if($status) $status.textContent='Cargando base Liga MX V121.2 fast 250...';
    const data=await API.ligaMXSeason(250);
    if(data&&data.matches&&data.matches.length>0){
      allMatches=data.matches;
      SEASON_CACHE=data.matches;
      ALL_BASE_CACHE_LOADED=true;
      localStorage.setItem('lian_cache_version', CONFIG.CACHE_VERSION);
      const prog = data.programados|| allMatches.filter(m=>!m.home_score||m.estado==='PROGRAMADO').length;
      log('BASE '+data.matches.length+' partidos ('+prog+' programados) - cache listo V121.2 fast','ok');
      renderAll();
      if($status) $status.textContent='BASE: '+data.count+' partidos ('+prog+' programados) - V121.2 fast sin MC6000';
      loadFuture14Days();
      return;
    }
  }catch(e){
    log('Error base: '+e.message,'err');
    console.error(e);
  }
  try{
    const allData=await API.calendarSeason(250);
    allMatches=allData.matches||[];
    ALL_BASE_CACHE_LOADED=true;
    const $status=document.getElementById('status');
    if($status) $status.textContent='BASE: '+allMatches.length+' partidos - cache V121.2';
    renderAll();
    loadFuture14Days();
  }catch(e2){
    const $status=document.getElementById('status');
    if($status) $status.textContent='Error total: '+e2.message;
  }
}

async function loadFuture14Days(){
  try{
    const progCount = allMatches.filter(m=>!m.home_score||m.estado==='PROGRAMADO'||(m.date&&m.date>=new Date().toISOString().slice(0,10))).length;
    if(progCount>=5){
      log('Ya hay '+progCount+' programados en cache V121.2, no sync-future bloqueante','info');
      const $status=document.getElementById('status');
      if($status) $status.textContent='BASE: '+allMatches.length+' partidos ('+progCount+' programados 14d) - V121.2 fast';
      return;
    }
    const $status=document.getElementById('status');
    if($status) $status.textContent='Buscando próximos 14 días...';
    log('V121.2 - Sincronizando próximos 14 días solo mex.1 si faltan programados','info');
    const future = await API.request('/api/supabase/sync-future?days=14&league=mex.1');
    if(future && future.found>0){
      log('Futuro: '+future.found+' partidos (SQLite '+future.saved_sqlite+')','ok');
      const fresh = await API.ligaMXSeason(250);
      if(fresh && fresh.matches){
        allMatches=fresh.matches;
        SEASON_CACHE=fresh.matches;
        renderAll();
        if($status) $status.textContent='BASE: '+fresh.count+' partidos ('+fresh.programados+' programados) - V121.2';
        log('Actualizado '+fresh.count+' total con '+fresh.programados+' programados 14d','ok');
      }
    } else {
      log('Sin futuros nuevos, base '+allMatches.length,'info');
    }
  }catch(e){
    log('Error futuros 14 días no bloquea: '+e.message,'err');
  }
}

async function syncLigaMX(){
  const $status=document.getElementById('status');
  if($status) $status.textContent='Sincronizando Liga MX 60-90 seg...';
  try{
    await API.ligaMXSync();
    log('Sync iniciado, espera 10s','ok');
    ALL_BASE_CACHE_LOADED=false;
    setTimeout(loadLigaMXOnly,10000);
  }catch(e){
    if($status) $status.textContent='Error sync: '+e.message;
  }
}

async function loadProgolFromBackend(){
  try{
    const data=await API.progolCurrent();
    if(data&&data.progol){
      PROGOL_REAL=data.progol.map(function(p,i){return {n:p.n||i+1,home:(p.home||'').toUpperCase(),away:(p.away||'').toUpperCase()};});
      REVANCHA_REAL=(data.revancha||[]).map(function(p,i){return {n:p.n||i+1,home:(p.home||'').toUpperCase(),away:(p.away||'').toUpperCase()};});
      PROGOL_META={fecha:data.fecha||'',hasta:data.hasta||'',fuente:data.fuente||'Backend'};
      log('Progol backend: '+data.fecha+' - '+PROGOL_REAL.length+'+'+REVANCHA_REAL.length,'ok');
      if(currentFilter==='progol') renderAll();
    }
  }catch(e){log('Progol no disponible: '+e.message,'err');}
}

document.addEventListener('click',function(e){
  const btn=e.target.closest('.menu-item');
  if(!btn||!btn.dataset.filter) return;
  document.querySelectorAll('.menu-item').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  currentFilter=btn.dataset.filter;
  const $searchBox=document.getElementById('searchBox');
  if($searchBox) $searchBox.style.display='none';
  log('Filtro: '+currentFilter+' - cache '+allMatches.length,'ok');
  renderAll();
  if(window.innerWidth<800){
    const main=document.querySelector('.main');
    if(main) main.scrollTop=0;
  }
});

(function(){
  const $dateInput=document.getElementById('dateInput');
  const $searchInput=document.getElementById('searchInput');
  const $leagueSelect=document.getElementById('leagueSelect');
  try{if($dateInput) $dateInput.value='';}catch(e){}
  if($searchInput) $searchInput.addEventListener('input',function(){if(currentFilter==='search') updateSearchResultsOnly();else renderAll();});
  if($leagueSelect) $leagueSelect.addEventListener('change',function(){if(currentFilter==='search') updateSearchResultsOnly();else renderAll();});
  if($dateInput) $dateInput.addEventListener('change',function(){if(currentFilter==='search') updateSearchResultsOnly();});
  const loadBtn=document.getElementById('loadBtn');if(loadBtn) loadBtn.addEventListener('click',loadLigaMXOnly);
  const refreshBtn=document.getElementById('refreshBtn');if(refreshBtn) refreshBtn.addEventListener('click',syncLigaMX);
  API.health().then(function(h){
    const $status=document.getElementById('status');
    if($status) $status.textContent='API: '+h.version+' - '+h.records+' partidos - Cargando base V121.2 fast...';
    return loadLigaMXOnly();
  }).then(function(){loadProgolFromBackend();}).catch(function(e){
    const $status=document.getElementById('status');
    if($status) $status.textContent='API no conecta: '+e.message;
    log('Health error: '+e.message,'err');
  });
})();
