
// API Layer - Todas las llamadas al backend
async function api(path){
  const url = CONFIG.BACKEND + path;
  log('GET '+url);
  try{
    const r = await fetch(url,{mode:'cors'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const j = await r.json();
    log('OK '+path+' -> '+(j.count||j.records||'ok'),'ok');
    return j;
  }catch(e){
    log('ERROR '+path+': '+e.message,'err');
    throw e;
  }
}

const API = {
  request: (path) => api(path),
  health: () => api('/api/health'),
  ligaMXSeason: (limit=500) => api(`/api/liga-mx/season?limit=${limit}`),
  calendarSeason: (limit=500) => api(`/api/calendar/season?limit=${limit}`),
  ligaMXSync: () => api('/api/liga-mx/sync'),
  modelReload: () => api('/api/model/reload'),
  calcElo: () => api('/api/supabase/calc-elo'),
  progolCurrent: () => api('/api/progol/current')
};
