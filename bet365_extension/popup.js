const button=document.getElementById('toggle');
async function render(){const data=await chrome.storage.local.get(['enabled','status','lastCapture']);button.textContent=data.enabled?'Detener lectura':'Activar lectura';document.getElementById('status').textContent=data.status||'Lector detenido.';document.getElementById('time').textContent=data.lastCapture?'Última captura: '+data.lastCapture:'';}
button.addEventListener('click',async()=>{const data=await chrome.storage.local.get('enabled');await chrome.storage.local.set({enabled:!data.enabled,status:!data.enabled?'Lector activo. Pulsa Actualizar cuotas en la app.':'Lector detenido.'});render();});
chrome.storage.onChanged.addListener(render);render();
