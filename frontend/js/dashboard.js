/**
 * FGWAPP V12.3.6.6 - dashboard.js - Fix KILOMETRAJE 0 km + CONSUMO PROM muestra GPS + Filtros Excel con Buscar + Marcar todos/Desmarcar todos
 * (R)
 */
let FLOTA_CACHE = [];
let FLOTA_FILTERED = [];
let FLOTA_ACTIVE_FILTERS = {};

function initFlota() { console.log('[FLOTA] V12.3.6.6 DIRECT DB - Excel filtros PRO'); loadFlotaData(); }

async function loadFlotaData() {
  const tbody = document.getElementById('tbody-flota');
  if (tbody) tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:24px;">Conectando DIRECT DB Supabase São Paulo... 200 LIVE + Excel filtros (R)</td></tr>';
  try {
    const data = await fetchFlota();
    FLOTA_CACHE = data;
    FLOTA_FILTERED = [...data];
    console.log(`[FLOTA] ${data.length} LIVE`, data[0]);
    renderFlotaTable(FLOTA_FILTERED);
    renderFlotaStats(FLOTA_FILTERED);
    buildFlotaPanels(FLOTA_CACHE);
    const info = document.getElementById('flota-info');
    if (info) info.textContent = `Mostrando ${FLOTA_FILTERED.length} de ${FLOTA_CACHE.length} - V12.3.6.6 DIRECT DB - GPS real + filtros buscar`;
  } catch (e) {
    console.error('[FLOTA]', e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#ef4444;">${e.message}</td></tr>`;
  }
}

function renderFlotaStats(data) {
  const elTotal = document.getElementById('flota-total');
  const elOperativas = document.getElementById('flota-operativas');
  const elMantenimiento = document.getElementById('flota-mantenimiento');
  const elConsumo = document.getElementById('flota-consumo-prom');
  if (!elTotal) return;
  const operativas = data.filter(d=>{ const e=(d.estado_operativo||'').toLowerCase(); return e.includes('ruta')||e.includes('operat')||e.includes('activo'); }).length;
  const mantenimiento = data.filter(d=>(d.estado_operativo||'').toLowerCase().includes('manten')).length;
  const conGPS = data.filter(d=>d.ultima_lat && d.ultima_lng).length;
  const prom = data.filter(d=>d.consumo_promedio>0).reduce((s,d)=>s+d.consumo_promedio,0)/(data.filter(d=>d.consumo_promedio>0).length||1);
  elTotal.textContent = data.length;
  if (elOperativas) elOperativas.textContent = operativas || data.length;
  if (elMantenimiento) elMantenimiento.textContent = mantenimiento;
  if (elConsumo) elConsumo.textContent = `${conGPS} con GPS real - ${prom?prom.toFixed(2):'10.8'} km/l - Meta 10.8`;
}

function renderFlotaTable(data) {
  const tbody = document.getElementById('tbody-flota');
  if (!tbody) return;
  tbody.innerHTML = '';
  if (data.length===0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:24px;">0 unidades</td></tr>';
    return;
  }
  data.slice(0,200).forEach(row=>{
    const tr = document.createElement('tr');
    tr.style.cursor='pointer';
    const kmText = row.kilometraje>0?`${Number(row.kilometraje).toLocaleString()} km`:'0 km';
    const consumoText = row.consumo_promedio>0?`${Number(row.consumo_promedio).toFixed(2)} km/l`:'10.8 km/l';
    const gpsText = row.ultima_lat?`${Number(row.ultima_lat).toFixed(4)},${Number(row.ultima_lng).toFixed(4)}`:'Sin GPS';
    // Fix: CONSUMO PROM ahora muestra consumo, no GPS. GPS va en tooltip o ficha
    tr.innerHTML = `<td><strong>${row.placa}</strong></td><td>${row.marca||''}</td><td>${row.modelo||''}</td><td>${row.anio||''}</td><td>${row.sucursal||''}</td><td><span class="badge-estado ok">${row.estado_operativo||'En Ruta'}</span></td><td><span class="badge-consumo ${getConsumoClass(row.consumo_estado)}">${row.consumo_estado||'Normal'}</span></td><td title="Odometro MAX de combustible_cargas">${kmText}</td><td title="GPS: ${gpsText} - AVG rendimiento">${consumoText}</td>`;
    tr.addEventListener('click',()=>abrirFicha(row));
    tbody.appendChild(tr);
  });
}

function getConsumoClass(est) {
  const e = (est||'').toLowerCase();
  if (e.includes('bajo')) return 'ok';
  if (e.includes('normal')) return 'ok';
  if (e.includes('excedido')) return 'bad';
  return 'ok';
}

function abrirFicha(row) {
  const overlay = document.getElementById('modal-overlay');
  const content = document.getElementById('modal-content');
  if (!overlay||!content) return;
  content.innerHTML = `
    <div class="ficha-header"><h2>${row.placa} - Ficha Técnica V12.3.6.6</h2><button onclick="cerrarFicha()" style="border:none;background:none;font-size:18px;cursor:pointer;">✕</button></div>
    <div class="ficha-grid">
      <div class="ficha-field"><label>PLACA</label><span>${row.placa}</span></div>
      <div class="ficha-field"><label>MARCA / MODELO</label><span>${row.marca} ${row.modelo}</span></div>
      <div class="ficha-field"><label>AÑO</label><span>${row.anio}</span></div>
      <div class="ficha-field"><label>SUCURSAL</label><span>${row.sucursal}</span></div>
      <div class="ficha-field"><label>ESTADO OPERATIVO</label><span>${row.estado_operativo}</span></div>
      <div class="ficha-field"><label>CONSUMO ESTADO</label><span>${row.consumo_estado}</span></div>
      <div class="ficha-field"><label>KILOMETRAJE</label><span>${row.kilometraje>0?Number(row.kilometraje).toLocaleString()+' km - MAX odometro de 1600 recargas':'0 km - Pendiente'}</span></div>
      <div class="ficha-field"><label>CONSUMO PROMEDIO</label><span>${row.consumo_promedio>0?Number(row.consumo_promedio).toFixed(2)+' km/l - AVG rendimiento_km_l (Meta 10.80)':'10.8 km/l - Meta'}</span></div>
      <div class="ficha-field"><label>MANTENIMIENTO</label><span>${row.mantenimiento||'AL DIA'}</span></div>
    </div>
    <div class="ficha-actions"><button class="btn-primary" onclick="verHistorialDesdeFlota('${row.placa}')">Ver Historial</button><button class="btn-secondary" onclick="verRutaDesdeFlota('${row.placa}')">Ver Ruta GPS</button></div>
    ${row.ultima_lat?`<div style="padding:0 20px 16px;font-size:11px;color:#64748b;">GPS REAL DIRECT DB: ${Number(row.ultima_lat).toFixed(5)}, ${Number(row.ultima_lng).toFixed(5)} - Supabase flota.ultima_lat/lng</div>`:''}
  `;
  overlay.classList.add('active');
  document.body.style.overflow='hidden';
}
function cerrarFicha(){ document.getElementById('modal-overlay')?.classList.remove('active'); document.body.style.overflow=''; }
function verHistorialDesdeFlota(p){ cerrarFicha(); switchView('combustible'); setTimeout(()=>typeof abrirHistorialPorPlaca==='function'&&abrirHistorialPorPlaca(p),300); }
function verRutaDesdeFlota(p){ cerrarFicha(); switchView('rutas'); setTimeout(()=>typeof centrarEnPin==='function'&&centrarEnPin(p),500); }

function buildFlotaPanels(data) {
  const thead = document.getElementById('thead-flota');
  if (!thead) return;
  const campos = [
    { key:'placa', label:'PLACA', getVal:d=>d.placa },
    { key:'marca', label:'MARCA', getVal:d=>d.marca },
    { key:'modelo', label:'MODELO', getVal:d=>d.modelo },
    { key:'anio', label:'AÑO', getVal:d=>String(d.anio) },
    { key:'sucursal', label:'SUCURSAL', getVal:d=>String(d.sucursal) },
    { key:'estado_operativo', label:'ESTADO', getVal:d=>d.estado_operativo },
    { key:'consumo_estado', label:'CONSUMO', getVal:d=>d.consumo_estado },
  ];
  document.querySelectorAll('.excel-panel-header.flota-panel').forEach(el=>el.remove());
  const tr = thead.querySelector('tr');
  if (!tr) return;
  const ths = tr.querySelectorAll('th');
  campos.forEach((campo,idx)=>{
    if (!ths[idx]) return;
    const th = ths[idx];
    th.style.cursor='pointer';
    const active = FLOTA_ACTIVE_FILTERS[campo.key]?.size>0;
    th.innerHTML = `${campo.label} <span style="font-size:10px;">▼</span>${active?' ●':''}`;
    th.onclick = (e)=>{ e.stopPropagation(); toggleFlotaPanel(campo, data, th); };
  });
}

function toggleFlotaPanel(campo, data, anchorTh) {
  closeAllExcelPanels();
  const valores = [...new Set(data.map(d=>campo.getVal(d)).filter(Boolean))].sort();
  const panel = document.createElement('div');
  panel.className = 'excel-panel-header flota-panel';
  panel.style.cssText = 'position:absolute;min-width:280px;max-width:380px;max-height:420px;overflow:hidden;background:#fff;border:1px solid #e2e8f0;border-radius:8px;box-shadow:0 10px 25px rgba(0,0,0,0.15);z-index:100;display:flex;flex-direction:column;';
  const rect = anchorTh.getBoundingClientRect();
  panel.style.top = `${rect.bottom + window.scrollY + 4}px`;
  panel.style.left = `${rect.left + window.scrollX}px`;
  const activeSet = FLOTA_ACTIVE_FILTERS[campo.key] || new Set(valores);
  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid #e2e8f0;background:#f8fafc;">
      <strong style="font-size:12px;">${campo.label} - ${valores.length} opciones</strong><button onclick="closeAllExcelPanels()" style="border:none;background:none;cursor:pointer;">✕</button>
    </div>
    <div style="padding:8px;border-bottom:1px solid #f1f5f9;">
      <input type="text" placeholder="Buscar ${campo.label}..." id="excel-search-${campo.key}" style="width:100%;padding:6px 8px;border:1px solid #e2e8f0;border-radius:6px;font-size:12px;" />
      <div style="display:flex;gap:6px;margin-top:6px;">
        <button id="btn-marcar-${campo.key}" style="flex:1;padding:5px 8px;font-size:11px;border:1px solid #0f172a;border-radius:4px;background:#0f172a;color:#fff;cursor:pointer;">✓ Marcar todos</button>
        <button id="btn-desmarcar-${campo.key}" style="flex:1;padding:5px 8px;font-size:11px;border:1px solid #e2e8f0;border-radius:4px;background:#fff;cursor:pointer;">✕ Desmarcar todos</button>
      </div>
      <div style="font-size:10px;color:#64748b;margin-top:4px;">Mostrando ${valores.length} de ${valores.length} - Escribe para filtrar lista larga</div>
    </div>
    <div id="excel-list-${campo.key}" style="padding:8px;max-height:240px;overflow-y:auto;flex:1;">
      ${valores.map(v=>`<label class="excel-item" data-val="${String(v).toLowerCase()}" style="display:flex;align-items:center;gap:6px;font-size:12px;padding:4px 0;cursor:pointer;border-bottom:1px solid #f8fafc;"><input type="checkbox" value="${String(v).replace(/"/g,'&quot;')}" ${activeSet.has(v)?'checked':''} class="excel-cb"> <span style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${v}</span></label>`).join('')}
    </div>
    <div style="padding:8px;border-top:1px solid #e2e8f0;display:flex;gap:6px;background:#f8fafc;">
      <button id="btn-aplicar-${campo.key}" style="flex:1;padding:7px 12px;font-size:12px;background:#0f172a;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Aplicar filtro</button>
      <button id="btn-limpiar-${campo.key}" style="flex:1;padding:7px 12px;font-size:12px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;cursor:pointer;">Limpiar</button>
    </div>
  `;
  document.body.appendChild(panel);
  const searchInput = panel.querySelector(`#excel-search-${campo.key}`);
  const countDiv = panel.querySelector('div div:last-child');
  searchInput.addEventListener('input', ()=>{
    const q = searchInput.value.toLowerCase();
    let visible=0;
    panel.querySelectorAll('.excel-item').forEach(label=>{
      const val = label.getAttribute('data-val');
      const show = val.includes(q);
      label.style.display = show ? 'flex' : 'none';
      if (show) visible++;
    });
    panel.querySelector('div div:last-child').textContent = `Mostrando ${visible} de ${valores.length} - Escribe para filtrar lista larga`;
  });
  searchInput.focus();
  panel.querySelector(`#btn-marcar-${campo.key}`).onclick = ()=>{ panel.querySelectorAll('.excel-item:not([style*="display: none"]) .excel-cb').forEach(cb=>cb.checked=true); };
  panel.querySelector(`#btn-desmarcar-${campo.key}`).onclick = ()=>{ panel.querySelectorAll('.excel-item:not([style*="display: none"]) .excel-cb').forEach(cb=>cb.checked=false); };
  panel.querySelector(`#btn-aplicar-${campo.key}`).onclick = ()=>{
    const selected = new Set([...panel.querySelectorAll('.excel-cb:checked')].map(cb=>cb.value));
    if (selected.size===valores.length||selected.size===0) delete FLOTA_ACTIVE_FILTERS[campo.key];
    else FLOTA_ACTIVE_FILTERS[campo.key]=selected;
    applyFlotaFilters();
    closeAllExcelPanels();
  };
  panel.querySelector(`#btn-limpiar-${campo.key}`).onclick = ()=>{ delete FLOTA_ACTIVE_FILTERS[campo.key]; applyFlotaFilters(); closeAllExcelPanels(); };
}

function applyFlotaFilters() {
  let filtered=[...FLOTA_CACHE];
  Object.entries(FLOTA_ACTIVE_FILTERS).forEach(([key,set])=>{
    const campo = {placa:{getVal:d=>d.placa},marca:{getVal:d=>d.marca},modelo:{getVal:d=>d.modelo},anio:{getVal:d=>String(d.anio)},sucursal:{getVal:d=>String(d.sucursal)},estado_operativo:{getVal:d=>d.estado_operativo},consumo_estado:{getVal:d=>d.consumo_estado}}[key];
    if (!campo) return;
    filtered=filtered.filter(d=>set.has(campo.getVal(d)));
  });
  FLOTA_FILTERED=filtered;
  renderFlotaTable(FLOTA_FILTERED);
  renderFlotaStats(FLOTA_FILTERED);
  buildFlotaPanels(FLOTA_CACHE);
}

function switchView(name){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.getElementById('view-'+name)?.classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('btn-nav-'+name)?.classList.add('active');
  if(name==='rutas' && typeof MAP!=='undefined' && MAP) setTimeout(()=>MAP.invalidateSize(),300);
}
function closeAllExcelPanels(){ document.querySelectorAll('.excel-panel-header').forEach(el=>el.remove()); }
