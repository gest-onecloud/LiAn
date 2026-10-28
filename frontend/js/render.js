// Render V116.3 - Con contadores Acertó/Falló para ajuste modelo
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
  
  // V120 - Botón Mejorar solo para programados
  let mejorarBtn = '';
  if(m.estado!=='FINALIZADO' && !m.improved){
    const safeHome = (m.home||'').replace(/'/g,'');
    const safeAway = (m.away||'').replace(/'/g,'');
    const safeLeague = (m.league_code||m.league||'mex.1').replace(/'/g,'');
    mejorarBtn = '<button class="btn-mejorar" onclick="mejorarPartido(\''+esc(safeHome)+'\',\''+esc(safeAway)+'\',\''+esc(safeLeague)+'\', this)" title="MonteCarlo 6000 + Disciplina + ELO para este partido">🚀 Mejorar</button>';
  } else if(m.improved){
    mejorarBtn = '<span class="badge badge-mejorado">🚀 Mejorado MC6000</span>';
  }

  // Mostrar disciplina si existe
  let discInfo = '';
  if(m.team_stats || m.discipline_index){
    const disc = m.discipline_index || '';
    if(disc) discInfo = '<div class="disc-info" style="font-size:10px;color:#8aa0c8">🟨 Disciplina: '+disc+'</div>';
  }

  return '<div class="card-compact"><div class="card-top"><span class="card-league">'+esc(liga)+' • '+esc(hora)+' • '+esc(fecha)+'</span>'+badge+'</div><div class="card-teams"><span>'+esc(m.home)+'</span><span class="vs-small"> vs </span><span>'+esc(m.away)+'</span></div>'+scoreBox+'<div class="card-probs"><span>L: '+(p['1']||0).toFixed(1)+'%</span><span>E: '+(p['X']||0).toFixed(1)+'%</span><span>V: '+(p['2']||0).toFixed(1)+'%</span><span class="sum">Σ '+total+'%</span></div><div class="card-bottom"><span class="fav">★ '+esc(fav)+'</span><span class="conf">Conf: '+esc(conf)+dot+'</span>'+mejorarBtn+'</div>'+discInfo+'</div>';
}

// V120 - Función mejorar partido individual con MonteCarlo
async function mejorarPartido(home, away, league, btn){
  if(!btn) return;
  const originalText = btn.innerHTML;
  btn.innerHTML = '⏳ Mejorando...';
  btn.disabled = true;
  try{
    const url = 'https://lian-backend.onrender.com/api/match/improve?home='+encodeURIComponent(home)+'&away='+encodeURIComponent(away)+'&league='+encodeURIComponent(league);
    log('Mejorando '+home+' vs '+away+' con MonteCarlo 6000...', 'info');
    const res = await fetch(url);
    const data = await res.json();
    if(data.error){
      log('Error mejorar: '+data.error, 'err');
      btn.innerHTML = '❌ Error';
      setTimeout(()=>{btn.innerHTML=originalText; btn.disabled=false;}, 2000);
      return;
    }
    // Actualizar card
    const card = btn.closest('.card-compact');
    if(card){
      const p = data.probabilities;
      card.querySelector('.card-probs').innerHTML = '<span style="color:#1ee07a">L: '+(p['1']||0).toFixed(1)+'%</span><span>E: '+(p['X']||0).toFixed(1)+'%</span><span style="color:#ff6b6b">V: '+(p['2']||0).toFixed(1)+'%</span><span class="sum">Σ '+((p['1']+p['X']+p['2'])).toFixed(1)+'%</span>';
      const favEl = card.querySelector('.fav');
      if(favEl) favEl.innerHTML = '★ '+esc(data.favorite)+' <small>(MC6000)</small>';
      // MonteCarlo info
      const mc = data.montecarlo || data.mc_interval || (data.prob_details&&data.prob_details.montecarlo_validador);
      if(mc){
        let mcL = (mc['1']||0); let mcX = (mc['X']||0); let mcV = (mc['2']||0);
        // Si viene en % >1, no multiplicar x100
        if(mcL<=1){mcL*=100; mcX*=100; mcV*=100;}
        let mcHtml = document.createElement('div');
        mcHtml.className = 'mc-info';
        mcHtml.style.cssText = 'font-size:10px;color:#8ab4ff;margin-top:4px;background:#0a1a33;padding:6px;border-radius:6px;line-height:1.3';
        let expl = '';
        if(data.explicabilidad && data.explicabilidad.length>0){
          expl = '<br><small style="color:#8aa0c8">'+data.explicabilidad[0]+' | '+data.explicabilidad[1]+'</small>';
        }
        mcHtml.innerHTML = '🎲 MC6000: L '+mcL.toFixed(1)+'% E '+mcX.toFixed(1)+'% V '+mcV.toFixed(1)+'% | ELO '+Math.round(data.elo[home])+' vs '+Math.round(data.elo[away])+expl;
        const bottom = card.querySelector('.card-bottom');
        if(bottom && !bottom.querySelector('.mc-info')) bottom.appendChild(mcHtml);
      }
      btn.innerHTML = '✅ Mejorado';
      btn.className = 'badge badge-mejorado';
      btn.disabled = true;
      log('Mejorado '+home+' vs '+away+': L '+(p['1']||0).toFixed(1)+'% E '+(p['X']||0).toFixed(1)+'% V '+(p['2']||0).toFixed(1)+'% con MC6000', 'ok');
    }
  } catch(e){
    log('Error mejorar '+home+' vs '+away+': '+e.message, 'err');
    btn.innerHTML = '❌ Error';
    setTimeout(()=>{btn.innerHTML=originalText; btn.disabled=false;}, 2000);
  }
}


function calcStats(matches){
  const fin = matches.filter(m=>m.estado==='FINALIZADO');
  const ac = fin.filter(m=>m.acierto===true).length;
  const fa = fin.filter(m=>m.acierto===false).length;
  const tot = fin.length;
  const pct = tot>0 ? ((ac/tot)*100).toFixed(1) : 0;
  return {total:matches.length, fin:tot, ac:ac, fa:fa, pct:pct};
}

function renderStatsBar(matches, extra=''){
  const s = calcStats(matches);
  if(s.fin===0) return '<div class="section-title">'+extra+' ('+matches.length+')</div>';
  return '<div class="section-title" style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px"><span>'+extra+' ('+matches.length+')</span><span style="font-size:12px">Finalizados: '+s.fin+' | ✅ '+s.ac+' Acertó | ❌ '+s.fa+' Falló | '+s.pct+'% acierto</span></div>';
}

function renderSection(title,matches){
  if(matches.length===0) return '';
  const s = calcStats(matches);
  let statsTxt = '';
  if(title.includes('Finalizados') && s.fin>0){
    statsTxt = ' - ✅ '+s.ac+' | ❌ '+s.fa+' | '+s.pct+'%';
  }
  return '<div class="section-title">'+title+statsTxt+'</div><div class="cards-grid">'+matches.map(cardA).join('')+'</div>';
}

function findMatchForProgol(home,away){
  const nh=(home||'').toLowerCase();const na=(away||'').toLowerCase();
  const src=allMatches.concat(SEASON_CACHE);
  for(let i=0;i<src.length;i++){
    const m=src[i];
    const h=(m.home||'').toLowerCase();const a=(m.away||'').toLowerCase();
    if((h.indexOf(nh)>=0||nh.indexOf(h)>=0)&&(a.indexOf(na)>=0||na.indexOf(a)>=0)) return m;
  }
  return null;
}

function renderProgolReal(){
  let html='<div class="section-title">▤ Progol - '+PROGOL_META.fecha+' hasta '+PROGOL_META.hasta+' - '+PROGOL_META.fuente+'</div>';
  function listProgol(list,titulo){
    let h='<div class="analytics-panel"><div class="section-title" style="background:'+(titulo.indexOf('REVANCHA')>=0?'#1a2a1a':'#0f1a33')+'">'+titulo+' ('+list.length+')</div><div style="display:grid;gap:8px">';
    for(let i=0;i<list.length;i++){
      const it=list[i];const m=findMatchForProgol(it.home,it.away);
      let p={L:33,E:33,V:33};let fav=it.home;let conf='Media';let pick='L';let maxP=33;
      if(m){
        const pr=m.probabilities||{'1':33,'X':33,'2':33};
        p={L:pr['1']||33,E:pr['X']||33,V:pr['2']||33};
        maxP=Math.max(p.L,p.E,p.V);
        if(p.E>p.L&&p.E>p.V){pick='E';fav='Empate';}
        else if(p.V>p.L&&p.V>p.E){pick='V';fav=m.away;}
        else {pick='L';fav=m.home;}
        conf=m.confidence||'Media';
      }
      const col=pick==='L'?'#1ee07a':pick==='E'?'#f5d547':'#ff6b6b';
      h+='<div class="card progol-row" style="display:flex;gap:10px;padding:10px;border-left:4px solid '+col+'"><div style="background:#1a2a4a;color:#fff;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:12px">'+it.n+'</div><div style="flex:1"><div style="display:flex;justify-content:space-between;gap:8px"><span style="font-weight:700;font-size:13px">'+esc(it.home)+' vs '+esc(it.away)+'</span><span style="font-size:11px;color:'+col+'"><b>'+pick+' → '+esc(fav)+' ('+maxP.toFixed(1)+'%)</b> - '+esc(conf)+'</span></div><div style="font-size:10px;color:#8aa0c8;margin-top:2px">L:'+p.L.toFixed(1)+'% E:'+p.E.toFixed(1)+'% V:'+p.V.toFixed(1)+'% '+(m?'• '+esc(m.league||''):'')+'</div></div></div>';
    }
    h+='</div></div>';return h;
  }
  html+=listProgol(PROGOL_REAL,'PROGOL - 14 PARTIDOS');
  html+=listProgol(REVANCHA_REAL,'REVANCHA - 7 PARTIDOS');
  return html;
}

function updateSearchResultsOnly(){
  try{
    const filtered=getFiltered();
    const $grid=document.getElementById('grid');
    const container=document.getElementById('searchResults')||$grid;
    const qEl=document.getElementById('topSearchInput');const q=(qEl?qEl.value:'').trim();
    const fromEl=document.getElementById('topDateFrom');const toEl=document.getElementById('topDateTo');
    const fromV=fromEl?fromEl.value:'';const toV=toEl?toEl.value:'';
    const ligaEl=document.getElementById('topLeagueSelect');const liga=ligaEl?ligaEl.value:'all';
    let html='';
    if(!q&&liga==='all'&&!fromV&&!toV){
      html='<div class="search-empty" style="text-align:center;padding:50px 20px;border:1px dashed #1e3a6a;border-radius:12px;background:#0a1228"><div style="font-size:48px">🔍</div><h2 style="color:#e6edf3;margin:12px 0">Busca un equipo o liga</h2><p style="color:#8aa0c8">Escribe \"Atlas\", \"América\", \"Liga MX\" o elige liga y rango<br>Tienes '+allMatches.length+' partidos en cache temporada completa</p></div>';
      container.innerHTML=html;return;
    }
    const st = calcStats(filtered);
    const rangeTxt=(fromV||toV)?' del '+(fromV||'inicio')+' al '+(toV||'hoy'):''; 
    html+='<div class="section-title" style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px"><span>🔍 \"'+esc(q)+'\" '+(liga!=='all'?esc(liga):'')+rangeTxt+' ('+filtered.length+')</span><span style="font-size:12px;color:#8ab4ff">Finalizados: '+st.fin+' | ✅ '+st.ac+' ('+st.pct+'%) | ❌ '+st.fa+'</span></div>';
    const g=groupByEstado(filtered);
    if(g.enJuego.length>0)html+=renderSection('🔴 En Juego ('+g.enJuego.length+')',g.enJuego);
    if(g.programados.length>0)html+=renderSection('⏰ Programados ('+g.programados.length+')',g.programados);
    if(g.finalizados.length>0)html+=renderSection('✅ Finalizados ('+g.finalizados.length+')',g.finalizados);
    if(filtered.length===0)html+='<div class="card"><div class="meta">No hay partidos para \"'+esc(q)+'\" '+esc(liga)+' '+rangeTxt+'. Prueba sin fechas.</div></div>';
    container.innerHTML=html;
  }catch(e){console.error(e);log('Search render err: '+e.message,'err');}
}

function renderAll(){
  try{
    const filtered=getFiltered();
    const $grid=document.getElementById('grid');
    const $countBadge=document.getElementById('countBadge');
    const globalStats = calcStats(allMatches);
    const filteredStats = calcStats(filtered);
    if($countBadge) $countBadge.textContent=filtered.length+' partidos / '+allMatches.length+' total | Global: ✅ '+globalStats.ac+' ❌ '+globalStats.fa+' ('+globalStats.pct+'%)';
    if(currentFilter==='search'){
      $grid.style.display='block'; $grid.style.width='100%';
      const exists=document.getElementById('searchBarContainer');
      if(!exists){
        const $searchInput=document.getElementById('searchInput');const $leagueSelect=document.getElementById('leagueSelect');
        const q=($searchInput?$searchInput.value:'').trim();const ligaVal=$leagueSelect?$leagueSelect.value:'all';
        let html='<div id="searchFilterWrapper" class="search-filter-wrapper" style="width:100%;display:block;margin-bottom:20px"><div id="searchBarContainer" class="card search-filter-card"><input id="topSearchInput" type="text" placeholder="Buscar: América, Atlas, Pumas, Liga MX..." value="'+esc(q)+'" class="search-main-input"><div class="search-filters-grid"><select id="topLeagueSelect" class="search-select"><option value="all" '+(ligaVal==='all'?'selected':'')+'>Todas las ligas</option><option value="mex" '+(ligaVal.toLowerCase().indexOf('mex')>=0?'selected':'')+'>Liga MX</option><option value="arg" '+(ligaVal.toLowerCase().indexOf('arg')>=0?'selected':'')+'>Argentina</option><option value="bra" '+(ligaVal.toLowerCase().indexOf('bra')>=0?'selected':'')+'>Brasil</option><option value="eng" '+(ligaVal.toLowerCase().indexOf('eng')>=0?'selected':'')+'>Premier</option><option value="esp" '+(ligaVal.toLowerCase().indexOf('esp')>=0?'selected':'')+'>España</option><option value="ita" '+(ligaVal.toLowerCase().indexOf('ita')>=0?'selected':'')+'>Italia</option></select><input id="topDateFrom" type="date" class="search-date" title="Desde"><input id="topDateTo" type="date" class="search-date" title="Hasta"></div><div class="search-actions"><button id="topSearchBtn" class="btn-search">Buscar</button><button id="topClearBtn" class="btn-clear">Limpiar</button><span id="searchCountBadge" class="search-badge"></span></div><div class="search-tip">Tip: America = toda su temporada. Base: '+allMatches.length+' partidos | Global ✅ '+globalStats.ac+' ❌ '+globalStats.fa+' ('+globalStats.pct+'%)</div></div></div></div><div id="searchResults" class="search-results-full" style="width:100%;display:block;clear:both;margin-top:20px"></div>';
        $grid.innerHTML=html;
        setTimeout(function(){
          const topS=document.getElementById('topSearchInput');const topFrom=document.getElementById('topDateFrom');const topTo=document.getElementById('topDateTo');const topL=document.getElementById('topLeagueSelect');
          const $searchInput=document.getElementById('searchInput');const $leagueSelect=document.getElementById('leagueSelect');
          const upd=function(){if(topS&&$searchInput) $searchInput.value=topS.value;if(topL&&$leagueSelect) $leagueSelect.value=topL.value;updateSearchResultsOnly();};
          if(topS){topS.addEventListener('input',upd);topS.focus();}
          if(topFrom) topFrom.addEventListener('change',upd);if(topTo) topTo.addEventListener('change',upd);if(topL) topL.addEventListener('change',upd);
          const btn=document.getElementById('topSearchBtn');if(btn) btn.addEventListener('click',upd);
          const clr=document.getElementById('topClearBtn');if(clr) clr.addEventListener('click',function(){if(topS)topS.value='';if(topFrom)topFrom.value='';if(topTo)topTo.value='';if(topL)topL.value='all';if($searchInput) $searchInput.value='';if($leagueSelect) $leagueSelect.value='all';updateSearchResultsOnly();if(topS)topS.focus();});
          updateSearchResultsOnly();
        },0);
        return;
      } else {updateSearchResultsOnly();return;}
    }
    if(currentFilter==='analytics'){
      const s = calcStats(allMatches);
      $grid.style.display=''; 
      $grid.innerHTML='<div class="analytics-panel"><div class="section-title">📊 Estadísticas V116 - '+allMatches.length+' partidos</div><div class="card" style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px"><div style="background:#0f2a1a;border:1px solid #1ee07a;padding:12px;border-radius:8px;text-align:center"><div style="font-size:24px;font-weight:900;color:#1ee07a">'+s.ac+'</div><div style="font-size:12px;color:#8aa0c8">ACERTÓ</div></div><div style="background:#2a1212;border:1px solid #ff6b6b;padding:12px;border-radius:8px;text-align:center"><div style="font-size:24px;font-weight:900;color:#ff6b6b">'+s.fa+'</div><div style="font-size:12px;color:#8aa0c8">FALLÓ</div></div><div style="background:#1a2a4a;border:1px solid #3a6ab5;padding:12px;border-radius:8px;text-align:center"><div style="font-size:24px;font-weight:900;color:#8ab4ff">'+s.pct+'%</div><div style="font-size:12px;color:#8aa0c8">ACIERTO</div></div></div><div class="card" style="margin-top:12px"><div class="meta">Base: '+allMatches.length+' partidos | Finalizados: '+s.fin+' | Poisson + ELO + team_stats REAL V116<br>Modelo: '+ (allMatches[0]?allMatches[0].source||'V116':'V116')+'</div></div></div>';
      return;
    }
    $grid.style.display=''; const g=groupByEstado(filtered);let html='';
    if(currentFilter==='all'){
      html+='<div class="section-title" style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px"><span>🇲🇽 Partidos del día '+getTodayMX()+' ('+filtered.length+') - Base '+allMatches.length+'</span><span style="font-size:12px;color:#8ab4ff">Global: ✅ '+globalStats.ac+' ❌ '+globalStats.fa+' ('+globalStats.pct+'%) | Filtro: ✅ '+filteredStats.ac+' ❌ '+filteredStats.fa+' ('+filteredStats.pct+'%)</span></div>';
    }
    else if(currentFilter==='top'){
      html+='<div class="section-title" style="display:flex;justify-content:space-between"><span>★ Top Picks ('+filtered.length+')</span><span style="font-size:12px">✅ '+filteredStats.ac+' ❌ '+filteredStats.fa+' ('+filteredStats.pct+'%)</span></div>';
    }
    else if(currentFilter==='aciertos'){html+='<div class="section-title">✅ Aciertos ('+filtered.length+' / '+globalStats.fin+' - '+filteredStats.pct+'% global)</div>';$grid.innerHTML=html+'<div class="cards-grid">'+filtered.map(cardA).join('')+'</div>';return;}
    else if(currentFilter==='fallos'){html+='<div class="section-title">❌ Fallos ('+filtered.length+' / '+globalStats.fin+' - '+(100 - parseFloat(globalStats.pct)).toFixed(1)+'% global)</div>';$grid.innerHTML=html+'<div class="cards-grid">'+filtered.map(cardA).join('')+'</div>';return;}
    else if(currentFilter==='progol'){$grid.innerHTML=renderProgolReal();return;}
    else if(currentFilter==='combinada'){html+='<div class="section-title">∽ Combinadas ('+filtered.length+') - ✅ '+filteredStats.ac+' ❌ '+filteredStats.fa+'</div>';$grid.innerHTML=html+'<div class="cards-grid">'+filtered.slice(0,20).map(cardA).join('')+'</div>';return;}
    else {html+='<div class="section-title" style="display:flex;justify-content:space-between"><span>'+esc(currentFilter)+' ('+filtered.length+')</span><span style="font-size:12px">✅ '+filteredStats.ac+' ❌ '+filteredStats.fa+' ('+filteredStats.pct+'%)</span></div>';}
    if(g.enJuego.length>0)html+=renderSection('🔴 En Juego ('+g.enJuego.length+')',g.enJuego);
    if(g.programados.length>0)html+=renderSection('⏰ Programados ('+g.programados.length+')',g.programados);
    if(g.finalizados.length>0)html+=renderSection('✅ Finalizados ('+g.finalizados.length+')',g.finalizados);
    if(g.enJuego.length===0&&g.programados.length===0&&g.finalizados.length===0){if(filtered.length>0)html+='<div class="cards-grid">'+filtered.map(cardA).join('')+'</div>';else html+='<div class="card"><div class="meta">No hay partidos para '+getTodayMX()+'. Base: '+allMatches.length+' partidos. Usa Buscar.</div></div>';}
    html+='<div class="section-title">📊 Transparencia V116</div><div class="card"><div class="meta">Global: '+allMatches.length+' partidos | Finalizados: '+globalStats.fin+' | ✅ '+globalStats.ac+' Acertó | ❌ '+globalStats.fa+' Falló | '+globalStats.pct+'% acierto<br>Filtro actual: '+filtered.length+' partidos | ✅ '+filteredStats.ac+' | ❌ '+filteredStats.fa+' | '+filteredStats.pct+'%<br>Probabilidad != recomendación segura. Σ 1X2 ~100% validado. Modelo V116 REAL team_stats.</div></div>';$grid.innerHTML=html;
  }catch(e){log('RENDER ERROR: '+e.message,'err');const $grid=document.getElementById('grid');if($grid) $grid.innerHTML='<div class="card"><div class="meta" style="color:#ff6b6b">Error: '+esc(e.message)+'</div></div>';}
}
