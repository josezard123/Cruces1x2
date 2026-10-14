async function waitForExchangeReader(ask,expectedUrl){
 // Creating a tab does not mean its document_idle content script is ready.
 // Missing receivers and the old document during navigation are transient.
 for(let attempt=0,deadline=Date.now()+30000;attempt<60&&Date.now()<deadline;attempt++){
  try{const reply=await ask({type:'exchange-ping'},5000);if(reply?.ok&&reply.url===expectedUrl)return;}
  catch(_){}
  await new Promise(resolve=>setTimeout(resolve,500));
 }
 throw Error('connection');
}
async function scanExchange(origin,source){
 let tab,captured=0,partial=false,read=0,teams=0,inspection={};
 const status=state=>fetch(origin+'/freebets/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state,captured,read,teams,inspection})});
 try{
  const settings=await chrome.storage.local.get('enabled');
  if(!settings.enabled)return {ok:false,reason:'disabled'};
  const data=await(await fetch(origin+'/freebets/targets?source='+encodeURIComponent(source))).json();
  if(!data.targets?.length){await status('empty');return {ok:false,reason:'empty'};}
  await status('reading');
  const laLigaOnly=data.targets.every(t=>t.league_key==='laliga');
  const championsOnly=data.targets.every(t=>t.league_key==='ucl');
  // Both competition links were verified in the public Exchange navigation.
  // Avoid walking the general football catalogue for a single known league.
  const firstUrl=laLigaOnly?'https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/la-liga-espa%C3%B1ola-apuestas-117':championsOnly?'https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/uefa-champions-league-apuestas-228':'https://www.betfair.es/exchange/plus/es/f%C3%BAtbol-apuestas-1';
  tab=await chrome.tabs.create({url:firstUrl,active:false});
  let expectedUrl=firstUrl;
  const ask=(message,limit=90000)=>typeof readerTask==='function'?readerTask(tab.id,message,limit):chrome.tabs.sendMessage(tab.id,message);
  const canonical=value=>{let n=value.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/&/g,' and ').replace(/[^a-z0-9]+/g,' ').trim();n=data.aliases[n]||n;n=n.split(' ').filter(w=>!['fc','cf','afc','sc','ac','club','futbol','football'].includes(w)).join(' ');return (data.aliases[n]||n).replace(/ club/g,'');};
  const found=new Set(),visited=new Set();
  for(let page=0;page<20;page++){
   let response;
   try{await waitForExchangeReader(ask,expectedUrl);response=await ask({type:'exchange-coupon'});}
   catch(_){await status('connection');return {ok:false,captured,reason:'connection'};}
   inspection=response?.inspection||response?.payload?.inspection||{};
   if(!response?.ok){const reason=response?.reason||'connection';await status(reason);return {ok:false,captured,reason};}
   const payload=response.payload;
   read+=payload.events.length;
   teams+=payload.events.filter(e=>data.targets.some(t=>canonical(e.home)===t.canonical_home&&canonical(e.away)===t.canonical_away)).length;
   const selected=payload.events.filter(e=>data.targets.some(t=>canonical(e.home)===t.canonical_home&&canonical(e.away)===t.canonical_away&&Math.abs(Date.parse(e.start)-Date.parse(t.start))<=60000));
   if(selected.length){
    const imported=await fetch(origin+'/freebets/exchange-observation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,events:selected})});
    if(!imported.ok)throw Error('import');
    captured+=(await imported.json()).captured;
    for(const e of selected)found.add(canonical(e.home)+'|'+canonical(e.away)+'|'+Date.parse(e.start));
    await status('reading');
   }
   if(data.targets.every(t=>[...found].some(key=>{const parts=key.split('|');return parts[0]===t.canonical_home&&parts[1]===t.canonical_away&&Math.abs(Number(parts[2])-Date.parse(t.start))<=60000;})))break;
   if(!payload.next||visited.has(payload.next))break;
   const next=new URL(payload.next);
   if(next.origin!=='https://www.betfair.es'||next.search||next.hash||!/^\/exchange\/plus\/es\/fútbol-apuestas-1(?:\/\d+)?$/.test(decodeURIComponent(next.pathname)))break;
   if(page===19){partial=true;break;}
   visited.add(payload.next);expectedUrl=payload.next;await chrome.tabs.update(tab.id,{url:expectedUrl});
  }
  const reason=!captured?(read===0?'no_lay':teams===0?'teams':'time'):undefined;
  await status(reason||(partial?'partial':'done'));return {ok:true,captured,partial,reason,read};
 }catch(_){await status('error').catch(()=>{});return {ok:false,captured};}
 finally{if(tab)await chrome.tabs.remove(tab.id).catch(()=>{});}
}
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(message.type!=='automatic-exchange-scan'||!sender.url)return false;
 const origin=new URL(sender.url).origin;
 if(!['http://127.0.0.1:8802','http://127.0.0.1:8803'].includes(origin))return false;
 if(activeScan){respond({ok:false,reason:'busy'});return false;}
 if(!['bet365','winamax_es','betfair_sb','sportium'].includes(message.source))return false;
 activeScan=scanExchange(origin,message.source).finally(()=>{activeScan=null;});
 activeScan.then(respond).catch(()=>respond({ok:false}));return true;
});
