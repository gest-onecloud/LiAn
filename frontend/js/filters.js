// Filters - Logica de filtrado
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
    const topQ=qInput?norm(qInput.value):'';const $searchInput=document.getElementById('searchInput');const $leagueSelect=document.getElementById('leagueSelect');const q2=norm(($searchInput?$searchInput.value:''));const finalQ=topQ||q2;
    const ligaEl=document.getElementById('topLeagueSelect');const liga=(ligaEl?ligaEl.value:($leagueSelect?$leagueSelect.value:'all')||'all').toLowerCase();
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

function groupByEstado(matches){
  const enJuego=matches.filter(function(m){return m.estado==='EN_JUEGO';});
  const programados=matches.filter(function(m){return m.estado==='PROGRAMADO'||!m.estado;});
  const finalizados=matches.filter(function(m){return m.estado==='FINALIZADO';});
  return {enJuego:enJuego,programados:programados,finalizados:finalizados};
}
