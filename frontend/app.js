
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
let customCombinada = [];
let _lastTopAlta = [];
let _lastTopMedia = [];

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
const REVANCHA_REAL = [
  {n:1, home:'MONTERREY', away:'TIJUANA'},
  {n:2, home:'GUADALAJARA', away:'ATLANTE'},
  {n:3, home:'S. LAGUNA', away:'NECAXA'},
  {n:4, home:'C. AZUL', away:'LEON'},
  {n:5, home:'GETAFE', away:'SEVILLA'},
  {n:6, home:'CHELSEA', away:'MAN. UNITED'},
  {n:7, home:'AJAX', away:'AZ ALKMAAR'}
];

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
function renderAnalyticsExtended(matches){
  const a=calcAnalytics(matches);
  const finalizados=matches.filter(m=>m.estado==='FINALIZADO'), enJuego=matches.filter(m=>m.estado==='EN_JUEGO'), programados=matches.filter(m=>m.estado==='PROGRAMADO');
  const aciertos=finalizados.filter(m=>m.acierto===true).length, fallos=finalizados.filter(m=>m.acierto===false).length;
  const pct=finalizados.length>0?Math.round(aciertos/finalizados.length*100):0;
  const cs=a.confStats;
  if(finalizados.length===0) return '';
  return `<div class="analytics-panel"><div class="analytics-grid"><div class="analytics-card"><div class="analytics-title">⚽ Estado</div><div class="analytics-value">🔴 ${enJuego.length} En Juego | ⏰ ${programados.length} Programados | ✅ ${finalizados.length} Finalizados</div></div><div class="analytics-card"><div class="analytics-title">🎯 Acierto Global</div><div class="analytics-value" style="font-size:22px">${pct}% - ${aciertos}✅ / ${fallos}❌ de ${finalizados.length}</div></div><div class="analytics-card wide"><div class="analytics-title">📊 Detalle por confianza</div><div class="conf-analytics" style="gap:10px"><div class="conf-detail"><div class="conf-row alta"><span class="conf-dot" style="background:#1ee07a"></span><b>Alta:</b> ${cs.Alta.total} → ${cs.Alta.aciertos}✅ / ${cs.Alta.fallos}❌ - ${cs.Alta.total>0?Math.round(cs.Alta.aciertos/cs.Alta.total*100):0}%</div></div><div class="conf-detail"><div class="conf-row media"><span class="conf-dot" style="background:#f5d547"></span><b>Media:</b> ${cs.Media.total} → ${cs.Media.aciertos}✅ / ${cs.Media.fallos}❌ - ${cs.Media.total>0?Math.round(cs.Media.aciertos/cs.Media.total*100):0}%</div></div><div class="conf-detail"><div class="conf-row limitada"><span class="conf-dot" style="background:#ff6b6b"></span><b>Limitada:</b> ${cs.Limitada.total} → ${cs.Limitada.aciertos}✅ / ${cs.Limitada.fallos}❌ - ${cs.Limitada.total>0?Math.round(cs.Limitada.aciertos/cs.Limitada.total*100):0}%</div></div></div></div><div class="analytics-card wide"><div class="analytics-title">📈 Resumen por liga</div><div class="liga-table">${Object.entries(a.porLiga).map(([liga,data])=>`<div class="liga-row"><span>${liga}</span><span>${data.aciertos}✅ ${data.fallos}❌ (${data.total})</span><span class="pct ${data.aciertos>=data.fallos?'ok':'err'}">${data.total>0?Math.round(data.aciertos/data.total*100):0}%</span></div>`).join('')}</div></div></div></div>`;
}
function findMatchForProgol(home, away){
  const nh = (home||'').toLowerCase().trim();
  const na = (away||'').toLowerCase().trim();
  const sources = [...allMatches, ...SEASON_CACHE];
  // Normaliza nombres para TuLotero: PUMAS -> Pumas UNAM, AGUILAS -> America, etc.
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
  // 1er intento: match exacto difuso
  let found = sources.find(m=>{
    const h=(m.home||'').toLowerCase();
    const a=(m.away||'').toLowerCase();
    return (h.includes(normHome) || normHome.includes(h) || h.includes(nh) || nh.includes(h.slice(0,5))) && 
           (a.includes(normAway) || normAway.includes(a) || a.includes(na) || na.includes(a.slice(0,5)));
  });
  if(found) return found;
  // 2do intento: solo home o away
  found = sources.find(m=>{
    const h=(m.home||'').toLowerCase();
    const a=(m.away||'').toLowerCase();
    return (h.includes(normHome) && a.includes(normAway.slice(0,3))) || (a.includes(normAway) && h.includes(normHome.slice(0,3)));
  });
  return found||null;
}
function cardA(m){
  const p=m.probabilities||{"1":0,"X":0,"2":0};
  const total=(p['1']+p['X']+p['2']).toFixed(1);
  const iconPath=`icons/${m.league_code||'default'}.svg`;
  const fallbackEmoji=m.league_code==='mex.1'?'🇲🇽':m.league_code==='usa.1'?'🇺🇸':m.league_code==='eng.1'?'🏴󠁧󠁢󠁥󠁮󠁧󠁿':m.league_code?.includes('champions')?'🏆':'⚽';
  let badgeHtml='';
  if(m.estado==='FINALIZADO'){ if(m.acierto===true) badgeHtml='<span class="estado-tag estado-acierto">✅ Acertó</span>'; else if(m.acierto===false) badgeHtml='<span class="estado-tag estado-fallo">❌ Falló</span>'; else badgeHtml='<span class="estado-tag estado-finalizado">✅ Finalizado</span>'; }
  else if(m.estado==='EN_JUEGO'){ badgeHtml='<span class="estado-tag estado-en_juego">🔴 En Juego</span>'; }
  else { badgeHtml='<span class="estado-tag estado-programado">⏰ Programado</span>'; }
  let scoreHtml=''; if(m.estado!=='PROGRAMADO' && m.home_score!=null && m.away_score!=null){ scoreHtml=`<div class="score-row"><span class="score">${m.home_score} - ${m.away_score}</span></div>`; }
  const confColor=m.confidence==='Alta'?'#1ee07a':m.confidence==='Media'?'#f5d547':'#ff6b6b';
  const confIcon=m.confidence==='Alta'?'icons/conf-alta.svg':m.confidence==='Media'?'icons/conf-media.svg':'icons/conf-limitada.svg';
  const confHtml=m.confidence?`<span class="conf-badge conf-${m.confidence.toLowerCase()}"><img src="${confIcon}" class="conf-icon" alt=""><span class="conf-dot" style="background:${confColor}"></span>Conf: ${esc(m.confidence)}</span>`:'';
  const key=m._key||`${m.date}_${m.home}_${m.away}`;
  const isSel=customCombinada.some(c=> (c._key||`${c.date}_${c.home}_${c.away}`)===key);
  const isCombinadaMode=currentFilter==='combinada';
  const addBtn=isCombinadaMode?`<button class="mini-filter ${isSel?'acierto':''}" style="margin-top:6px; width:100%" onclick="event.stopPropagation(); toggleCombinada('${key.replace(/'/g,"\\'")}')">${isSel?'✅ En tu combinada - Quitar':'➕ Agregar a mi combinada'}</button>`:'';
  const borderStyle=isCombinadaMode&&isSel?'border:2px solid #1ee07a; box-shadow:0 0 12px rgba(30,224,122,0.4)':'';
  return `<div class="card" style="${borderStyle}" data-league="${esc(m.league||'')}" data-home="${esc(m.home||'')}" data-away="${esc(m.away||'')}" data-estado="${esc(m.estado||'PROGRAMADO')}" data-acierto="${m.acierto===true?'acierto':m.acierto===false?'fallo':''}"><div class="badge-row"><span class="tag"><img src="${iconPath}" class="league-icon" onerror="this.style.display='none';this.nextElementSibling.style.display='inline'"><span style="display:none">${fallbackEmoji}</span> ${esc(m.league_code||'')}</span>${badgeHtml}</div><div class="league">${esc(m.league||'Futbol')} • ${esc(m.time||'')} • ${esc(m.date||'')}</div><div class="teams">${esc(m.home)} <span style="color:#8aa0c8">vs</span> ${esc(m.away)}</div>${scoreHtml}<div class="prob-row"><span class="prob">L: ${p['1']}%</span><span class="prob">E: ${p['X']}%</span><span class="prob">V: ${p['2']}%</span><span class="total">Σ ${total}%</span></div><div class="meta fav-conf-row"><span>⭐ Favorito: <b>${esc(m.favorite||'')}</b></span>${confHtml}</div>${addBtn}</div>`;
}
function getFiltered(){
  let filtered=allMatches;
  const f=currentFilter;
  const selectedDate=$dateInput.value||new Date().toLocaleDateString('en-CA');
  const norm=(s)=>(s||'').toLowerCase().trim();
  const lc=(m)=>norm(m.league_code);
  const ln=(m)=>norm(m.league);
  if(f==='all'){ filtered=allMatches.filter(m=> (m.date||'').startsWith(selectedDate)); }
  else if(f==='top'){ let base=allMatches.filter(m=> (m.date||'').startsWith(selectedDate)); if(base.length===0) base=allMatches; filtered=base.filter(m=> m.confidence==='Alta'||m.confidence==='Media'); const order={Alta:0,Media:1}; filtered.sort((a,b)=>{const ca=order[a.confidence]??2,cb=order[b.confidence]??2; if(ca!==cb) return ca-cb; return (b.date||'').localeCompare(a.date||'');}); }
  else if(f==='liga-mx'){ filtered=allMatches.filter(m=>lc(m).includes('mex')||ln(m).includes('liga mx')||ln(m).includes('mexico')); }
  else if(f==='mls'){ filtered=allMatches.filter(m=>lc(m).includes('usa')||ln(m).includes('mls')); }
  else if(f==='champions'){ filtered=allMatches.filter(m=>lc(m).includes('champions')||ln(m).includes('champions')); }
  else if(f==='europa'){ filtered=allMatches.filter(m=>['eng.1','esp.1','ita.1','ger.1','fra.1'].includes(lc(m))); }
  else if(f.startsWith('league:')){ const code=f.split(':')[1]; const codeNorm=norm(code); filtered=allMatches.filter(m=>{const c=lc(m),n=ln(m); if(c===codeNorm) return true; if(codeNorm==='eng.fa') return c==='eng.fa'||n.includes('fa cup'); if(codeNorm==='eng.1') return c==='eng.1'||(n.includes('premier league')&&!n.includes('fa cup')); if(codeNorm==='esp.1') return c==='esp.1'||n.includes('la liga')||(n.includes('liga')&&n.includes('españa')); if(codeNorm==='ita.1') return c==='ita.1'||n.includes('serie a'); if(codeNorm==='ger.1') return c==='ger.1'||n.includes('bundesliga'); if(codeNorm==='fra.1') return c==='fra.1'||n.includes('ligue 1'); if(codeNorm==='mex.1') return c==='mex.1'||n.includes('liga mx')||n.includes('mexico'); if(codeNorm==='usa.1') return c==='usa.1'||n.includes('mls'); if(codeNorm==='bra.1') return c==='bra.1'||n.includes('brasil')||n.includes('brasileirão'); if(codeNorm==='arg.1') return c==='arg.1'||n.includes('argentina'); if(codeNorm==='uefa.champions') return c==='uefa.champions'||n.includes('champions league'); if(codeNorm==='uefa.europa') return (c==='uefa.europa'||n.includes('europa league'))&&!c.includes('conf'); if(codeNorm==='uefa.europa.conf') return c==='uefa.europa.conf'||n.includes('conference'); if(codeNorm==='concacaf.champions') return c.includes('concacaf')||n.includes('concachampions'); return false;}); }
  else if(f.startsWith('continent:')){ const cont=f.split(':')[1]; if(cont==='america'){ filtered=allMatches.filter(m=>{const c=lc(m),n=ln(m); return c.includes('mex')||c.includes('usa')||c.includes('bra')||c.includes('arg')||c.includes('concacaf')||n.includes('liga mx')||n.includes('mls')||n.includes('brasil')||n.includes('argentina')||n.includes('concachampions')||n.includes('mexico');}); } else if(cont==='europa'){ filtered=allMatches.filter(m=>{const c=lc(m),n=ln(m); return c.includes('eng')||c.includes('esp')||c.includes('ita')||c.includes('ger')||c.includes('fra')||c.includes('uefa')||n.includes('premier')||n.includes('la liga')||n.includes('serie a')||n.includes('bundesliga')||n.includes('ligue 1')||n.includes('champions')||n.includes('europa league')||n.includes('conference');}); } }
  else if(f==='search'){ const q=norm($searchInput.value); const liga=$leagueSelect.value; if(!q&&liga==='all'){ filtered=[]; } else { filtered=allMatches.filter(m=>{const matchQ=!q||norm(m.home).includes(q)||norm(m.away).includes(q)||ln(m).includes(q); const matchLiga=liga==='all'||(m.league||'').includes(liga); return matchQ&&matchLiga;}); } }
  else if(f==='aciertos'){ filtered=allMatches.filter(m=>m.estado==='FINALIZADO'&&m.acierto===true); }
  else if(f==='fallos'){ filtered=allMatches.filter(m=>m.estado==='FINALIZADO'&&m.acierto===false); }
  else if(f==='combinada'){ let base=allMatches.filter(m=> (m.date||'').startsWith(selectedDate)); if(base.length<4) base=allMatches; filtered=base.filter(m=> m.confidence==='Alta'||m.confidence==='Media'); const order={Alta:0,Media:1}; filtered.sort((a,b)=>{const ca=order[a.confidence]??2,cb=order[b.confidence]??2; if(ca!==cb) return ca-cb; return Math.max(b.probabilities?.['1']||0,b.probabilities?.['X']||0,b.probabilities?.['2']||0)-Math.max(a.probabilities?.['1']||0,a.probabilities?.['X']||0,a.probabilities?.['2']||0);}); }
  else if(f==='progol'){ filtered=allMatches; }
  else if(f==='analytics'){ filtered=allMatches; }
  const seenFinal={}; filtered=filtered.filter(m=>{const key=`${m.date||''}_${(m.league_code||'').toLowerCase()}_${(m.home||'').toLowerCase()}_${(m.away||'').toLowerCase()}`; if(seenFinal[key]) return false; seenFinal[key]=true; m._key=key; return true;}); return filtered;
}
function groupByEstado(matches){ const enJuego=matches.filter(m=>m.estado==='EN_JUEGO'); const programados=matches.filter(m=>m.estado==='PROGRAMADO'||!m.estado); const finalizados=matches.filter(m=>m.estado==='FINALIZADO'); return {enJuego,programados,finalizados}; }
function renderSection(title,matches){ if(matches.length===0) return ''; let html=''; if(title.includes('Finalizados')){ const aciertos=matches.filter(m=>m.acierto===true).length, fallos=matches.filter(m=>m.acierto===false).length; html+=`<div class="section-title finalizados-header"><span>${title}</span><div class="filter-mini"><button class="mini-filter acierto" onclick="setFilterAciertos()">✅ Aciertos (${aciertos})</button><button class="mini-filter fallo" onclick="setFilterFallos()">❌ Fallos (${fallos})</button></div></div>`; } else { html+=`<div class="section-title">${title}</div>`; } const order={Alta:0,Media:1,Limitada:2}; const sorted=[...matches].sort((a,b)=>{const ca=order[a.confidence]??2,cb=order[b.confidence]??2; if(ca!==cb) return ca-cb; return (b.date||'').localeCompare(a.date||'');}); html+=sorted.map(cardA).join(''); return html; }
function resetToAll(){ document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active')); const btn=document.querySelector('[data-filter="all"]'); if(btn) btn.classList.add('active'); currentFilter='all'; renderAll(); }
function renderProgolReal(){
  var metaF = (typeof PROGOL_META!=='undefined' && PROGOL_META.fecha) ? PROGOL_META.fecha : '30 oct.';
  var metaH = (typeof PROGOL_META!=='undefined' && PROGOL_META.hasta) ? 'hasta '+PROGOL_META.hasta : '';
  var metaSrc = (typeof PROGOL_META!=='undefined' && PROGOL_META.fuente) ? PROGOL_META.fuente : 'TuLotero';
  let html='<div class="section-title">▤ Progol - Quiniela Lotería Nacional '+metaF+' '+metaH+' (14 + Revancha 7) - '+metaSrc+' - Auto</div>';
  html+=`<div class="analytics-panel"><div class="analytics-card wide" style="background:#0a1a2e; border:2px solid #d4af37"><div class="analytics-title">🎫 Boleta Progol Oficial - L/E/V | LiAn sugiere con prob</div><div class="analytics-value" style="font-size:13px">Marca L=Local, E=Empate, V=Visitante. LiAn usa Poisson 58% + ELO 16% + Forma 10% + MonteCarlo 16% para sugerir. Dobles/Triples aumentan chance. Revancha opcional 7 partidos.</div></div></div>`;
  
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
        // Estimado sin datos
        p={L:40,E:28,V:32}; pick='L'; fav=item.home; conf='Estimado';
      }
      const pickColor=pick==='L'?'#1ee07a':pick==='E'?'#f5d547':'#ff6b6b';
      const confIcon=conf==='Alta'?'icons/conf-alta.svg':conf==='Media'?'icons/conf-media.svg':'icons/conf-limitada.svg';
      h+=`<div class="card progol-row" style="display:flex; align-items:center; gap:10px; padding:10px; border-left:4px solid ${pickColor}">
        <div style="background:#1a2a4a; color:#fff; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:13px; flex-shrink:0">${item.n}</div>
        <div style="display:flex; gap:6px; flex-shrink:0">
          <button style="width:32px; height:28px; border-radius:6px; border:2px solid ${pick==='L'?pickColor:'#2a3a5a'}; background:${pick==='L'?pickColor:'#0f1a33'}; color:${pick==='L'?'#000':'#8aa0c8'}; font-weight:900; font-size:12px">L</button>
          <button style="width:32px; height:28px; border-radius:6px; border:2px solid ${pick==='E'?pickColor:'#2a3a5a'}; background:${pick==='E'?pickColor:'#0f1a33'}; color:${pick==='E'?'#000':'#8aa0c8'}; font-weight:900; font-size:12px">E</button>
          <button style="width:32px; height:28px; border-radius:2px; border:2px solid ${pick==='V'?pickColor:'#2a3a5a'}; background:${pick==='V'?pickColor:'#0f1a33'}; color:${pick==='V'?'#fff':'#8aa0c8'}; font-weight:900; font-size:12px">V</button>
        </div>
        <div style="flex:1; min-width:0">
          <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap">
            <span style="font-weight:700; font-size:13px">${esc(item.home)} <span style="color:#8aa0c8">vs</span> ${esc(item.away)}</span>
            <span style="font-size:11px; color:#8aa0c8">Sugerido: <b style="color:${pickColor}">${pick} → ${esc(fav)} (${maxP.toFixed(1)}%)</b> - Conf: ${esc(conf)}</span>
          </div>
          <div style="display:flex; gap:6px; margin-top:4px; font-size:10px; color:#8aa0c8">
            <span>L:${p.L.toFixed(1)}%</span><span>E:${p.E.toFixed(1)}%</span><span>V:${p.V.toFixed(1)}%</span>
            ${match?`<span style="color:${pickColor}">• ${esc(match.league||'')}</span>`:''}
            ${match && match.estado==='FINALIZADO'?`<span style="color:${match.acierto===true?'#1ee07a':'#ff6b6b'}">${match.home_score}-${match.away_score} ${match.acierto===true?'✅':match.acierto===false?'❌':''}</span>`:''}
          </div>
        </div>
      </div>`;
    });
    h+=`</div></div>`;
    return h;
  }
  
  html+=renderProgolList(PROGOL_REAL, 'PROGOL - 14 PARTIDOS');
  html+=renderProgolList(REVANCHA_REAL, 'REVANCHA (OPCIONAL) - 7 PARTIDOS');
  
  // Resumen copiar
  html+=`<div class="analytics-panel"><div class="analytics-card wide" style="background:#0a1a2e; border:1px solid #d4af37"><div class="analytics-title">📋 Resumen Boleta Progol - Copiar para TuLotero</div><div class="analytics-value" style="font-family:monospace; font-size:12px; line-height:1.6">`;
  PROGOL_REAL.forEach(item=>{
    const m=findMatchForProgol(item.home, item.away);
    let pick='L'; if(m){ const p=m.probabilities||{'1':33,'X':33,'2':33}; if(p['X']>p['1']&&p['X']>p['2']) pick='E'; else if(p['2']>p['1']&&p['2']>p['X']) pick='V'; }
    html+=`${item.n}. ${item.home} vs ${item.away} → ${pick}<br>`;
  });
  html+=`<br>REVANCHA:<br>`;
  REVANCHA_REAL.forEach(item=>{
    const m=findMatchForProgol(item.home, item.away);
    let pick='L'; if(m){ const p=m.probabilities||{'1':33,'X':33,'2':33}; if(p['X']>p['1']&&p['X']>p['2']) pick='E'; else if(p['2']>p['1']&&p['2']>p['X']) pick='V'; }
    html+=`${item.n}. ${item.home} vs ${item.away} → ${pick}<br>`;
  });
  html+=`</div><button class="mini-filter" style="background:#d4af37; color:#000; margin-top:8px" onclick="navigator.clipboard.writeText(\`${PROGOL_REAL.map(i=>i.n+'. '+i.home+' vs '+i.away).join('\\n')}\\n\\nREVANCHA:\\n${REVANCHA_REAL.map(i=>i.n+'. '+i.home+' vs '+i.away).join('\\n')}\`); alert('Progol copiado!')">📋 Copiar Progol 14 + Revancha 7</button></div></div>`;
  
  return html;
}
function renderAll(){
  try{
    const filtered=getFiltered();
    if(currentFilter==='analytics'){ const finalizados=filtered.filter(m=>m.estado==='FINALIZADO'); const aciertos=finalizados.filter(m=>m.acierto===true).length, fallos=finalizados.filter(m=>m.acierto===false).length, total=finalizados.length, pct=total>0?Math.round(aciertos/total*100):0; $grid.innerHTML=renderAnalytics(filtered)+renderAnalyticsExtended(filtered); $countBadge.textContent=`📊 ${total} finalizados - ${aciertos}✅ ${fallos}❌ - ${pct}% acierto`; return; }
    $countBadge.textContent=`${filtered.length} partidos / ${allMatches.length} total`;
    if(currentFilter==='search'){
      const q=$searchInput.value; if(!q){ $grid.innerHTML=`<div class="search-google-empty"><div class="search-google-icon">🔍</div><h2>Busca un equipo o liga</h2><p>Escribe Atlas, América, Liga MX...</p></div>`; return; }
      let html=`<div class="section-title">🔍 Resultados para "${esc(q)}" (${filtered.length})</div>`; const groups=groupByEstado(filtered); if(groups.enJuego.length>0) html+=renderSection(`🔴 En Juego (${groups.enJuego.length})`,groups.enJuego); if(groups.programados.length>0) html+=renderSection(`⏰ Programados (${groups.programados.length})`,groups.programados); if(groups.finalizados.length>0) html+=renderSection(`✅ Finalizados (${groups.finalizados.length})`,groups.finalizados); if(groups.enJuego.length===0&&groups.programados.length===0&&groups.finalizados.length===0) html+=filtered.map(cardA).join(''); $grid.innerHTML=html; return;
    }
    const {enJuego,programados,finalizados}=groupByEstado(filtered);
    let html='';
    if(filtered.length===0 && allMatches.length>0 && currentFilter!=='progol'){
      let emptyMsg=`<div class="empty-state"><div class="empty-icon">⚽</div><h3>No hay partidos de ${esc(currentFilter.replace('league:','').replace('continent:','').replace('country:',''))} para ${$dateInput.value}</h3><p>Hay ${allMatches.length} partidos totales en otras fechas/ligas.</p><button class="primary" onclick="resetToAll()">Ver partidos del día</button></div>`;
      $grid.innerHTML=emptyMsg; return;
    }
    if(currentFilter==='all'){
      const selDate=$dateInput.value||new Date().toLocaleDateString('en-CA');
      html+=`<div class="section-title">⊙ Partidos del día ${selDate} (${filtered.length} partidos)</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`⏰ Programados (${programados.length})`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados);
      if(enJuego.length===0&&programados.length===0&&finalizados.length===0) html+=filtered.map(cardA).join('');
    } else if(currentFilter==='top'){
      html+=`<div class="section-title">★ Top Picks - Alta/Media confianza (${filtered.length}) - Orden: Alta primero, luego Media, por fecha</div>`;
      if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      if(programados.length>0) html+=renderSection(`🎯 Programados (${programados.length}) - Alta primero`,programados);
      if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados);
      if(enJuego.length===0&&programados.length===0&&finalizados.length===0) html+=filtered.map(cardA).join('');
    } else if(currentFilter==='combinada'){
      const topAlta=[...filtered].filter(m=>m.confidence==='Alta').sort((a,b)=>Math.max(b.probabilities?.['1']||0,b.probabilities?.['X']||0,b.probabilities?.['2']||0)-Math.max(a.probabilities?.['1']||0,a.probabilities?.['X']||0,a.probabilities?.['2']||0));
      const topMedia=[...filtered].filter(m=>m.confidence==='Media').sort((a,b)=>Math.max(b.probabilities?.['1']||0,b.probabilities?.['X']||0,b.probabilities?.['2']||0)-Math.max(a.probabilities?.['1']||0,a.probabilities?.['X']||0,a.probabilities?.['2']||0));
      _lastTopAlta=topAlta; _lastTopMedia=topMedia;
      let htmlCombinadas=`<div class="section-title">∽ Combinadas - Sugeridas + Arma la tuya (${filtered.length} picks)</div>`;
      if(customCombinada.length>0){
        const stats=calcCombinadaStats(customCombinada);
        htmlCombinadas+=`<div class="analytics-panel" style="background:#102a1e; border:2px solid #1ee07a"><div class="analytics-card wide" style="border-left:4px solid #1ee07a"><div class="analytics-title" style="font-size:18px">🎯 TU COMBINADA (${customCombinada.length}/6) - Prob ${stats.prob.toFixed(1)}% | Cuota ${stats.cuota.toFixed(2)}x</div><div class="analytics-value">Con $100 ganas $${(100*stats.cuota).toFixed(0)} | Prob combinada ${stats.prob.toFixed(1)}%</div><div style="margin-top:10px">`;
        customCombinada.forEach((m,i)=>{ const fav=m.favorite||''; const p=m.probabilities||{}; const maxP=Math.max(p['1']||0,p['X']||0,p['2']||0); htmlCombinadas+=`<div class="liga-row"><span>${i+1}. ⭐ ${esc(m.home)} vs ${esc(m.away)} → ${esc(fav)} (${maxP.toFixed(1)}%)</span><button class="mini-filter fallo" onclick="toggleCombinada('${(m._key||`${m.date}_${m.home}_${m.away}`).replace(/'/g,"\\'")}')" style="margin-left:8px">❌ Quitar</button></div>`; });
        htmlCombinadas+=`</div><div style="margin-top:10px; display:flex; gap:8px"><button class="mini-filter acierto" onclick="clearCombinada()">🗑️ Limpiar</button><button class="mini-filter" style="background:#1ee07a; color:#000" onclick="navigator.clipboard.writeText(customCombinada.map(m=>m.home+' vs '+m.away+' → '+m.favorite).join('\\n')); alert('Combinada copiada!')">📋 Copiar</button></div></div></div>`;
      } else {
        htmlCombinadas+=`<div class="analytics-panel"><div class="analytics-card wide" style="background:#0f1a33"><div class="analytics-title">👆 Arma tu combinada - Click en "➕ Agregar a mi combinada" en las tarjetas de abajo (máx 6)</div><div class="analytics-value">Selecciona 2-4 partidos Alta confianza. Verás prob y cuota arriba.</div></div></div>`;
      }
      htmlCombinadas+=`<div class="analytics-panel"><div class="analytics-card wide" style="background:#0f1a33"><div class="analytics-title">💡 Sugeridas por LiAn - Click para usar</div></div></div>`;
      const dobleSegura=topAlta.slice(0,2), tripleEquilibrada=[...topAlta.slice(0,2),...topMedia.slice(0,1)], cuadruple=[...topAlta.slice(0,2),...topMedia.slice(0,2)];
      htmlCombinadas+=`<div class="analytics-panel" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px,1fr)); gap:12px">`;
      if(dobleSegura.length>=2){ const s=calcCombinadaStats(dobleSegura); htmlCombinadas+=`<div class="analytics-card" style="border-left:4px solid #1ee07a"><div class="analytics-title">🟢 DOBLE SEGURA</div><div class="analytics-value">Riesgo bajo | Prob ${s.prob.toFixed(1)}% | Cuota ${s.cuota.toFixed(2)}x</div>${dobleSegura.map(m=>`<div class="liga-row"><span>⭐ ${esc(m.home)} vs ${esc(m.away)} → ${esc(m.favorite||'')}</span></div>`).join('')}<button class="mini-filter acierto" style="margin-top:8px" onclick="useSuggested('doble')">➕ Usar esta (2)</button></div>`; }
      if(tripleEquilibrada.length>=3){ const s=calcCombinadaStats(tripleEquilibrada); htmlCombinadas+=`<div class="analytics-card" style="border-left:4px solid #f5d547"><div class="analytics-title">🟡 TRIPLE EQUILIBRADA</div><div class="analytics-value">Riesgo medio | Prob ${s.prob.toFixed(1)}% | Cuota ${s.cuota.toFixed(2)}x</div>${tripleEquilibrada.map(m=>`<div class="liga-row"><span>⭐ ${esc(m.home)} vs ${esc(m.away)} → ${esc(m.favorite||'')}</span></div>`).join('')}<button class="mini-filter acierto" style="margin-top:8px" onclick="useSuggested('triple')">➕ Usar esta (3)</button></div>`; }
      if(cuadruple.length>=4){ const s=calcCombinadaStats(cuadruple); htmlCombinadas+=`<div class="analytics-card" style="border-left:4px solid #ff6b6b"><div class="analytics-title">🔴 CUÁDRUPLE ARRIESGADA</div><div class="analytics-value">Riesgo alto | Prob ${s.prob.toFixed(1)}% | Cuota ${s.cuota.toFixed(2)}x</div>${cuadruple.map(m=>`<div class="liga-row"><span>⭐ ${esc(m.home)} vs ${esc(m.away)} → ${esc(m.favorite||'')}</span></div>`).join('')}<button class="mini-filter acierto" style="margin-top:8px" onclick="useSuggested('cuadruple')">➕ Usar esta (4)</button></div>`; }
      htmlCombinadas+=`</div>`;
      if(programados.length>0) htmlCombinadas+=renderSection(`⏰ Programados para armar tu combinada (${programados.length}) - Click ➕ en tarjeta`,programados);
      if(enJuego.length>0) htmlCombinadas+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego);
      html=htmlCombinadas;
    } else if(currentFilter==='progol'){
      html=renderProgolReal();
    } else if(currentFilter==='aciertos'){
      html+=`<div class="section-title">✅ Aciertos (${filtered.length})</div>`; html+=filtered.map(cardA).join('');
    } else if(currentFilter==='fallos'){
      html+=`<div class="section-title">❌ Fallos (${filtered.length})</div>`; html+=filtered.map(cardA).join('');
    } else {
      const titleMap={'liga-mx':'🇲🇽 Liga MX','mls':'🇺🇸 MLS','champions':'🏆 Champions League','europa':'🏅 Top 5 Europa','league:mex.1':'🇲🇽 Liga MX - México','league:usa.1':'🇺🇸 MLS - USA','league:bra.1':'🇧🇷 Brasileirão - Brasil','league:arg.1':'🇦🇷 Liga Argentina','league:eng.1':'🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League','league:eng.fa':'🏴󠁧󠁢󠁥󠁮󠁧󠁿 FA Cup','league:esp.1':'🇪🇸 La Liga','league:ita.1':'🇮🇹 Serie A','league:ger.1':'🇩🇪 Bundesliga','league:fra.1':'🇫🇷 Ligue 1','league:uefa.champions':'🏆 Champions League','league:uefa.europa':'Europa League','league:uefa.europa.conf':'Conference League','league:concacaf.champions':'Concachampions','continent:america':'🌎 América','continent:europa':'🌍 Europa','analytics':'📊 Estadísticas'};
      const t=titleMap[currentFilter]||currentFilter.replace('league:','').replace('continent:','').replace('country:',''); html+=`<div class="section-title">${t} (${filtered.length} partidos)</div>`; if(enJuego.length>0) html+=renderSection(`🔴 En Juego (${enJuego.length})`,enJuego); if(programados.length>0) html+=renderSection(`⏰ Programados (${programados.length})`,programados); if(finalizados.length>0) html+=renderSection(`✅ Finalizados (${finalizados.length})`,finalizados); if(enJuego.length===0&&programados.length===0&&finalizados.length===0) html+=filtered.map(cardA).join('');
    }
    html+=`<div class="section-title">📊 Transparencia</div><div class="card"><div class="meta">Probabilidad != recomendación segura. Suma 1X2 ~100% validado.</div><div class="meta">V91 Progol real TuLotero 14 + Revancha 7</div></div>`;
    $grid.innerHTML=html;
  }catch(e){
    log(`RENDER ERROR: ${e.message}`,'err');
    $grid.innerHTML=`<div class="card"><div class="meta" style="color:#ff6b6b">Error render: ${esc(e.message)} - ${e.stack}</div></div>`;
  }
}
function setFilterAciertos(){ document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active')); const btn=document.querySelector('[data-filter="aciertos"]'); if(btn) btn.classList.add('active'); currentFilter='aciertos'; renderAll(); }
function setFilterFallos(){ document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active')); const btn=document.querySelector('[data-filter="fallos"]'); if(btn) btn.classList.add('active'); currentFilter='fallos'; renderAll(); }

async function loadLigaMXOnly(){
  // Intentar hasta 2 veces con delay si Render está dormido
  for(let attempt=1; attempt<=2; attempt++){
    try{

  try{
    $status.textContent='Cargando SOLO Liga MX temporada completa...';
    const data = await api('/api/liga-mx/season?limit=300');
    if(data && data.matches && data.matches.length>0){
        allMatches = data.matches;
        log(`Liga MX cargada: ${data.matches.length} partidos temporada`, 'ok');
        currentFilter='liga-mx';
        document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active'));
        const btn=document.querySelector('[data-filter="liga-mx"]');
        if(btn) btn.classList.add('active');
        renderAll();
        $status.textContent=`${data.count} partidos Liga MX temporada - ${data.source}`;
        return;
      } else {
        $status.textContent='No hay Liga MX, sincronizando... intento '+attempt;
        await api('/api/liga-mx/sync');
        await new Promise(r=>setTimeout(r, 8000));
      }
    }catch(e){
      log(`Error Liga MX intento ${attempt}: ${e.message}`, 'err');
      if(attempt<2){
        $status.textContent=`Error Liga MX intento ${attempt}, reintentando...`;
        await new Promise(r=>setTimeout(r, 3000));
      } else {
        $status.textContent=`Error Liga MX: ${e.message} - Intentando temporada general`;
        try{
          const allData=await api(`/api/calendar/season?limit=300`);
          allMatches=allData.matches||[];
          $status.textContent=`${allMatches.length} partidos temporada general`;
          renderAll();
        }catch(e2){
          $status.textContent=`Error total: ${e.message}`;
        }
      }
    }
  }
}


async function syncLigaMX(){
  $status.textContent='Sincronizando SOLO Liga MX... 60-90 seg';
  try{
    await api('/api/liga-mx/sync');
    log('Sync Liga MX iniciado', 'ok');
    setTimeout(loadLigaMXOnly, 10000);
  }catch(e){
    $status.textContent=`Error sync Liga MX: ${e.message}`;
  }
}

async function loadFast(){
  const date=$dateInput.value||new Date().toLocaleDateString('en-CA');
  if(!date){ $dateInput.value=new Date().toLocaleDateString('en-CA'); }
  const d=$dateInput.value||new Date().toLocaleDateString('en-CA');
  $status.textContent=`Cargando ${d} - intentando Liga MX...`;
  try{
    const data=await api(`/api/calendar/fast?date=${d}`);
    allMatches=data.matches||[];
    if(allMatches.length===0){
      log(`Fast devolvió 0 para ${d}, cargando Liga MX temporada`, 'err');
      await loadLigaMXOnly();
      return;
    }
    $status.textContent=`${data.count} partidos reales de ${d} - ${data.source||''}`;
    renderAll();
  }catch(e){ 
    log(`Fast falló (${e.message}), cargando Liga MX temporada como fallback`, 'err');
    $status.textContent=`Fast falló, cargando Liga MX...`;
    await loadLigaMXOnly();
  }
}
async function refresh(){ const date=$dateInput.value||new Date().toLocaleDateString('en-CA'); $status.textContent=`Sincronizando ${date}...`; try{ await api(`/api/calendar?refresh=1&date=${date}`); setTimeout(loadFast,3000); }catch(e){ $status.textContent=`Error sync: ${e.message}`; } }
document.addEventListener('click',(e)=>{ const btn=e.target.closest('.menu-item'); if(!btn) return; if(!btn.dataset.filter) return; document.querySelectorAll('.menu-item').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); currentFilter=btn.dataset.filter; if(currentFilter==='search') $searchBox.style.display='block'; else $searchBox.style.display='none'; if(currentFilter==='liga-mx'){ loadLigaMXOnly(); return; } renderAll(); if(window.innerWidth<800) document.querySelector('.main').scrollTop=0; });
$searchInput.addEventListener('input',renderAll);
$leagueSelect.addEventListener('change',renderAll);
document.getElementById('loadBtn').addEventListener('click',loadFast);
document.getElementById('refreshBtn').addEventListener('click',refresh);
(async()=>{ 
  $dateInput.value=new Date().toLocaleDateString('en-CA'); 
  try{ 
    const h=await api('/api/health'); 
    $status.textContent=`API: ${h.version} - ${h.records} partidos - Cargando Liga MX`; 
    // Focus Liga MX - temporada completa, no por fecha
    await loadLigaMXOnly();
    loadProgolFromBackend(); 
  }catch(e){ 
    $status.textContent='API no conecta: '+e.message; 
    log('Health error: '+e.message, 'err');
  } 
})();
