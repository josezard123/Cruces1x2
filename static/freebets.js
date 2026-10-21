(()=>{
const $=id=>document.getElementById(id), euro=n=>Number(n).toLocaleString('es-ES',{style:'currency',currency:'EUR'}), pct=n=>Number(n).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})+' %';
const fields=['fb-house','fb-variant','fb-amount','fb-commission','fb-min','fb-back','fb-lay'];
let rankVersion=0,calcVersion=0,timer,scan=false,poll,lastScanMessage='';
function save(){try{sessionStorage.setItem('cruces.freebets',JSON.stringify(Object.fromEntries(fields.map(id=>[id,$(id).value]))));}catch(_){}}
try{const saved=JSON.parse(sessionStorage.getItem('cruces.freebets')||'null');if(saved)for(const id of fields)if(typeof saved[id]==='string')$(id).value=saved[id];}catch(_){}
function params(){return new URLSearchParams({source:$('fb-house').value,freebet:$('fb-amount').value,commission:$('fb-commission').value,min_odds:$('fb-min').value,variant:$('fb-variant').value});}
async function rank(){
 const bet=$('fb-house').value==='bet365',reta=$('fb-house').value==='retabet';
 $('fb-variant-field').hidden=!bet&&!reta;
 $('fb-variant-label').textContent='Cuotas de '+(reta?'RETAbet':'Bet365');
 const normal=$('fb-variant').querySelector('[value="normal"]'),enhanced=$('fb-variant').querySelector('[value="enhanced"]'),early=$('fb-variant').querySelector('[value="two_goals"]');
 enhanced.hidden=enhanced.disabled=reta;early.hidden=early.disabled=!reta;
 $('fb-variant').querySelector('[value="both"]').textContent=reta?'Comparar normales y Ventaja 2 goles':'Comparar normales y mejoradas';
 normal.textContent='Solo normales';
 if((reta&&$('fb-variant').value==='enhanced')||(bet&&$('fb-variant').value==='two_goals')){$('fb-variant').value='both';save();}
 $('fb-variant-help').textContent=reta?'Compara los dos mercados con su propio rating y cobertura. En Cruces se utiliza la normal para X si tiene mejor precio.':'Las mejoradas de Bet365 se añaden solo cuando sus precios están disponibles. Si no se pueden leer, puedes calcular con las normales.';
 const version=++rankVersion;
 try{
  const response=await fetch('/freebets/opportunities?'+params()),data=await response.json();if(version!==rankVersion)return;
  if(!response.ok||!data.ok)throw Error(data.error||'No se pudo calcular el ranking.');
  $('fb-rows').replaceChildren();$('fb-table').hidden=!data.rows.length;$('fb-empty').hidden=!!data.rows.length;
  $('fb-count').textContent=data.rows.length+' oportunidades';
  $('fb-empty').textContent=!data.eligible_matches?'No hay cuotas vigentes de esta casa. Actualízalas en la pestaña Cruces y vuelve aquí.':!data.exchange_matches?'Falta una lectura reciente del Exchange. Pulsa «Actualizar Exchange y ordenar».':'No se encontraron coberturas con equipos, hora, cuota mínima y liquidez compatibles.';
  if(!scan)$('fb-status').textContent=(lastScanMessage?lastScanMessage+' ':'')+`${data.eligible_matches} partidos vigentes de la casa · ${data.exchange_matches} lecturas Exchange vigentes · ${data.insufficient_liquidity} selecciones excluidas por liquidez.`;
  for(const row of data.rows){
   const tr=document.createElement('tr');
   const cell=text=>{const td=document.createElement('td');td.textContent=text;tr.append(td);return td;};
   cell(pct(row.rating)).className='rating';const match=cell(`${row.home} — ${row.away}`);const sub=document.createElement('small');sub.textContent=`${row.start} · ${row.sign}: ${row.selection}`;match.append(sub);
   const back=cell(row.back.toFixed(2));const book=document.createElement('small');book.textContent=row.book+((row.book.startsWith('Bet365')||row.book==='RETAbet ES')?' · '+row.variant_label:'');back.append(book);
   const lay=cell(row.lay.toFixed(2));const liq=document.createElement('small');liq.textContent='Disponible: '+euro(row.liquidity);lay.append(liq);
   cell(euro(row.lay_stake));cell(euro(row.liability));cell(euro(row.profit));
   const actions=cell('');const button=document.createElement('button');button.className='btn secondary';button.textContent='Calcular';button.addEventListener('click',()=>{$('fb-back').value=row.back;$('fb-lay').value=row.lay;$('fb-selection').textContent=`${row.home} — ${row.away} · ${row.selection} · ${row.variant_label}`;save();calculate();$('fb-calculator').scrollIntoView({behavior:'smooth'});});actions.append(button);
   for(const [label,url] of [['Casa',row.book_url],['Exchange',row.exchange_url]]){if(!url)continue;try{if(new URL(url).protocol!=='https:')continue;}catch(_){continue;}const link=document.createElement('a');link.textContent=label;link.href=url;link.target='_blank';link.rel='noopener';link.style.marginLeft='10px';actions.append(link);}
   const captured=document.createElement('small');captured.textContent='Lay leído '+new Date(row.observed_at).toLocaleTimeString('es-ES');actions.append(captured);
   $('fb-rows').append(tr);
  }
 }catch(error){if(version===rankVersion){$('fb-table').hidden=true;$('fb-empty').hidden=false;$('fb-empty').textContent=error.message;}}
}
async function calculate(){const version=++calcVersion;$('fb-calculation').hidden=true;
 if(!$('fb-back').value||!$('fb-lay').value){$('fb-calc-status').textContent='Introduce las dos cuotas.';return;}
 try{const response=await fetch('/freebets/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({freebet:$('fb-amount').value,commission:$('fb-commission').value,back:$('fb-back').value,lay:$('fb-lay').value})});const data=await response.json();if(version!==calcVersion)return;if(!response.ok||!data.ok)throw Error(data.error||'No se pudo calcular.');const r=data.result;
 $('fb-lay-stake').textContent=euro(r.lay_stake);$('fb-liability').textContent=euro(r.liability);$('fb-profit').textContent=euro(r.profit);$('fb-rating').textContent=pct(r.rating);$('fb-win').textContent=euro(r.profit_win);$('fb-lose').textContent=euro(r.profit_lose);$('fb-calc-status').textContent='Cobro de la freebet si gana: '+euro(r.gross)+'. Importes de cobertura redondeados a céntimos.';$('fb-calculation').hidden=false;
 }catch(error){if(version===calcVersion)$('fb-calc-status').textContent=error.message;}
}
for(const id of fields)$(id).addEventListener('input',()=>{save();rankVersion++;calcVersion++;$('fb-table').hidden=true;$('fb-calculation').hidden=true;clearTimeout(timer);timer=setTimeout(()=>{rank();calculate();},200);});
$('fb-rank').addEventListener('click',()=>{rank();calculate();});
function finish(detail){
 scan=false;clearInterval(poll);$('fb-refresh').disabled=false;
 const reasons={empty:'No hay cuotas vigentes de esta casa; actualízalas en Cruces.',busy:'El lector está ocupado con otra búsqueda; espera a que termine.',disabled:'Activa la lectura desde el icono de la extensión.',connection:'No se pudo conectar con el lector del Exchange. Recarga la extensión y comprueba su permiso para Betfair.',market:'Exchange no mostró «Cuotas de partido».',layout:'El formato de las cuotas del Exchange no se pudo leer.',loading:'Exchange no cargó su tabla antes del límite de espera.',no_lay:'Exchange mostró partidos, pero no se pudieron leer sus cuotas lay activas.',teams:'Se leyeron cuotas del Exchange, pero sus equipos no coinciden con la casa.',time:'Se encontraron los equipos, pero la fecha u hora del Exchange no coincide con la casa.'};
 Object.assign(reasons,{date_format:'No se pudo interpretar la fecha mostrada por Exchange.',time_window:'Los partidos leídos del Exchange quedan fuera del intervalo prepartido.',lay_buttons:'Exchange no mostró botones lay activos en las filas leídas.',price_format:'No se pudo interpretar el formato de las cuotas o importes lay en euros.'});
 lastScanMessage=detail?.ok&&detail.captured?`Exchange: ${detail.captured} partidos leídos. ${detail.partial?'Cobertura parcial.':''}`:(reasons[detail?.reason]||'No se pudo completar la lectura del Exchange. Recarga el lector 2.1.7 y vuelve a probar.');
 $('fb-status').textContent=lastScanMessage;rank();
}
document.addEventListener('cruces-exchange-finished',event=>finish(event.detail));
$('fb-refresh').addEventListener('click',()=>{
 if(scan)return;
 if(document.documentElement.dataset.crucesReaderVersion!=='2.1.7'){$('fb-status').textContent='Recarga el lector a versión 2.1.7 en Extensiones y después recarga esta página. La calculadora manual ya funciona.';return;}
 scan=true;$('fb-refresh').disabled=true;$('fb-status').textContent='Iniciando lectura automática del Exchange…';
 const started=Date.now();poll=setInterval(async()=>{try{const data=await(await fetch('/freebets/status')).json();if(scan)$('fb-status').textContent=data.message+' '+data.captured+' partidos leídos.';}catch(_){}if(Date.now()-started>600000)finish({ok:false});},2000);
 document.dispatchEvent(new CustomEvent('cruces-read-exchange',{detail:{source:$('fb-house').value}}));
});
// Expire displayed opportunities without automatically requesting external data.
setInterval(()=>{if(!scan)rank();},30000);
rank();calculate();
})();
