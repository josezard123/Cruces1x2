async function scanRetabet(origin,continuing){
 const enabled=await chrome.storage.local.get('enabled');if(!enabled.enabled)return {ok:false,captured:0,reason:'disabled'};
 const settings=await(await fetch(origin+'/direct-settings')).json();
 const references=await(await fetch(origin+'/retabet-targets')).json();
 const targets=references.targets||[],cancelled=async()=> (await(await fetch(origin+'/update-status')).json()).cancelled===true;
 if(await cancelled())return {ok:false,captured:0,reason:'cancelled'};
 let tab,captured=0,processed=0;const failures=[],started=Date.now();
 const progress=async current=>{
  await fetch(origin+'/bet365-scan-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:'retabet',running:true,processed,total:targets.length,captured,current,last_error:''})});
  await chrome.storage.local.set({status:`RETAbet ES: ${processed}/${targets.length} partidos · ${captured} con Ventaja 2 goles. ${current}`});
 };
 const matches=(event,target)=>directRetaTeam(event.home,references.aliases)===target.canonical_home&&directRetaTeam(event.away,references.aliases)===target.canonical_away&&Math.abs(Date.parse(event.start)-Date.parse(target.start))<=60000&&event.competition.key===target.league_key;
 const found=new Map();
 try{
  if(!targets.length){failures.push('No hay partidos de referencia de Winamax en el intervalo elegido.');}
  else{
   await progress('Localizando competiciones');
   tab=await chrome.tabs.create({url:'https://apuestas.retabet.es/deportes/futbol/1',active:false});await waitForReader(tab.id);
   const discovered=await readerTask(tab.id,{type:'retabet-discover',settings});
   if(!discovered?.ok)throw Error(discovered?.reason||'No cargó el catálogo de RETAbet.');
   const competitions=(discovered.competitions||[]).filter(c=>settings.leagues.includes(c.key)&&targets.some(t=>t.league_key===c.key)&&retabetPublicURL(c.url,false)).slice(0,40);
   for(const competition of competitions){
    if(await cancelled())break;
    if(Date.now()-started>600000)throw Error('Tiempo máximo alcanzado; cobertura parcial.');
    await progress('Localizando '+competition.name);
    try{
     await chrome.tabs.update(tab.id,{url:competition.url});await waitForReader(tab.id,competition.url);
     const catalogue=await readerTask(tab.id,{type:'retabet-catalogue',competition,settings});
     if(catalogue?.blocked)throw Object.assign(Error(catalogue.reason),{blocked:true});
     if(!catalogue?.ok)throw Error(catalogue?.reason||'No cargaron los partidos.');
     for(const event of catalogue.events||[]){if(retabetPublicURL(event.url,true)&&targets.some(t=>matches(event,t)))found.set(event.url,event);}
    }catch(error){if(error.blocked)throw error;failures.push(competition.name+': '+error.message);}
   }
   for(const reference of targets){
    if(await cancelled())break;
    if(Date.now()-started>600000){failures.push('Tiempo máximo alcanzado; cobertura parcial.');break;}
    const label=reference.home+' — '+reference.away;await progress('Leyendo '+label);
    const candidates=[...found.values()].filter(e=>matches(e,reference));
    if(candidates.length!==1){failures.push(label+': no hay un único partido con equipos, competición y hora coincidentes en RETAbet.');processed++;continue;}
    const target=candidates[0];
    try{
     await chrome.tabs.update(tab.id,{url:target.url});await waitForReader(tab.id,target.url);
     const result=await readerTask(tab.id,{type:'retabet-event',target,settings});
     if(result?.blocked)throw Object.assign(Error(result.reason),{blocked:true});
     if(!result?.ok)throw Error(result?.reason||'No se pudo leer Ventaja 2 goles.');
     if(await cancelled())break;
     const response=await fetch(origin+'/direct-observation/retabet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result.payload)}),received=await response.json();
     if(!response.ok||!received.ok)throw Error(received.reason||'La app rechazó la lectura.');
     captured+=received.captured;
    }catch(error){if(error.blocked)throw error;failures.push(label+': '+error.message);}
    processed++;await progress(label);
   }
  }
 }catch(error){failures.push(error.message||'No se pudo completar la lectura de RETAbet.');}
 finally{if(tab)await chrome.tabs.remove(tab.id).catch(()=>{});}
 await fetch(origin+'/bet365-scan-complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:'retabet',captured,failures,continuing})});
 return {ok:!(await cancelled()),captured,failures,reason:(await cancelled())?'cancelled':undefined};
}
function retabetPublicURL(value,event){try{const u=new URL(value);return u.protocol==='https:'&&u.hostname==='apuestas.retabet.es'&&!u.search&&!u.hash&&!u.username&&!u.password&&(event?/^\/deportes\/futbol\/[^/]+\/[^/]+\/[^/]+\/\d+$/:/^\/deportes\/futbol\/[^/]+\/[^/]+\/\d+$/).test(decodeURIComponent(u.pathname));}catch(_){return false;}}
function directRetaTeam(value,aliases={}){let n=String(value||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/&/g,' and ').replace(/[^a-z0-9]+/g,' ').trim();n=aliases[n]||n;n=n.split(' ').filter(w=>!['fc','cf','afc','sc','ac','club','futbol','football'].includes(w)).join(' ');return aliases[n]||n;}
