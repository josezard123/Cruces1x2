// Bound browser replies independently of timers in an inactive content tab.
async function readerTask(tabId,message,limit=90000){
 let timeout,keepAlive;
 try{
  keepAlive=setInterval(()=>chrome.storage.local.get('enabled').catch(()=>{}),10000);
  return await Promise.race([chrome.tabs.sendMessage(tabId,message),new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('La página no respondió a tiempo; se continúa con las demás casas.')),limit);})]);
 }finally{clearTimeout(timeout);clearInterval(keepAlive);}
}
async function scanDirectSource(origin,source,continuing){
 const settings=await chrome.storage.local.get('enabled');if(!settings.enabled)return {ok:false,captured:0,reason:'disabled'};
 const configuration=await(await fetch(origin+'/direct-settings')).json();
 const cancelled=async()=> (await(await fetch(origin+'/update-status')).json()).cancelled===true;
 if(await cancelled())return {ok:false,captured:0,reason:'cancelled'};
 const wina=source==='winamax_es',label=wina?'Winamax ES':'Betfair Sportsbook';
 // Competition URL verified on the public Spanish coupon. Avoid its menu for LaLiga-only scans.
 const known=!wina&&configuration.leagues.includes('laliga')?[{url:'https://www.betfair.es/apuestas/f%C3%BAtbol/la-liga-espa%C3%B1ola/c-117',name:'La Liga Española',country:'España',key:'laliga'}]:[];
 const discover=wina||configuration.leagues.some(key=>key!=='laliga');
 let tab,captured=0,processed=0,total=0;const failures=[];const started=Date.now();
 let currentPhase='Preparando lectura';
 const progress=async current=>{
  currentPhase=current;
  await fetch(origin+'/bet365-scan-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source,running:true,processed,total,captured,current,last_error:''})});
  await chrome.storage.local.set({status:`${label}: ${processed}/${total} competiciones · ${captured} partidos. ${current}`});
 };
 const heartbeat=setInterval(()=>progress(currentPhase).catch(()=>{}),10000);
 try{
  await progress(discover?'Descubriendo competiciones públicas':'Cargando LaLiga de Betfair');
  tab=await chrome.tabs.create({url:!discover&&known.length?known[0].url:wina?'https://www.winamax.es/apuestas-deportivas/sports/1':'https://www.betfair.es/apuestas/f%C3%BAtbol/s-1',active:false});
  let result={ok:true,competitions:known};
  if(discover){
   try{await waitForReader(tab.id);result=await readerTask(tab.id,{type:'direct-discover',settings:configuration});}
   catch(error){if(!known.length)throw error;failures.push('Catálogo: '+error.message);}
   if(typeof savePublicDiagnostic==='function')await savePublicDiagnostic(origin,result);
   if(!wina&&typeof retryEmptyPublicPage==='function'){
    result=await retryEmptyPublicPage(tab,result,()=>readerTask(tab.id,{type:'direct-discover',settings:configuration}),cancelled,progress);
    if(typeof savePublicDiagnostic==='function')await savePublicDiagnostic(origin,result);
   }
   if(known.length)result={ok:true,competitions:[...new Map([...known,...(result.competitions||[])].map(c=>[c.url,c])).values()]};
  }
  if(!result?.ok)throw Error(result?.reason||'No se pudo leer el catálogo público.');
  const competitions=(result.competitions||[]).filter(c=>{
   try{const u=new URL(c.url);return u.hostname===(wina?'www.winamax.es':'www.betfair.es')&&u.protocol==='https:'&&!u.search&&!u.hash&&!u.username&&!u.password&&configuration.leagues.includes(c.key)&&(wina?/^\/apuestas-deportivas\/sports\/1\/\d+\/\d+$/.test(u.pathname):/^\/apuestas\/f%C3%BAtbol\/[^/]+\/c-\d+$/i.test(u.pathname));}catch{return false;}
  }).slice(0,40);
  total=competitions.length;
  if(!total)failures.push('No se encontraron las competiciones seleccionadas en el catálogo público.');
  for(const competition of competitions){
   if(await cancelled())break;
   if(Date.now()-started>600000){failures.push('Tiempo máximo alcanzado; cobertura parcial.');break;}
   await progress('Leyendo '+competition.name);
   try{
    await chrome.tabs.update(tab.id,{url:competition.url});await waitForReader(tab.id,competition.url);
    const task={type:'direct-read',competition,settings:configuration};
    let read=await readerTask(tab.id,task,120000);
    if(typeof savePublicDiagnostic==='function')await savePublicDiagnostic(origin,read);
    if(!wina&&typeof retryEmptyPublicPage==='function'){
     read=await retryEmptyPublicPage(tab,read,()=>readerTask(tab.id,task,120000),cancelled,progress);
     if(typeof savePublicDiagnostic==='function')await savePublicDiagnostic(origin,read);
    }
    if(!read?.ok)throw Error(read?.reason||'No se pudo leer el resultado final.');
    if(await cancelled())break;
    const response=await fetch(origin+'/direct-observation/'+source,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(read.payload)});
    const received=await response.json();
    if(!response.ok||!received.ok)throw Error(received.reason||'La app rechazó la lectura.');
    captured+=received.captured;
    if(!received.captured)failures.push(competition.name+': no se verificaron cuotas activas prepartido en el intervalo.');
   }catch(error){failures.push(competition.name+': '+(error.message||'Lectura no completada.'));}
   processed++;await progress(competition.name);
  }
 }catch(error){failures.push(error.message||'No se pudo completar la lectura pública.');}
 finally{clearInterval(heartbeat);if(tab)await chrome.tabs.remove(tab.id).catch(()=>{});}
 await fetch(origin+'/bet365-scan-complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source,captured,failures,continuing})});
 return {ok:!(await cancelled()),captured,failures,reason:(await cancelled())?'cancelled':undefined};
}
