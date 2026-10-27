// App - Logica principal de carga y eventos
async function loadLigaMXOnly(){
  const storedVer = localStorage.getItem('lian_cache_version');
  if(storedVer !== CONFIG.CACHE_VERSION){
    localStorage.removeItem('lian_season_cache');
    localStorage.removeItem('lian_cache_version');
    ALL_BASE_CACHE_LOADED = false;
    allMatches = [];
    log('Cache version changed '+storedVer+' -> '+CONFIG.CACHE_VERSION+', limpiando cache','ok');
  }
  if(ALL_BASE_CACHE_LOADED&&allMatches.length>0){log('Cache '+allMatches.length+' partidos - filtro local','ok');renderAll();return;}
  try{
    const $status=document.getElementById('status');
    if($status) $status.textContent='Cargando base Liga MX... temporada completa';
    const data=await API.ligaMXSeason(500);
    if(data&&data.matches&&data.matches.length>0){
      allMatches=data.matches;SEASON_CACHE=data.matches;ALL_BASE_CACHE_LOADED=true;
      localStorage.setItem('lian_cache_version', CONFIG.CACHE_VERSION);
      log('BASE '+data.matches.length+' partidos - cache listo','ok');
      renderAll();
      if($status) $status.textContent='BASE: '+data.count+' partidos Liga MX - Cache local activo';
      return;
    }
  }catch(e){log('Error base: '+e.message,'err');}
  try{
    const allData=await API.calendarSeason(500);
    allMatches=allData.matches||[];ALL_BASE_CACHE_LOADED=true;
    const $status=document.getElementById('status');
    if($status) $status.textContent='BASE: '+allMatches.length+' partidos - cache';
    renderAll();
  }catch(e2){
    const $status=document.getElementById('status');
    if($status) $status.textContent='Error total: '+e2.message;
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

// Event Listeners
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
    if($status) $status.textContent='API: '+h.version+' - '+h.records+' partidos - Cargando base...';
    return loadLigaMXOnly();
  }).then(function(){loadProgolFromBackend();}).catch(function(e){
    const $status=document.getElementById('status');
    if($status) $status.textContent='API no conecta: '+e.message;
    log('Health error: '+e.message,'err');
  });
})();
