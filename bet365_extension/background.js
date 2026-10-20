let activeScan=null;
importScripts('recovery_background.js','exchange_background.js','direct_background.js','retabet_background.js');
async function createBet365Tab(url){
  // A normal window shares the session opened by the user in this profile.
  // Never open incognito, handle credentials, or create a betting account.
  const opened=(await chrome.tabs.query({url:'https://www.bet365.es/*'})).filter(tab=>!tab.incognito);
  if(!opened.length)throw Error('Abre Bet365 tú en una ventana normal de este mismo Chrome o Edge y vuelve a actualizar. Se continúa con las otras casas.');
  const windows=(await chrome.windows.getAll({windowTypes:['normal']})).filter(w=>!w.incognito);
  const available=windows.filter(w=>opened.some(tab=>tab.windowId===w.id));
  const window=available.find(w=>w.focused)||available[0];
  if(!window)throw Error('Abre Bet365 en una ventana normal de este mismo Chrome o Edge y vuelve a actualizar.');
  return chrome.tabs.create({url,active:false,windowId:window.id});
}
async function savePublicDiagnostic(origin,result) {
  if(!result?.diagnostic)return;
  try{await fetch(origin+'/reader-diagnostic',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result.diagnostic)});}catch(_){}
}
async function waitForReader(tabId,expectedUrl,deadline=Date.now()+30000) {
  for(deadline=Math.min(deadline,Date.now()+30000);Date.now()<deadline;) {
    try {
      const reply=await readerTask(tabId,{type:'reader-ping'},Math.max(1,Math.min(5000,deadline-Date.now())));
      if(reply?.ok && (!expectedUrl||reply.url===expectedUrl)) return;
    } catch(_) {}
    await new Promise(resolve=>setTimeout(resolve,500));
  }
  throw new Error('No se pudo conectar con el lector tras cargar la página.');
}
function requireUpcomingTarget(target){
  if(!Number.isFinite(Date.parse(target.start))||Date.parse(target.start)<=Date.now())throw Error('El partido ya ha comenzado; se omite la lectura prepartido.');
  if(target.readDeadline&&Date.now()>=target.readDeadline)throw Error('Límite de espera de este partido alcanzado; se continúa con los demás.');
}
async function selectBetTarget(tabId,target,aliases) {
  requireUpcomingTarget(target);
  try{return await readerTask(tabId,{type:'scan-target',target,aliases},Math.min(20000,(target.readDeadline||Date.now()+19000)-Date.now()+1000));}
  catch(_){
    // A genuine event navigation can close the response channel. Confirm the
    // actual public event route instead of treating every timeout as success.
    try{
      requireUpcomingTarget(target);await waitForReader(tabId,undefined,target.readDeadline);
      const ping=await readerTask(tabId,{type:'reader-ping'},5000),url=new URL(ping?.url||'');
      if(ping?.ok&&url.protocol==='https:'&&url.hostname==='www.bet365.es'&&/\/E\d+\//.test(url.hash))return {ok:true,navigated:true};
    }catch(_){}
    return {ok:false,reason:'Bet365 no respondió a la búsqueda; no se confirmó la apertura del partido.'};
  }
}
async function searchBetTeam(tabId,team,target,aliases) {
  try{
    requireUpcomingTarget(target);
    const url='https://www.bet365.es/#/AX/K%5E'+encodeURIComponent(team)+'/';
    await chrome.tabs.update(tabId,{url});await waitForReader(tabId,url,target.readDeadline);
    return await selectBetTarget(tabId,target,aliases);
  }catch(_){return {ok:false,reason:'No se pudo cargar esta búsqueda de Bet365.'};}
}
async function scanAutomatically(origin,filter={},source='bet365',continuing=false) {
  const cancelled=async()=> (await(await fetch(origin+'/update-status')).json()).cancelled===true;
  if(await cancelled())return {ok:false,captured:0,reason:'cancelled'};
  const sportium=source==='sportium',label=sportium?'Sportium ES':'Bet365';
  const settings=await chrome.storage.local.get('enabled');
  if(!settings.enabled) return {ok:false,captured:0,reason:'disabled'};
  let query=filter.home&&filter.away?'?home='+encodeURIComponent(filter.home)+'&away='+encodeURIComponent(filter.away):'';
  query+=(query?'&':'?')+'source='+source;
  if(filter.missing===true)query+='&missing=1';
  const response=await fetch(origin+'/bet365-targets'+query);
  const data=await response.json();
  let captured=0,processed=0;
  const failures=[];
  if(sportium&&data.outside_window)failures.push(`${data.outside_window} partidos fuera del catálogo de 48 horas; no se buscaron en Sportium.`);
  let tab,catalogue=[];
  const started=Date.now();
  const progress=async(current='',last_error='')=>{
    await fetch(origin+'/bet365-scan-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source,running:true,total:data.targets.length,processed,captured,current,last_error})});
    await chrome.storage.local.set({status:`${label}: ${processed}/${data.targets.length} revisados · ${captured} con cuotas. ${current}${last_error?' · '+last_error:''}`});
  };
  try {
    await progress();
    if(!data.targets.length) {if(!data.outside_window)failures.push('No hay referencias de Winamax para el partido o intervalo elegido.');}
    else tab=sportium?await chrome.tabs.create({url:'https://www.sportium.es/apuestas/sports/soccer/matches/48h',active:false}):await createBet365Tab('https://www.bet365.es/#/AX/');
    if(sportium&&tab){
      await progress('Leyendo el catálogo público de Sportium (48 horas)');
      await waitForReader(tab.id);
      const task={type:'sportium-catalogue',aliases:data.aliases,leagues:data.leagues||[],targets:data.targets};
      let listed=await readerTask(tab.id,task);
      await savePublicDiagnostic(origin,listed);
      listed=await retryEmptyPublicPage(tab,listed,()=>readerTask(tab.id,task),cancelled,progress);
      await savePublicDiagnostic(origin,listed);
      if(!listed?.ok)throw new Error(listed?.reason||'No se pudo leer el catálogo público de Sportium.');
      catalogue=listed.events||[];
      failures.push(...(listed.warnings||[]));
    }
    for(const reference of data.targets) {
      if(await cancelled())break;
      if(Date.now()-started>600000){failures.push('Tiempo máximo alcanzado; cobertura parcial.');break;}
      const target=sportium?reference:{...reference,readDeadline:Math.min(started+600000,Date.now()+75000)};
      const match=`${target.home} — ${target.away}`;
      await progress('Buscando '+match);
      let error='';
      try {
        requireUpcomingTarget(target);
        // New document/route per search; reconnect after every navigation.
        let selected;
        if(sportium){
          const found=catalogue.filter(event=>/^https:\/\/www\.sportium\.es\/apuestas\/sports\/soccer\/events\/\d+$/.test(event.source_url)&&
            event.canonical_home===target.canonical_home&&event.canonical_away===target.canonical_away&&Math.abs(Date.parse(event.start)-Date.parse(target.start))<=900000);
          if(found.length!==1)selected={ok:false,reason:found.length?'Sportium tiene varios eventos con los mismos equipos y hora.':'Este partido no aparece con equipos y hora coincidentes en el catálogo de 48 horas de Sportium.'};
          else{
            await chrome.tabs.update(tab.id,{url:found[0].source_url});
            await waitForReader(tab.id,found[0].source_url);
            selected={ok:true,verifiedStart:found[0].start,expectedEventId:found[0].event_id};
          }
        }else {
          // Search the visitor immediately after the home team. A spelling
          // variant of the home team is only a third attempt, with shared time.
          const queries=[target.home,target.away];
          const original=target.home.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').trim();
          if(target.canonical_home!==original)queries.push(target.canonical_home);
          for(const team of [...new Set(queries)]){
            if(await cancelled())break;
            requireUpcomingTarget(target);
            // Reserve time for the visitor and for reading the selected event.
            const searchTarget={...target,readDeadline:Math.min(target.readDeadline,Date.now()+25000)};
            selected=await searchBetTeam(tab.id,team,searchTarget,data.aliases);
            await savePublicDiagnostic(origin,selected);
            if(Date.now()<searchTarget.readDeadline){
              selected=await retryEmptyPublicPage(tab,selected,()=>selectBetTarget(tab.id,searchTarget,data.aliases),cancelled,progress);
              await savePublicDiagnostic(origin,selected);
            }
            if(selected?.ok||selected?.blocked)break;
          }
        }
        if(!selected?.ok) {
          error=selected?.reason||'No se encontró el partido.';
          if(selected?.blocked){failures.push(match+': '+error);break;}
        } else {
          requireUpcomingTarget(target);
          const readTarget=sportium?{...target,verifiedStart:selected.verifiedStart,expectedEventId:selected.expectedEventId}:target;
          const read=()=>{
            requireUpcomingTarget(target);
            return readerTask(tab.id,{type:'read-target',target:readTarget,aliases:data.aliases},sportium?90000:Math.max(1,target.readDeadline-Date.now()+1000));
          };
          await waitForReader(tab.id,undefined,target.readDeadline);
          let result=await read().catch(()=>null);
          if(!result) {
            // A full document navigation closes the first message channel.
            requireUpcomingTarget(target);await waitForReader(tab.id,undefined,target.readDeadline);
            result=await read();
          }
          await savePublicDiagnostic(origin,result);
          if(!sportium){
            result=await retryEmptyPublicPage(tab,result,read,cancelled,progress);
            await savePublicDiagnostic(origin,result);
          }
          if(!result?.ok){
            error=result?.reason||'No apareció Resultado final.';
            if(result?.blocked){failures.push(match+': '+error);break;}
          }
          else {
            if(await cancelled())break;
            const received=await fetch(origin+'/'+source+'-scan-observation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result.payload)});
            if(received.ok)captured++;
            else error=(await received.json().catch(()=>null))?.reason||'Fecha, equipos o mercado no verificados por la app.';
          }
        }
      } catch(problem){error=/ya ha comenzado|Límite de espera/.test(problem.message)?problem.message:'Se perdió la conexión con la página de este partido.';}
      if(error)failures.push(match+': '+error);
      processed++;
      await progress(match,error);
    }
  } catch(error){failures.push(error.message||(sportium?'No se pudo leer el catálogo de Sportium.':'No se pudo completar la búsqueda automática.'));}
  finally {if(tab)await chrome.tabs.remove(tab.id).catch(()=>{});}
  await fetch(origin+'/bet365-scan-complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source,captured,failures,continuing})});
  await chrome.storage.local.set({status:`${label} terminada: ${captured} con cuotas de ${processed} revisados.${failures.length?' Último error: '+failures[failures.length-1]:''}`});
  return {ok:!(await cancelled()),captured,failures,reason:(await cancelled())?'cancelled':undefined};
}
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  if(sender.url && ['http://127.0.0.1:8802','http://127.0.0.1:8803'].includes(new URL(sender.url).origin) && message.type==='automatic-bet365-scan') {
    if(activeScan){respond({ok:false,reason:'busy'});return false;}
    activeScan=(async()=>{
      const sources=[...new Set(message.filter?.sources||['bet365'])].filter(s=>['winamax_es','betfair_sb','bet365','sportium','retabet'].includes(s));
      let captured=0;const failures=[];
      for(const [index,source] of sources.entries()){const result=await (source==='retabet'?scanRetabet(new URL(sender.url).origin,index<sources.length-1):['winamax_es','betfair_sb'].includes(source)?scanDirectSource(new URL(sender.url).origin,source,index<sources.length-1):scanAutomatically(new URL(sender.url).origin,message.filter||{},source,index<sources.length-1));if(!result.ok)return result;captured+=result.captured;failures.push(...result.failures);}
      return {ok:true,captured,failures};
    })().finally(()=>{activeScan=null;});
    activeScan.then(respond).catch(()=>respond({ok:false,captured:0,reason:'reader-error'}));
    return true;
  }
  if (sender.url && new URL(sender.url).origin === 'http://127.0.0.1:8802' && message.type==='refresh-open-bet365') {
    chrome.storage.local.get('enabled').then(async settings=>{
      if(!settings.enabled){respond({ok:false,captured:0,reason:'disabled'});return;}
      const tabs=await chrome.tabs.query({url:'https://www.bet365.es/*'});
      const results=[];
      for(const tab of tabs) results.push(await readerTask(tab.id,{type:'capture-now'}).catch(()=>({ok:false})));
      const captured=results.filter(r=>r?.ok).length;
      respond({ok:captured>0,captured,opened:tabs.length});
    }).catch(()=>respond({ok:false,captured:0}));
    return true;
  }
  if (!sender.url || new URL(sender.url).hostname !== 'www.bet365.es') return false;
  if (message.type==='reader-status') {
    if(activeScan){respond({ok:false});return false;}
    chrome.storage.local.set({status:message.message});
    respond({ok:false});return false;
  }
  if (message.type!=='bet365-observation') return false;
  // Incognito is a separate session and can hide enhanced prices.
  if(sender.tab?.incognito){respond({ok:false,reason:'incognito'});return false;}
  chrome.storage.local.get('enabled').then(async settings=>{
    if(!settings.enabled){respond({ok:false});return;}
    try{
      const response=await fetch('http://127.0.0.1:8802/bet365-feed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(message.payload)});
      if(!response.ok)throw new Error('La app rechazó la lectura.');
      const data=await response.json();
      await chrome.storage.local.set({status:`Lectura enviada: ${data.events} partido(s).`,lastCapture:message.payload.observed_at});
      respond({ok:true});
    }catch(error){
      await chrome.storage.local.set({status:'No se pudo enviar la lectura. Abre la app en 127.0.0.1:8802.'});
      respond({ok:false});
    }
  });
  return true;
});
