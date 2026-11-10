/**
 * FGWAPP V12.3.6.5 - api.js FIX 400 - order=fecha.desc rompia flota
 * Si order falla, reintenta sin order
 * (R)
 */
async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CONFIG.TIMEOUT_MS);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal, headers: { 'Content-Type': 'application/json', ...(options.headers||{}) } });
    clearTimeout(timeoutId);
    if (!response.ok) return [];
    return await response.json();
  } catch (e) {
    clearTimeout(timeoutId);
    return [];
  }
}

async function fetchDirectSupabase(table, limit = 200, orderBy = null) {
  const tryFetch = async (withOrder) => {
    try {
      let url = `${CONFIG.SUPABASE_URL}/rest/v1/${table}?select=*&limit=${limit}`;
      if (withOrder && orderBy) url += `&order=${orderBy}.asc`;
      console.log(`[DIRECT DB] Fetch ${table} limit ${limit}${withOrder&&orderBy?` order ${orderBy}`:''}...`);
      const res = await fetch(url, {
        headers: { 'apikey': CONFIG.SUPABASE_ANON_KEY, 'Authorization': `Bearer ${CONFIG.SUPABASE_ANON_KEY}` }
      });
      if (!res.ok) {
        const txt = await res.text();
        console.warn(`[DIRECT DB] ${table} ${res.status}:`, txt.slice(0,300));
        if (res.status===400 && withOrder) {
          console.log(`[DIRECT DB] Reintentando ${table} sin order...`);
          return await tryFetch(false);
        }
        return [];
      }
      const data = await res.json();
      console.log(`[DIRECT DB] ${table} -> ${data.length} LIVE ${data.length>0?JSON.stringify(Object.keys(data[0])).slice(0,120):''}`);
      return data;
    } catch (e) { console.error(`[DIRECT DB] ${table}`, e); return []; }
  };
  return await tryFetch(true);
}

function normalizeFlotaRow(row) {
  return {
    id: row.id,
    placa: row.placa || row.PLACA || '',
    marca: row.marca || row.MARCA || '',
    modelo: row.modelo || row.MODELO || '',
    anio: row.anio || row.año || row.ANIO || '',
    sucursal: row.sucursal || row.sucursal_id || (row.sucursal_id===1?'Matriz Guadalajara':row.sucursal_id===2?'Sucursal Culiacán':'GDL'),
    estado_operativo: row.estado_operativo || row.estado || row.ESTADO || 'En Ruta',
    consumo_estado: row.consumo_estado || 'Normal',
    kilometraje: Number(row.kilometraje ?? row.odometro ?? row.km ?? 0),
    consumo_promedio: Number(row.consumo_promedio ?? row.consumo ?? row.rendimiento_km_l ?? 0),
    mantenimiento: row.mantenimiento || 'AL DIA',
    ultima_lat: row.ultima_lat != null ? Number(row.ultima_lat) : (row.lat != null ? Number(row.lat) : (row.gps_lat!=null?Number(row.gps_lat):null)),
    ultima_lng: row.ultima_lng != null ? Number(row.ultima_lng) : (row.lng != null ? Number(row.lng) : (row.gps_lng!=null?Number(row.gps_lng):null)),
  };
}

function normalizeCombustibleRow(row) {
  return {
    fecha: row.fecha || '',
    placa: row.placa || '',
    sucursal: row.sucursal || 'GDL',
    tipo: row.tipo || row.combustible || 'Diesel',
    litros: Number(row.litros ?? 0),
    consumo: Number(row.consumo ?? row.rendimiento_km_l ?? 0),
    costo: Number(row.costo ?? 0),
    kilometraje: Number(row.kilometraje ?? row.odometro ?? 0),
    consumo_estado: row.consumo_estado || (Number(row.consumo ?? row.rendimiento_km_l ?? 10) < 8 ? 'Excedido' : Number(row.consumo ?? row.rendimiento_km_l ?? 10) < 10 ? 'Bajo' : 'Normal')
  };
}

async function fetchFlota() {
  let raw = await fetchWithTimeout(`${CONFIG.API_BASE}/api/flota`);
  let arr = Array.isArray(raw) ? raw : (raw.data || raw.flota || []);
  if (arr.length > 0) {
    console.log(`[API] /api/flota ${arr.length} desde Render`);
    return arr.map(normalizeFlotaRow).filter(r=>r.placa);
  }
  // DIRECT DB - primero tabla flota sin order (seguro)
  raw = await fetchDirectSupabase('flota', 200, null);
  if (raw.length > 0) {
    console.log(`[FLOTA] DIRECT flota sin order -> ${raw.length}`);
    return raw.map(normalizeFlotaRow).filter(r=>r.placa);
  }
  // Intenta con id
  raw = await fetchDirectSupabase('flota', 200, 'id');
  if (raw.length > 0) return raw.map(normalizeFlotaRow).filter(r=>r.placa);
  // Vista
  raw = await fetchDirectSupabase('v_flota_dashboard', 200, 'placa');
  if (raw.length > 0) return raw.map(normalizeFlotaRow).filter(r=>r.placa);
  
  console.error('[FLOTA] 0 LIVE - Revisa fix_rls_anon_read.sql');
  return [];
}

async function fetchCombustible() {
  let raw = await fetchWithTimeout(`${CONFIG.API_BASE}/api/combustible`);
  let arr = Array.isArray(raw) ? raw : (raw.data || raw.combustible || []);
  if (arr.length > 0) return arr.map(normalizeCombustibleRow).filter(r=>r.placa);
  raw = await fetchDirectSupabase('v_combustible_con_placa', 1000, 'fecha');
  if (raw.length > 0) return raw.map(normalizeCombustibleRow).filter(r=>r.placa);
  // fallback sin order
  raw = await fetchDirectSupabase('v_combustible_con_placa', 1000, null);
  if (raw.length > 0) return raw.map(normalizeCombustibleRow).filter(r=>r.placa);
  raw = await fetchDirectSupabase('combustible_cargas', 1000, null);
  if (raw.length > 0) {
    const flota = await fetchDirectSupabase('flota', 200, null);
    const mapFlota = Object.fromEntries(flota.map(f=>[f.id, f]));
    return raw.map(r=>{
      const f = mapFlota[r.flota_id] || {};
      return normalizeCombustibleRow({ ...r, placa: f.placa || `FG-${String(r.flota_id).padStart(4,'0')}`, sucursal: f.sucursal_id||'GDL', consumo: r.rendimiento_km_l, kilometraje: r.odometro });
    });
  }
  return [];
}

async function fetchGPS() {
  if (typeof FLOTA_CACHE !== 'undefined' && FLOTA_CACHE.length > 0) {
    return FLOTA_CACHE.filter(r=>r.ultima_lat && r.ultima_lng);
  }
  const raw = await fetchDirectSupabase('flota', 200, null);
  return raw.filter(r=>r.ultima_lat!=null&&r.ultima_lng!=null).map(r=>({placa:r.placa, ultima_lat:r.ultima_lat, ultima_lng:r.ultima_lng, marca:r.marca, modelo:r.modelo, sucursal:r.sucursal_id, estado_operativo:r.estado}));
}
async function fetchRutas(){return []}
async function fetchStats(){return {}}
async function fetchHealth(){return {status:'ok', version:'V12.3.6.5 FIX 400 FLOTA'};}
