function scanProgressView(p){
 const total=Math.max(0,Number(p.total)||0),done=Math.min(total,Math.max(0,Number(p.processed)||0));
 const percent=total?Math.floor(done/total*100):null;
 const seconds=Math.max(0,Number(p.phase_elapsed_seconds)||0),elapsed=seconds>=60?`${Math.floor(seconds/60)} min ${seconds%60} s`:`${seconds} s`;
 let text=total?`${p.label||'Lector'}: ${done}/${total} revisados · ${percent}% de esta casa · ${p.captured||0} con cuotas · ${p.current||''}`:`${p.label||'Lector'}: ${p.current||'Preparando lectura'} · buscando el total`;
 text+=` · ${elapsed} en esta fase`;
 if(p.last_error)text+=' · '+p.last_error;
 if(p.stale)text+=' · El lector lleva más de 2 minutos sin responder. Puedes detener y recargar la extensión; las cuotas se conservan.';
 else if(seconds>=45)text+=' · Esperando respuesta de la web; el porcentaje solo avanza al completar una lectura.';
 return {percent,text};
}
function renderScanProgress(p){
 const bar=document.getElementById('scan-progress'),status=document.getElementById('reader-status'),view=scanProgressView(p);
 bar.hidden=!p.running;
 if(view.percent===null)bar.removeAttribute('value');else bar.value=view.percent;
 if(p.running)status.textContent=view.text;
}
