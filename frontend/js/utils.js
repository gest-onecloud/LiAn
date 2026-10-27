
// Utils - Funciones auxiliares
function log(m,c=''){
  const $log = document.getElementById('log');
  if(!$log) return;
  const d=document.createElement('div');
  d.textContent='['+new Date().toLocaleTimeString()+'] '+m;
  if(c) d.className=c;
  $log.prepend(d);
}
function esc(s){
  if(!s) return '';
  const div=document.createElement('div');
  div.textContent=s;
  return div.innerHTML;
}
function norm(s){
  return (s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
}
function ln(m){
  return norm((m.league||'')+' '+(m.league_code||''));
}
function getTodayMX(){
  try{
    return new Date().toLocaleDateString('en-CA',{timeZone:'America/Mexico_City'});
  }catch{
    return new Date().toLocaleDateString('en-CA');
  }
}
function toggleGroup(id){
  const el=document.getElementById('group-'+id);
  const arrow=document.getElementById('arrow-'+id);
  if(!el) return;
  if(el.classList.contains('open')){
    el.classList.remove('open');
    if(arrow) arrow.textContent='▶';
  } else {
    el.classList.add('open');
    if(arrow) arrow.textContent='▼';
  }
}
function toggleCountry(id){
  const el=document.getElementById('country-'+id);
  const arrow=document.getElementById('arrow-'+id);
  if(!el) return;
  if(el.classList.contains('open')){
    el.classList.remove('open');
    if(arrow) arrow.textContent='▶';
  } else {
    el.classList.add('open');
    if(arrow) arrow.textContent='▼';
  }
}
