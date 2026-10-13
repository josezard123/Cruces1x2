(()=>{
 const status=document.getElementById('app-update-status'),check=document.getElementById('app-update-check'),install=document.getElementById('app-update-install');
 if(!status)return;
 async function show(){
  const response=await fetch('/app-updates');const data=await response.json();
  status.textContent=`Versión ${data.version}. ${data.message||''}`;
  install.hidden=!data.available||!data.packaged;install.disabled=Boolean(data.installing);check.disabled=Boolean(data.checking||data.installing);
  if(data.checking||data.installing)setTimeout(()=>show().catch(()=>{status.textContent='La app se está reiniciando. Recarga la página en unos segundos.';}),1500);
 }
 async function post(path){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const data=await response.json();if(!response.ok)throw Error(data.message||'No se pudo completar la operación.');return data;}
 check.onclick=()=>post('/app-updates/check').then(show).catch(error=>{status.textContent=error.message;});
 install.onclick=()=>{if(confirm('¿Actualizar Cruces? Se cerrará y volverá a abrir. Tus ajustes se conservan. Si cambia el lector, recárgalo en Extensiones.'))post('/app-updates/install').then(show).catch(error=>{status.textContent=error.message;});};
 show().then(()=>{if(document.documentElement.dataset.crucesInstalled==='1')return post('/app-updates/check').then(show);}).catch(()=>{status.textContent='No se pudo comprobar la versión; la app sigue disponible.';});
})();
