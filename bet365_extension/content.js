let enabled = false;
let busy = false;
let scanning = false;
async function capture() {
  if (!enabled || busy || scanning) return {ok:false};
  busy = true;
  try {
    const payload = await readWithEnhanced(readBet365Result());
    return await chrome.runtime.sendMessage({type:'bet365-observation',payload});
  } catch (error) {
    await chrome.runtime.sendMessage({type:'reader-status',message:error.message}).catch(()=>{});
    return {ok:false};
  } finally { busy = false; }
}
chrome.storage.local.get('enabled').then(data=>{enabled=Boolean(data.enabled);capture();});
chrome.storage.onChanged.addListener(changes=>{if(changes.enabled){enabled=Boolean(changes.enabled.newValue);capture();}});
setInterval(capture, 60000);
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  if(message.type==='reader-ping'){respond({ok:true,url:location.href});return false;}
  if(message.type==='scan-target'){
    scanTarget(message.target,message.aliases).then(respond).catch(()=>respond({ok:false,reason:'No se pudo leer el encuentro.'}));
    return true;
  }
  if(message.type==='read-target'){
    readTarget(message.target,message.aliases).then(respond).catch(()=>respond({ok:false,reason:'No se pudo leer Resultado final.'}));
    return true;
  }
  if(message.type!=='capture-now') return false;
  capture().then(respond);
  return true;
});

async function waitFor(check,milliseconds=15000) {
  // DOM changes arrive even when Chrome throttles timers in inactive tabs.
  return new Promise((resolve,reject)=>{
    let observer,timer;
    const finish=(value,error)=>{observer?.disconnect();clearTimeout(timer);error?reject(error):resolve(value);};
    const inspect=()=>{
      try {const value=check();if(value)finish(value);}
      catch(error){finish(null,error);}
    };
    observer=new MutationObserver(inspect);
    observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true});
    timer=setTimeout(()=>finish(null,new Error('La web no cargó el elemento esperado.')),milliseconds);
    inspect();
  });
}
function normalizeTeam(value,aliases) {
  const clean=s=>s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/&/g,' and ').replace(/[^a-z0-9]+/g,' ').trim();
  let name=clean(value);name=aliases[name]||name;
  name=name.split(' ').filter(s=>!['fc','cf','afc','sc','ac','club','futbol','football'].includes(s)).join(' ');
  return clean(aliases[name]||name);
}
function matchesSearchHeader(text,target,aliases){
 let teams=String(text||'').trim().split(/\s+v(?:s\.?)?\s+/i);
 if(teams.length!==2){
  const lines=String(text||'').split('\n').map(s=>s.trim()).filter(Boolean);
  teams=lines.length===2?lines:lines.length===3&&/^v(?:s\.?)?$/i.test(lines[1])?[lines[0],lines[2]]:[];
 }
 return teams.length===2&&normalizeTeam(teams[0],aliases)===target.canonical_home&&normalizeTeam(teams[1],aliases)===target.canonical_away;
}
function enhancedMarketControl(payload) {
  const main=document.querySelector('[role="main"]');
  if(!main)return null;
  const visible=n=>n.getClientRects().length>0;
  const names=['resultado final - cuotas mejoradas','full time result - enhanced prices'];
  const titles=[...main.querySelectorAll('*')].filter(n=>!n.children.length && visible(n) &&
    names.includes((n.innerText||'').trim().toLowerCase().replace(/[–—]/g,'-').replace(/\s+/g,' ')));
  if(titles.length!==1)return null;
  const title=titles[0];let header=null;
  for(let node=title.parentElement;node && node!==main;node=node.parentElement){
    if(!header && node.getAttribute('role')==='button')header=node;
    const leaves=[...node.querySelectorAll('*')].filter(n=>!n.children.length && visible(n));
    if(leaves.some(n=>n!==title && /^(resultado final|full time result)/i.test((n.innerText||'').trim())))break;
    const labels=leaves.map(n=>(n.innerText||'').trim());
    if([payload.events[0].home,payload.events[0].away].every(team=>labels.includes(team)) &&
       labels.some(label=>/^(empate|draw)$/i.test(label)))return {header,expanded:true};
  }
  return header?{header,expanded:false}:null;
}
async function readWithEnhanced(payload,milliseconds=6000) {
  if(payload.events[0].enhanced_odds)return payload;
  const control=enhancedMarketControl(payload);
  if(!control)return payload;
  // Only expand the market heading, never a price or promotion button.
  if(!control.expanded)control.header.click();
  try {
    return await waitFor(()=>{
      try {
        const current=readBet365Result(),original=payload.events[0],event=current.events[0];
        if(event.event_id!==original.event_id || event.home!==original.home || event.away!==original.away || event.start!==original.start)return null;
        return event.enhanced_odds?current:null;
      }catch(_){return null;}
    },milliseconds);
  }catch(_){return payload;} // Missing enhanced prices do not remove verified normal odds.
}
async function scanTarget(target,aliases) {
  if(scanning)return {ok:false,reason:'Ya hay una lectura en curso.'};
  scanning=true;
  try {
    if(document.body.innerText.match(/access denied|acceso denegado|verify you are human|verifica que eres humano/i))
      return {ok:false,blocked:true,reason:'La web bloqueó el acceso; lectura detenida.'};
    // Background navigates to the public search URL for this team.
    // Avoid carrying an input or message channel across document navigation.
    const find=()=>[...document.querySelectorAll('*')].filter(row=>{
      if(row.getClientRects().length===0)return false;
      return matchesSearchHeader(row.innerText,target,aliases);
    }).filter(row=>![...row.children].some(child=>child.innerText===row.innerText));
    const rows=await waitFor(()=>{const found=find();return found.length?found:null;},30000);
    if(rows.length!==1)return {ok:false,reason:'La búsqueda no identifica un único partido.'};
    rows[0].click();
    return {ok:true,navigated:true};
  } catch(error) {return {ok:false,reason:error.message==='La web no cargó el elemento esperado.'?
    'La búsqueda no mostró este encuentro antes del límite de espera.':error.message};}
  finally {scanning=false;}
}

async function readTarget(target,aliases) {
  scanning=true;
  let lastError='No apareció Resultado final para este encuentro.';
  try {
    const payload=await waitFor(()=>{
      try {
        if(!/\/E\d+\//.test(location.hash||''))return null;
        const candidate=readBet365Result();
        if(normalizeTeam(candidate.events[0].home,aliases)!==target.canonical_home || normalizeTeam(candidate.events[0].away,aliases)!==target.canonical_away) return null;
        return candidate;
      } catch(error){lastError=error.message;return null;}
    },30000);
    if(Math.abs(new Date(payload.events[0].start)-new Date(target.start))>900000)return {ok:false,reason:'Hora distinta; partido excluido.'};
    return {ok:true,payload:await readWithEnhanced(payload)};
  } catch(_){return {ok:false,reason:lastError};}
  finally{scanning=false;}
}
