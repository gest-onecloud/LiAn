
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

const LIGAS_AMERICA = {
  'mex.1': 'Liga MX',
  'usa.1': 'MLS',
  'bra.1': 'Brasileirão',
  'arg.1': 'Liga Argentina',
  'concacaf.champions': 'Concachampions'
};
const LIGAS_EUROPA = {
  'eng.1': 'Premier League',
  'eng.fa': 'FA Cup',
  'esp.1': 'La Liga',
  'ita.1': 'Serie A',
  'ger.1': 'Bundesliga',
  'fra.1': 'Ligue 1',
  'uefa.champions': 'Champions League',
  'uefa.europa': 'Europa League',
  'uefa.europa.conf': 'Conference League'
};
const LIGAS_AMERICA_CODES = Object.keys(LIGAS_AMERICA);
const LIGAS_EUROPA_CODES = Object.keys(LIGAS_EUROPA);

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

function calcAnalytics(matches){
  const finalizados = matches.filter(m=>m.estado==='FINALIZADO');
  const porLiga = {};
  finalizados.forEach(m=>{
    const liga = m.league || m.league_code || 'Desconocida';
    if(!porLiga[liga]) porLiga[liga]={aciertos:0, fallos:0, total:0};
    porLiga[liga].total++;
    if(m.acierto===true) porLiga[liga].aciertos++;
    else if(m.acierto===false) porLiga[liga].fallos++;
  });
  let ligaMasAciertos = null, maxAc= -1;
  let ligaMenosAciertos = null, minAc= 999;
  for(const [liga, data] of Object.entries(porLiga)){
    if(data.aciertos > maxAc){ maxAc=data.aciertos; ligaMasAciertos={liga, ...data}; }
    if(data.aciertos < minAc){ minAc=data.aciertos; ligaMenosAciertos={liga, ...data}; }
  }
  const confStats = {Alta:{aciertos:0,fallos:0,total:0}, Media:{aciertos:0,fallos:0,total:0}, Limitada:{aciertos:0,fallos:0,total:0}};
  finalizados.forEach(m=>{
    const c = m.confidence;
    if(!confStats[c]) return;
    confStats[c].total++;
    if(m.acierto===true) confStats[c].aciertos++;
    else if(m.acierto===false) confStats[c].fallos++;
  });
  return {porLiga, ligaMasAciertos, ligaMenosAciertos, confStats, totalFinalizados: finalizados.length};
}

function renderAnalytics(matches){
  const a = calcAnalytics(matches);
  if(a.totalFinalizados===0) return `<div class="analytics-panel"><div class="section-title">📊 Estadísticas</div><div class="analytics-card">Aún no hay partidos finalizados hoy para analizar.</div></div>`;
  const mas = a.ligaMasAciertos;
  const menos = a.ligaMenosAciertos;
  return `
  <div class="analytics-panel">
    <div class="section-title">📊 Analytics del día - ${matches.length} partidos totales</div>
    <div class="analytics-grid">
      <div class="analytics-card">
        <div class="analytics-title">🏆 Liga con más aciertos</div>
        <div class="analytics-value">${mas?`${mas.liga} - ${mas.aciertos} aciertos / ${mas.total}`:'N/A'}</div>
        <div class="analytics-bar"><div class="bar-fill acierto" style="width:${mas?Math.round(mas.aciertos/Math.max(1,mas.total)*100):0}%"></div></div>
      </div>
      <div class="analytics-card">
        <div class="analytics-title">📉 Liga con menos aciertos</div>
        <div class="analytics-value">${menos?`${menos.liga} - ${menos.aciertos} aciertos / ${menos.total} (${menos.fallos} fallos)`:'N/A'}</div>
        <div class="analytics-bar"><div class="bar-fill fallo" style="width:${menos?Math.round(menos.fallos/Math.max(1,menos.total)*100):0}%"></div></div>
      </div>
    </div>
  </div>`;
}

function renderAnalyticsExtended(matches){
  const a = calcAnalytics(matches);
  const finalizados = matches.filter(m=>m.estado==='FINALIZADO');
  const enJuego = matches.filter(m=>m.estado==='EN_JUEGO');
  const programados = matches.filter(m=>m.estado==='PROGRAMADO');
  const aciertos = finalizados.filter(m=>m.acierto===true).length;
  const fallos = finalizados.filter(m=>m.acierto===false).length;
  const pct = finalizados.length>0?Math.round(aciertos/finalizados.length*100):0;
  const cs = a.confStats;
  const totalConf = cs.Alta.total+cs.Media.total+cs.Limitada.total;
  if(finalizados.length===0) return '';
  return `
  <div class="analytics-panel">
    <div class="analytics-grid">
      <div class="analytics-card">
        <div class="analytics-title">⚽ Estado del día</div>
        <div class="analytics-value">🔴 ${enJuego.length} En Juego | ⏰ ${programados.length} Programados | ✅ ${finalizados.length} Finalizados</div>
        <div class="analytics-bar"><div class="bar-fill acierto" style="width:${matches.length>0?Math.round(finalizados.length/matches.length*100):0}%"></div></div>
      </div>
      <div class="analytics-card">
        <div class="analytics-title">🎯 Acierto Global</div>
        <div class="analytics-value" style="font-size:22px">${pct}% - ${aciertos}✅ / ${fallos}❌ de ${finalizados.length}</div>
        <div class="analytics-bar"><div class="bar-fill acierto" style="width:${pct}%"></div></div>
      </div>
      <div class="analytics-card wide">
        <div class="analytics-title">📊 Detalle por confianza - Cuántos atinó y falló</div>
        <div class="conf-analytics" style="gap:10px">
          <div class="conf-detail">
            <div class="conf-row alta"><span class="conf-dot" style="background:#1ee07a"></span><b>Alta:</b> ${cs.Alta.total} partidos → ${cs.Alta.aciertos}✅ atinó / ${cs.Alta.fallos}❌ falló - ${cs.Alta.total>0?Math.round(cs.Alta.aciertos/cs.Alta.total*100):0}% acierto</div>
            <div class="conf-bar"><div class="bar-fill acierto" style="width:${cs.Alta.total>0?Math.round(cs.Alta.aciertos/cs.Alta.total*100):0}%"></div></div>
          </div>
          <div class="conf-detail">
            <div class="conf-row media"><span class="conf-dot" style="background:#f5d547"></span><b>Media:</b> ${cs.Media.total} partidos → ${cs.Media.aciertos}✅ atinó / ${cs.Media.fallos}❌ falló - ${cs.Media.total>0?Math.round(cs.Media.aciertos/cs.Media.total*100):0}% acierto</div>
            <div class="conf-bar"><div class="bar-fill" style="width:${cs.Media.total>0?Math.round(cs.Media.aciertos/cs.Media.total*100):0}%; background:#f5d547"></div></div>
          </div>
          <div class="conf-detail">
            <div class="conf-row limitada"><span class="conf-dot" style="background:#ff6b6b"></span><b>Limitada:</b> ${cs.Limitada.total} partidos → ${cs.Limitada.aciertos}✅ atinó / ${cs.Limitada.fallos}❌ falló - ${cs.Limitada.total>0?Math.round(cs.Limitada.aciertos/cs.Limitada.total*100):0}% acierto</div>
            <div class="conf-bar"><div class="bar-fill fallo" style="width:${cs.Limitada.total>0?Math.round(cs.Limitada.aciertos/cs.Limitada.total*100):0}%"></div></div>
          </div>
        </div>
      </div>
      <div class="analytics-card wide">
        <div class="analytics-title">📈 Resumen por liga</div>
        <div class="liga-table">
          ${Object.entries(a.porLiga).map(([liga,data])=>`<div class="liga-row"><span>${liga}</span><span>${data.aciertos}✅ ${data.fallos}❌ (${data.total})</span><span class="pct ${data.aciertos>=data.fallos?'ok':'err'}">${data.total>0?Math.round(data.aciertos/data.total*100):0}%</span></div>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
}

function cardA(m){
  const p = m.probabilities || {"1":0,"X":0,"2":0};
  const total = (p['1']+p['X']+p['2']).toFixed(1);
  const iconPath = `icons/${m.league_code||'default'}.svg`;
  const fallbackEmoji = m.league_code==='mex.1'?'🇲🇽':m.league_code==='usa.1'?'🇺🇸':m.league_code==='eng.1'?'🏴󠁧󠁢󠁥󠁮󠁧󠁿':m.league_code?.includes('champions')?'🏆':'⚽';
  let badgeHtml='';
  if(m.estado==='FINALIZADO'){
    if(m.acierto===true) badgeHtml='<span class="estado-tag estado-acierto">✅ Acertó</span>';
    else if(m.acierto===false) badgeHtml='<span class="estado-tag estado-fallo">❌ Falló</span>';
    else badgeHtml='<span class="estado-tag estado-finalizado">✅ Finalizado</span>';
  } else if(m.estado==='EN_JUEGO'){
    badgeHtml='<span class="estado-tag estado-en_juego">🔴 En Juego</span>';
  } else {
    badgeHtml='<span class="estado-tag estado-programado">⏰ Programado</span>';
  }
  let scoreHtml='';
  if(m.estado!=='PROGRAMADO' && m.home_score!=null && m.away_score!=null){
    scoreHtml=`<div class="score-row"><span class="score">${m.home_score} - ${m.away_score}</span></div>`;
  }
  const confColor=m.confidence==='Alta'?'#1ee07a':m.confidence==='Media'?'#f5d547':'#ff6b6b';
  const confIcon=m.confidence==='Alta'?'icons/conf-alta.svg':m.confidence==='Media'?'icons/conf-media.svg':'icons/conf-limitada.svg';
  const confHtml=m.confidence?`<span class="conf-badge conf-${m.confidence.toLowerCase()}"><img src="${confIcon}" class="conf-icon" alt=""><span class="conf-dot" style="background:${confColor}"></span>Conf: ${esc(m.confidence)}</span>`:'';
  return `<div class="card" data-league="${esc(m.league||'')}" data-home="${esc(m.home||'')}" data-away="${esc(m.away||'')}" data-estado="${esc(m.estado||'PROGRAMADO')}" data-acierto="${m.acierto===true?'acierto':m.acierto===false?'fallo':''}"><div class="badge-row"><span class="tag"><img src="${iconPath}" class="league-icon" onerror="this.style.display='none';this.nextElementSibling.style.display='inline'"><span style="display:none">${fallbackEmoji}</span> ${esc(m.league_code||'')}</span>${badgeHtml}</div><div class="league">${esc(m.league||'Futbol')} • ${esc(m.time||'')} • ${esc(m.date||'')}</div><div class="teams">${esc(m.home)} <span style="color:#8aa0c8">vs</span> ${esc(m.away)}</div>${scoreHtml}<div class="prob-row"><span class="prob">L: ${p['1']}%</span><span class="prob">E: ${p['X']}%</span><span class="prob">V: ${p['2']}%</span><span class="total">Σ ${total}%</span></div><div class="meta fav-conf-row"><span>⭐ Favorito: <b>${esc(m.favorite||'')}</b></span>${confHtml}</div></div>`;
}

function getFiltered(){
  let filtered=allMatches;
  const f = currentFilter;
  const norm = (s)=> (s||'').toLowerCase().trim();
  const lc = (m)=> norm(m.league_code);
  const ln = (m)=> norm(m.league);

  if(f==='top'){
    filtered=allMatches.filter(m=>m.confidence==='Alta'||m.confidence==='Media');
  } else if(f==='liga-mx'){
    filtered=allMatches.filter(m=>lc(m).includes('mex')||ln(m).includes('liga mx')||ln(m).includes('mexico'));
  } else if(f==='mls'){
    filtered=allMatches.filter(m=>lc(m).includes('usa')||ln(m).includes('mls'));
  } else if(f==='champions'){
    filtered=allMatches.filter(m=>lc(m).includes('champions')||ln(m).includes('champions'));
  } else if(f==='europa'){
    filtered=allMatches.filter(m=>['eng.1','esp.1','ita.1','ger.1','fra.1'].includes(lc(m)));
  } else if(f.startsWith('league:')){
    const code=f.split(':')[1];
    const codeNorm=norm(code);
    filtered=allMatches.filter(m=>{
      const c=lc(m);
      const n=ln(m);
      if(c===codeNorm) return true;
      if(codeNorm==='eng.fa') return c==='eng.fa' || n.includes('fa cup');
      if(codeNorm==='eng.1') return c==='eng.1' || (n.includes('premier league') && !n.includes('fa cup'));
      if(codeNorm==='esp.1') return c==='esp.1' || n.includes('la liga') || (n.includes('liga') && n.includes('españa'));
      if(codeNorm==='ita.1') return c==='ita.1' || n.includes('serie a');
      if(codeNorm==='ger.1') return c==='ger.1' || n.includes('bundesliga');
      if(codeNorm==='fra.1') return c==='fra.1' || n.includes('ligue 1');
      if(codeNorm==='mex.1') return c==='mex.1' || n.includes('liga mx') || n.includes('mexico');
      if(codeNorm==='usa.1') return c==='usa.1' || n.includes('mls');
      if(codeNorm==='bra.1') return c==='bra.1' || n.includes('brasil') || n.includes('brasileirão');
      if(codeNorm==='arg.1') return c==='arg.1' || n.includes('argentina');
      if(codeNorm==='uefa.champions') return c==='uefa.champions' || n.includes('champions league');
      if(codeNorm==='uefa.europa') return (c==='uefa.europa' || n.includes('europa league')) && !c.includes('conf');
      if(codeNorm==='uefa.europa.conf') return c==='uefa.europa.conf' || n.includes('conference');
      if(codeNorm==='concacaf.champions') return c.includes('concacaf') || n.includes('concachampions');
      return false;
    });
  } else if(f.startsWith('continent:')){
    const cont=f.split(':')[1];
    if(cont==='america'){
      filtered=allMatches.filter(m=>{
        const c=lc(m); const n=ln(m);
        return c.includes('mex')||c.includes('usa')||c.includes('bra')||c.includes('arg')||c.includes('concacaf')||n.includes('liga mx')||n.includes('mls')||n.includes('brasil')||n.includes('argentina')||n.includes('concachampions')||n.includes('mexico');
      });
    } else if(cont==='europa'){
      filtered=allMatches.filter(m=>{
        const c=lc(m); const n=ln(m);
        return c.includes('eng')||c.includes('esp')||c.includes('ita')||c.includes('ger')||c.includes('fra')||c.includes('uefa')||n.includes('premier')||n.includes('la liga')||n.includes('serie a')||n.includes('bundesliga')||n.includes('ligue 1')||n.includes('champions')||n.includes('europa league')||n.includes('conference');
      });
    }
  } else if(f.startsWith('country:')){
    const ctry=f.split(':')[1];
    if(ctry==='mx') filtered=allMatches.filter(m=>lc(m).includes('mex')||ln(m).includes('mexico')||ln(m).includes('liga mx'));
    else if(ctry==='usa') filtered=allMatches.filter(m=>lc(m).includes('usa')||lc(m).includes('concacaf')||ln(m).includes('mls'));
    else if(ctry==='eng') filtered=allMatches.filter(m=>lc(m).includes('eng')||ln(m).includes('premier')||ln(m).includes('fa cup'));
    else if(ctry==='esp') filtered=allMatches.filter(m=>lc(m).includes('esp')||ln(m).includes('la liga'));
    else if(ctry==='ita') filtered=allMatches.filter(m=>lc(m).includes('ita')||ln(m).includes('serie a'));
    else if(ctry==='ger') filtered=allMatches.filter(m=>lc(m).includes('ger')||ln(m).includes('bundesliga'));
    else if(ctry==='fra') filtered=allMatches.filter(m=>lc(m).includes('fra')||ln(m).includes('ligue'));
    else if(ctry==='uefa') filtered=allMatches.filter(m=>lc(m).startsWith('uefa')||ln(m).includes('champions')||ln(m).includes('europa')||ln(m).includes('conference'));
    else if(ctry==='br') filtered=allMatches.filter(m=>lc(m).includes('bra')||ln(m).includes('brasil'));
    else if(ctry==='ar') filtered=allMatches.filter(m=>lc(m).includes('arg')||ln(m).includes('argentina'));
  } else if(f==='search'){
    const q=norm($searchInput.value);
    const liga=$leagueSelect.value;
    if(!q&&liga==='all'){ filtered=[]; }
    else {
      filtered=allMatches.filter(m=>{
        const matchQ=!q||norm(m.home).includes(q)||norm(m.away).includes(q)||ln(m).includes(q);
        const matchLiga=liga==='all'||(m.league||'').includes(liga);
        return matchQ&&matchLiga;
      });
    }
  } else if(f==='aciertos'){
    filtered=allMatches.filter(m=>m.estado==='FINALIZADO'&&m.acierto===true);
  } else if(f==='fallos'){
    filtered=allMatches.filter(m=>m.estado==='FINALIZADO'&&m.acierto===false);
  } else if(f==='combinada'){
    filtered=allMatches.filter(m=>m.confidence==='Alta'||m.confidence==='Media').slice(0,6);
  } else if(f==='progol'){
    filtered=allMatches.slice(0,14);
  } else if(f==='analytics'){
    filtered=allMatches;
  }
  // FIX DEDUP final antes de devolver
  const seenFinal={};
  filtered = filtered.filter(m=>{
    const key = `${m.date||''}_${(m.league_code||'').toLowerCase()}_${(m.home||'').toLowerCase()}_${(m.away||'').toLowerCase()}`;
    if(seenFinal[key]) return false;
    seenFinal[key]=true;
    return true;
  });
  return filtered;
}

function groupByEstado(matches){
  const enJuego=matches.filter(m=>m.estado==='EN_JUEGO');
  const programados=matches.filter(m=>m.estado==='PROGRAMADO'||!m.estado);
  const finalizados=matches.filter(m=>m.estado==='FINALIZADO');
  return {enJuego,programados,finalizados};
}

function renderSection(title,matches){
  if(matches.length===0) return '';
  let html='';
  if(title.includes('Finalizados')){
    const aciertos=matches.filter(m=>m.acierto===true).length;
    const fallos=matches.filter(m=>m.acierto===false).length;
    html+=`<div class="section-title finalizados-header"><span>${title}</span><div class="filter-mini"><button class="mini-filter acierto" onclick="setFilterAciertos()">✅ Aciertos (${aciertos})</button><button class="mini-filter fallo" onclick="setFilterFallos()">❌ Fallos (${fallos})</button></div></div>`;
  } else {
    html+=`<div class="section-title">${title}</div>`;
  }
  html+=matches.map(cardA).join('');
  return html;
}

function resetToAll(){
  document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active'));
  const btn=document.querySelector('[data-filter="all"]');
  if(btn) btn.classList.add('active');
  currentFilter='all';
  renderAll();
}

function renderAll(){
  try{
    const filtered=getFiltered();
    // ANALYTICS - SOLO ANALYTICS, SIN TARJETAS
    if(currentFilter==='analytics'){
      const finalizados = filtered.filter(m=>m.estado==='FINALIZADO');
      const aciertos = finalizados.filter(m=>m.acierto===true).length;
      const fallos = finalizados.filter(m=>m.acierto===false).length;
      const total = finalizados.length;
      const pct = total>0?Math.round(aciertos/total*100):0;
      $grid.innerHTML = renderAnalytics(filtered) + renderAnalyticsExtended(filtered);
      $countBadge.textContent = `📊 ${total} finalizados - ${aciertos}✅ ${fallos}❌ - ${pct}% acierto`;
      return;
    }
    $countBadge.textContent=`${filtered.length} partidos / ${allMatches.length} total`;
    if(currentFilter==='search'){
      const q=$searchInput.value;
      if(!q){
        $grid.innerHTML=`<div class="search-google-empty"><div class="search-google-icon">🔍</div><h2>Busca un equipo o liga</h2><p>Escribe Atlas, América, Liga MX...</p></div>`;
        return;
      }
      let html=`<div class="section-title">🔍 Resultados para "${esc(q)}" (${filtered.length})</div>`;
      const groups=groupByEstado(filtered);
      if(groups.enJuego.length>0) html+=renderSection(`🔴 En Juego (${groups.enJuego.length})`,groups.enJuego);
      if(groups.programados.length>0) html+=renderSection(`⏰ Programados (${groups.programados.length})`,groups.programados);
      if(groups.finalizados.length>0) html+=renderSection(`✅ Finalizados (${groups.finalizados.length})`,groups.finalizados);
      if(groups.enJuego.length===0&&groups.programados.length===0&&groups.finalizados.length===0) html+=filtered.map(cardA).join('');
      $grid.innerHTML=html;
      return;
    }
    const {enJuego,programados,finalizados}=groupByEstado(filtered);
    let html='';
    if(filtered.length===0 && allMatches.length>0){
      let emptyMsg = `<div class="empty-state"><div class="empty-icon">⚽</div><h3>No hay partidos de ${esc(currentFilter.replace('league:','').replace('continent:','').replace('country:',''))} hoy (${$dateInput.value})</h3><p>Hay ${allMatches.length} partidos totales en otras ligas.</p><button class="primary" onclick="resetToAll()">Ver todos los partidos del día</button></div>`;
      if(currentFilter==='search'){
        emptyMsg = `<div class="empty-state"><div class="empty-icon">🔍</div><h3>No se encontraron resultados</h3><p>Intenta con otro equipo o liga.</p></div>`;
      }
      $grid.innerHTML = emptyMsg;
      return;
    }
    if(currentFilter==='all'){
      html+=`<div class="section-title">⊙ Partidos del día (${filtered.length} partidos - 15 ligas mundiales)</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`⏰ Programados (${programados.length})`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados);
      if(enJuego.length===0&&programados.length===0&&finalizados.length===0) html+=filtered.map(cardA).join('');
    } else if(currentFilter==='top'){
      html+=`<div class="section-title">★ Top Picks - Alta/Media confianza (${filtered.length})</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`⏰ Programados (${programados.length})`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados);
    } else if(currentFilter==='combinada'){
      html+=`<div class="section-title">∽ Combinadas (${filtered.length} selecciones)</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`⏰ Programados (${programados.length})`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados);
    } else if(currentFilter==='progol'){
      html+=`<div class="section-title">▤ Progol - 14 partidos (quiniela mexicana)</div>`;
      html+=filtered.map((m,i)=>`<div class="card progol"><div class="progol-num">${i+1}</div>`+cardA(m)+`</div>`).join('');
    } else if(currentFilter==='aciertos'){
      html+=`<div class="section-title">✅ Aciertos (${filtered.length})</div>`;
      html+=filtered.map(cardA).join('');
    } else if(currentFilter==='fallos'){
      html+=`<div class="section-title">❌ Fallos (${filtered.length})</div>`;
      html+=filtered.map(cardA).join('');
    } else {
      const titleMap={
        'liga-mx':'🇲🇽 Liga MX','mls':'🇺🇸 MLS','champions':'🏆 Champions League','europa':'🏅 Top 5 Europa',
        'league:mex.1':'🇲🇽 Liga MX - México','league:usa.1':'🇺🇸 MLS - USA','league:bra.1':'🇧🇷 Brasileirão - Brasil','league:arg.1':'🇦🇷 Liga Argentina',
        'league:eng.1':'🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League','league:eng.fa':'🏴󠁧󠁢󠁥󠁮󠁧󠁿 FA Cup','league:esp.1':'🇪🇸 La Liga','league:ita.1':'🇮🇹 Serie A','league:ger.1':'🇩🇪 Bundesliga','league:fra.1':'🇫🇷 Ligue 1',
        'league:uefa.champions':'🏆 Champions League','league:uefa.europa':'Europa League','league:uefa.europa.conf':'Conference League','league:concacaf.champions':'Concachampions',
        'continent:america':'🌎 América','continent:europa':'🌍 Europa',
        'analytics':'📊 Estadísticas'
      };
      const t = titleMap[currentFilter] || currentFilter.replace('league:','').replace('continent:','').replace('country:','');
      html+=`<div class="section-title">${t} (${filtered.length} partidos)</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`⏰ Programados (${programados.length})`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados);
      if(enJuego.length===0&&programados.length===0&&finalizados.length===0) html+=filtered.map(cardA).join('');
    }
    html+=`<div class="section-title">📊 Transparencia</div><div class="card"><div class="meta">Probabilidad != recomendación segura. Suma 1X2 ~100% validado.</div><div class="meta">Versión: V71 SOLO Analytics - sin tarjetas - FIX Europa y FA Cup</div></div>`;
    $grid.innerHTML=html;
  }catch(e){
    log(`RENDER ERROR: ${e.message}`,'err');
    $grid.innerHTML=`<div class="card"><div class="meta" style="color:#ff6b6b">Error render: ${esc(e.message)}</div></div>`;
  }
}

function setFilterAciertos(){
  document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active'));
  const btn=document.querySelector('[data-filter="aciertos"]');
  if(btn) btn.classList.add('active');
  currentFilter='aciertos';
  renderAll();
}
function setFilterFallos(){
  document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active'));
  const btn=document.querySelector('[data-filter="fallos"]');
  if(btn) btn.classList.add('active');
  currentFilter='fallos';
  renderAll();
}


// PASO 8: Temporada completa por liga
async function loadSeasonAll(){
  $status.textContent=`Cargando temporada completa 15 ligas...`;
  try{
    const data=await api(`/api/calendar/season?limit=1000`);
    allMatches=data.matches||[];
    allMatches.sort((a,b)=>{
      const da = (a.date||'') + ' ' + (a.time||'');
      const db = (b.date||'') + ' ' + (b.time||'');
      return db.localeCompare(da);
    });
    $status.textContent=`✅ Temporada completa: ${data.count} partidos - ${data.dates?data.dates.length+' fechas':''}`;
    log(`Temporada: ${data.count} partidos`, 'ok');
    renderAll();
  }catch(e){
    $status.textContent=`Error temporada: ${e.message}`;
    loadFast();
  }
}

async function loadSeasonLeague(leagueCode){
  $status.textContent=`Cargando temporada ${leagueCode}...`;
  try{
    const data=await api(`/api/calendar/season/league?league=${leagueCode}&limit=500`);
    // Si estamos en vista de liga, reemplazar solo los de esa liga o merge?
    // Merge con allMatches para no perder otras ligas
    let nuevos = data.matches||[];
    // FIX DEDUP FRONTEND: eliminar duplicados por fecha+liga+equipos
    const seenF = {};
    nuevos = nuevos.filter(m=>{
      const key = `${m.date||''}_${(m.league_code||'').toLowerCase()}_${(m.home||'').toLowerCase()}_${(m.away||'').toLowerCase()}`;
      if(seenF[key]) return false;
      seenF[key]=true;
      return true;
    });
    // Actualizar allMatches: quitar viejos de esa liga y agregar nuevos sin duplicar
    const otros = allMatches.filter(m=> (m.league_code||'').toLowerCase()!==leagueCode.toLowerCase());
    allMatches = [...otros, ...nuevos];
    // Dedup global final
    const seenG={};
    allMatches = allMatches.filter(m=>{
      const key = `${m.date||''}_${(m.league_code||'').toLowerCase()}_${(m.home||'').toLowerCase()}_${(m.away||'').toLowerCase()}`;
      if(seenG[key]) return false;
      seenG[key]=true;
      return true;
    });
    allMatches.sort((a,b)=>{
      const da = (a.date||'') + ' ' + (a.time||'');
      const db = (b.date||'') + ' ' + (b.time||'');
      return db.localeCompare(da);
    });
    $status.textContent=`✅ ${leagueCode}: ${data.count} partidos temporada`;
    log(`${leagueCode} temporada: ${data.count}`, 'ok');
    renderAll();
  }catch(e){
    $status.textContent=`Error temporada ${leagueCode}: ${e.message}`;
  }
}

async function syncTemporadaCompleta(){
  $status.textContent=`Sincronizando temporada 15 ligas (2-3 min)...`;
  try{
    await api(`/api/calendar/sync_season`);
    log('Sincronización temporada iniciada, espera 2-3 min y luego Cargar temporada', 'ok');
    setTimeout(loadSeasonAll, 120000);
  }catch(e){
    $status.textContent=`Error sync temporada: ${e.message}`;
  }
}

async function loadCountByLeague(){
  try{
    const data=await api(`/api/calendar/count_by_league`);
    log(`Ligas en BD: ${data.leagues.map(l=>l.league_code+':'+l.c).join(', ')}`, 'ok');
  }catch(e){}
}


async function loadFast(){
  const date=$dateInput.value||new Date().toLocaleDateString('en-CA');
  $status.textContent=`Cargando ${date} - 15 ligas...`;
  try{
    const data=await api(`/api/calendar/fast?date=${date}`);
    allMatches=data.matches||[];
    $status.textContent=`${data.count} partidos reales de ${date} - ${data.source||''}`;
    renderAll();
  }catch(e){ $status.textContent=`Error: ${e.message}`; }
}
async function refresh(){
  const date=$dateInput.value||new Date().toLocaleDateString('en-CA');
  $status.textContent=`Sincronizando ${date}...`;
  try{
    await api(`/api/calendar?refresh=1&date=${date}`);
    setTimeout(loadFast, 3000);
  }catch(e){ $status.textContent=`Error sync: ${e.message}`; }
}

// Delegación para menú árbol
document.addEventListener('click', async (e)=>{
  const btn = e.target.closest('.menu-item');
  if(!btn) return;
  if(!btn.dataset.filter) return;
  document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  currentFilter=btn.dataset.filter;
  if(currentFilter==='search') $searchBox.style.display='block';
  else $searchBox.style.display='none';
  
  // PASO 8: Si es liga específica y tenemos pocos partidos de esa liga, cargar temporada de esa liga
  if(currentFilter.startsWith('league:')){
    const code = currentFilter.split(':')[1];
    const countLiga = allMatches.filter(m=> (m.league_code||'').toLowerCase()===code.toLowerCase()).length;
    if(countLiga < 10){
      await loadSeasonLeague(code);
      return;
    }
  }
  // Si es continente y tenemos pocos, cargar temporada completa
  if(currentFilter.startsWith('continent:') && allMatches.length < 50){
    await loadSeasonAll();
    return;
  }
  
  renderAll();
  if(window.innerWidth<800) document.querySelector('.main').scrollTop=0;
});

$searchInput.addEventListener('input',renderAll);
$leagueSelect.addEventListener('change',renderAll);
document.getElementById('loadBtn').addEventListener('click',loadSeasonAll);
document.getElementById('refreshBtn').addEventListener('click',()=>{ if(confirm('¿Sincronizar temporada completa 15 ligas? Tarda 2-3 min')) syncTemporadaCompleta(); else refresh(); });

(async()=>{
  $dateInput.value=new Date().toLocaleDateString('en-CA');
  try{
    const h=await api('/api/health');
    $status.textContent=`API: ${h.version} - ${h.records} partidos - Cargando temporada...`;
    await loadCountByLeague();
    // Si hay pocos partidos en BD, cargar temporada completa automaticamente
    if(h.records < 100){
      await loadSeasonAll();
    } else {
      loadFast();
    }
  }catch{ $status.textContent='API no conecta.'; }
})();
