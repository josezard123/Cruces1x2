// Public coupon DOM only. No cookies, forms, credentials, page state or API calls.
function directClean(text){return String(text||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim();}
function directTeam(text,aliases={}){let name=directClean(text);name=aliases[name]||name;name=name.split(' ').filter(x=>!['fc','cf','afc','sc','ac','club','futbol','football'].includes(x)).join(' ');return directClean(aliases[name]||name);}
function directCompetition(name,country){
 const n=directClean(name),c=directClean(country);
 if(/\(f\)|\bu[ -]?(17|18|19|20|21|23)\b|women|femen|juvenil|virtual|simulated|srl/i.test(name))return null;
 if(c==='espana'){
  if(n==='laliga'||n==='la liga espanola')return 'laliga';
  if(n==='segunda division'||n==='espana segunda division')return 'segunda';
  if(n==='copa del rey')return 'copadelrey';
 }
 if(c==='inglaterra'&&n==='premier league')return 'premier';
 if(c==='italia'&&n==='serie a')return 'seriea';
 if(c==='alemania'&&n==='bundesliga')return 'bundesliga';
 if(c==='francia'&&n.startsWith('ligue 1'))return 'ligue1';
 if(c==='portugal'&&/^(primeira liga|liga portugal|liga portugal betclic)$/.test(n))return 'primeira';
 if(['paises bajos','holanda'].includes(c)&&n==='eredivisie')return 'eredivisie';
 if(n==='champions league'||n==='uefa champions league')return 'ucl';
 if(n==='europa league'||n==='uefa europa league')return 'uel';
 if(n==='conference league'||n==='uefa conference league')return 'uecl';
 if(/^(nations league|liga de naciones|mundial|eurocopa|amistosos selecciones|amistosos internacionales|international friendlies|clasificacion mundial.*|clasificacion eurocopa.*|copa america|copa africa|copa del golfo)$/.test(n))return 'internationals';
 return null;
}
function directBfCountry(name){const n=directClean(name);if(n==='la liga espanola'||n.startsWith('espana ')||n==='copa del rey')return 'España';if(/inglesa|inglaterra|english/.test(n))return 'Inglaterra';if(/italia/.test(n))return 'Italia';if(/alemania|german/.test(n))return 'Alemania';if(/francia|french/.test(n))return 'Francia';if(/portugal/.test(n))return 'Portugal';if(/holand|paises bajos/.test(n))return 'Países Bajos';return 'Europa';}
function directBfName(name){const n=directClean(name);if(/premier league|premier inglesa/.test(n))return 'Premier League';if(/serie a.*italia|italia.*serie a/.test(n))return 'Serie A';if(/bundesliga/.test(n))return 'Bundesliga';if(/ligue 1/.test(n))return 'Ligue 1';if(/primeira liga|liga portugal/.test(n))return 'Primeira Liga';if(/eredivisie/.test(n))return 'Eredivisie';return name;}
function directBfCompetitionURL(path) {
 try{
  const url=new URL(path,'https://www.betfair.es/apuestas/');
  if(url.protocol!=='https:'||url.hostname!=='www.betfair.es'||url.search||url.hash||url.username||url.password||!/^\/apuestas\/fútbol\/[^/]+\/c-\d+$/.test(decodeURIComponent(url.pathname)))return null;
  return url.href;
 }catch(_){return null;}
}
function directMadridParts(date){return Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date).map(p=>[p.type,p.value]));}
function directMadridDate(year,month,day,hour,minute){
 let value=Date.UTC(year,month,day,hour,minute);
 for(let i=0;i<3;i++){const p=directMadridParts(new Date(value));value+=Date.UTC(year,month,day,hour,minute)-Date.UTC(+p.year,+p.month-1,+p.day,+p.hour,+p.minute);}
 const result=new Date(value),p=directMadridParts(result);
 if(+p.year!==year||+p.month!==month+1||+p.day!==day||+p.hour!==hour||+p.minute!==minute)throw Error('Fecha no válida.');
 return result;
}
function directWinaDate(dayLabel,timeLabel,now=new Date()){
 const t=/^(\d{1,2}):(\d{2})$/.exec(timeLabel||'');if(!t||+t[1]>23||+t[2]>59)throw Error('Hora no reconocida.');
 const p=directMadridParts(now);let date=new Date(Date.UTC(+p.year,+p.month-1,+p.day));
 const label=directClean(dayLabel),weekdays={do:0,dom:0,su:0,lu:1,lun:1,mo:1,ma:2,mar:2,tu:2,mi:3,mie:3,we:3,ju:4,jue:4,th:4,vi:5,vie:5,fr:5,sa:6,sab:6,sat:6};
 if(label==='manana')date.setUTCDate(date.getUTCDate()+1);
 else if(label==='hoy'||label==='today'){}
 else if(label in weekdays)date.setUTCDate(date.getUTCDate()+(weekdays[label]-date.getUTCDay()+7)%7);
 else {const match=/^(\d{1,2})\s+(ene|jan|feb|mar|abr|apr|may|jun|jul|ago|aug|sep|oct|nov|dic|dec)$/.exec(label);if(!match)throw Error('Fecha no reconocida.');const months={ene:0,jan:0,feb:1,mar:2,abr:3,apr:3,may:4,jun:5,jul:6,ago:7,aug:7,sep:8,oct:9,nov:10,dic:11,dec:11};date=new Date(Date.UTC(+p.year,months[match[2]],+match[1]));if(date<now-180*86400000)date.setUTCFullYear(date.getUTCFullYear()+1);}
 return directMadridDate(date.getUTCFullYear(),date.getUTCMonth(),date.getUTCDate(),+t[1],+t[2]);
}
function directPrices(items){if(items.length!==3||items.some(x=>!x.active||!/^\d+(?:[.,]\d+)?$/.test(x.price||'')))return null;const values=items.map(x=>Number(x.price.replace(',','.')));return values.every(x=>Number.isFinite(x)&&x>1&&x<=1000)?{'1':values[0],X:values[1],'2':values[2]}:null;}
function parseDirectWina(snapshot,competition,settings,now=new Date()){
 const events=[];
 for(const card of snapshot.cards){
  try{
   const odds=directPrices(card.odds);if(!odds||!/^\d+$/.test(card.id))continue;
   const lines=card.lines,league=lines[0].replace(/J\d+$/,'').trim();
   if(directCompetition(league,competition.country)!==competition.key)continue;
   // The public coupon omits "Hoy" on today's cards. Tomorrow and later days
   // have an additional date line; live scores cannot satisfy either layout.
   const today=/^\d{1,2}:\d{2}$/.test(lines[2]||'');
   const home=lines[1],away=lines[today?3:4],start=directWinaDate(today?'Hoy':lines[2],lines[today?2:3],now);
   if(!home||!away||start<=now||start-now>settings.hours*3600000)continue;
   // Selection names may have known abbreviations; require canonical team agreement.
   const names=card.odds.map(x=>x.text.split('\n').map(s=>s.trim()).filter(s=>s&&!/^\d/.test(s)&&!s.includes('%')).pop());
   if(directClean(names[1])!=='empate'||directTeam(names[0],settings.aliases)!==directTeam(home,settings.aliases)||directTeam(names[2],settings.aliases)!==directTeam(away,settings.aliases))continue;
   events.push({event_id:card.id,home,away,league:competition.name,country:competition.country,start:start.toISOString(),odds,market:'FULL_TIME_1X2',payout:'normal',source_url:'https://www.winamax.es/apuestas-deportivas/match/'+card.id});
  }catch(_){}
 }
 return events;
}
function parseDirectBf(snapshot,competition,settings,now=new Date()){
 const market=directClean(snapshot.market?.split('\n').pop());
 if(!['resultados','resultado 2 goles de ventaja'].includes(market))return [];
 const events=[];
 for(const row of snapshot.rows){
  const odds=directPrices(row.buttons),start=new Date(row.date),id=/\/e-(\d+)$/.exec(row.path)?.[1];
  if(!odds||!id||row.teams.length!==2||!/(?:GMT[+-]\d{4}|[zZ]$|[+-]\d{2}:\d{2}$)/.test(row.date||'')||!Number.isFinite(+start)||start<=now||start-now>settings.hours*3600000)continue;
  const url=new URL(row.path,'https://www.betfair.es/apuestas/');
  if(url.hostname!=='www.betfair.es'||url.search||url.hash||!/^\/apuestas\/f%C3%BAtbol\/[^/]+\/[^/]+\/e-\d+$/i.test(url.pathname))continue;
  events.push({event_id:id,home:row.teams[0],away:row.teams[1],league:competition.name,country:competition.country,start:start.toISOString(),odds,market:'FULL_TIME_1X2',payout:market==='resultados'?'normal':'two_goals',source_url:url.href});
 }
 return events;
}
function directWinaSnapshot(){return {cards:[...document.querySelectorAll('[data-testid^="match-card-"]')].filter(n=>n.getClientRects().length).map(n=>({id:n.getAttribute('data-testid').replace('match-card-',''),lines:n.innerText.split('\n').map(s=>s.trim()).filter(Boolean),odds:[...n.querySelectorAll('.odd-button-wrapper')].map(b=>({text:b.innerText,price:b.querySelector('.odd-button-value')?.innerText,active:b.getClientRects().length>0&&b.getAttribute('aria-disabled')!=='true'&&!/disabled|suspend/i.test(b.className)}))}))};}
function directBfSnapshot(){return {market:[...document.querySelectorAll('button')].find(n=>/seleccionar mercado/i.test(n.innerText))?.innerText,rows:[...document.querySelectorAll('a[href*="/e-"]')].filter(n=>n.getClientRects().length).map(n=>({path:n.getAttribute('href'),teams:[...n.querySelectorAll('[data-testid="team-name"]')].map(t=>t.innerText),date:n.querySelector('time')?.getAttribute('datetime'),buttons:[...n.parentElement.querySelectorAll('button')].filter(b=>/^\d+(?:[.,]\d+)?$/.test(b.innerText.trim())).map(b=>({price:b.innerText.trim(),active:b.getClientRects().length>0&&!b.disabled&&b.getAttribute('aria-disabled')!=='true'}))}))};}
async function directWait(check,milliseconds=30000){
 // Inactive Chrome tabs throttle repeated timers. Observe DOM changes instead.
 return new Promise((resolve,reject)=>{
  let observer,timer,finished=false;
  const finish=(value,error)=>{if(finished)return;finished=true;observer?.disconnect();clearTimeout(timer);error?reject(error):resolve(value);};
  const inspect=()=>{try{if(/access denied|acceso denegado|verify you are human|verifica que eres humano/i.test(document.body.innerText))throw Error('La web bloqueó la lectura pública.');const value=check();if(value)finish(value);}catch(error){finish(null,error);}};
  observer=new MutationObserver(inspect);observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,characterData:true});
  timer=setTimeout(()=>finish(null,Error('La web no cargó los partidos antes del límite de espera.')),milliseconds);inspect();
 });
}
function directScrollHost(anchor){
 for(let node=anchor?.parentElement;node;node=node.parentElement){
  if(node.clientHeight>0&&node.scrollHeight>node.clientHeight+2 &&
    (String(node.className||'').includes('ReactVirtualized__Grid')||/auto|scroll/.test(getComputedStyle(node).overflowY)))return node;
 }
 return null;
}
function directCardSignature(wina){
 return [...document.querySelectorAll(wina?'[data-testid^="match-card-"]':'a[href*="/e-"]')].map(n=>wina?n.getAttribute('data-testid'):n.getAttribute('href')).join('|');
}
async function directMoveGrid(grid,position,wina){
 const before=directCardSignature(wina);grid.scrollTop=position;
 if(!String(grid.className||'').includes('ReactVirtualized'))return;
 // A virtual list renders the next cards asynchronously. No timer-poll chain.
 try{await directWait(()=>directCardSignature(wina)!==before,5000);}catch(error){if(/bloqueó/.test(error.message))throw error;}
}
async function discoverDirect(settings){
 const wina=location.hostname==='www.winamax.es';
 const hasCompetition=()=>[...document.querySelectorAll('a')].some(n=>wina?/^\/apuestas-deportivas\/sports\/1\/\d+\/\d+$/.test(n.getAttribute('href')||''):directBfCompetitionURL(n.getAttribute('href')||''));
 if(!wina){
  // Some coupons already contain competition links without a tablist.
  await directWait(()=>hasCompetition()||[...document.querySelectorAll('[role="tab"]')].find(n=>n.innerText.trim()==='Competiciones'));
  if(!hasCompetition()){
   const tab=[...document.querySelectorAll('[role="tab"]')].find(n=>n.innerText.trim()==='Competiciones');
   if(!tab)throw Error('No apareció Competiciones.');tab.click();
  }
 }
 await directWait(hasCompetition);
 const found=new Map();
 for(const link of document.querySelectorAll('a')){
  const path=link.getAttribute('href')||'',name=link.innerText.trim();let country,key,normalized=name;
  if(wina){if(!/^\/apuestas-deportivas\/sports\/1\/\d+\/\d+$/.test(path))continue;country=link.parentElement?.parentElement?.parentElement?.parentElement?.innerText.split('\n')[0];key=directCompetition(name,country);}
  else{if(!directBfCompetitionURL(path))continue;country=directBfCountry(name);normalized=directBfName(name);key=directCompetition(normalized,country);}
  if(!key||!settings.leagues.includes(key))continue;
  const url=wina?new URL(path,'https://www.winamax.es').href:directBfCompetitionURL(path);
  found.set(url,{url,name:normalized,country,key});
 }
 return [...found.values()].slice(0,40);
}
async function readDirectCompetition(competition,settings){
 const wina=location.hostname==='www.winamax.es';
 if(wina){
  const result=await directWait(()=>[...document.querySelectorAll('.filter-button')].find(n=>n.innerText.trim()==='Resultado'));
  result.click();
 }
 if(!wina){
  const selector=await directWait(()=>[...document.querySelectorAll('button')].find(n=>/seleccionar mercado/i.test(n.innerText)));
  if(directClean(selector.innerText.split('\n').pop())!=='resultado 2 goles de ventaja'){
   selector.click();await directWait(()=>document.querySelector('[role="radio"],input[type="radio"]'));
   const options=[...document.querySelectorAll('[role="radio"],input[type="radio"]')];
   const enhanced=options.find(n=>directClean(n.getAttribute('aria-label')||(n.id?document.querySelector('label[for="'+n.id+'"]')?.innerText:'')||n.parentElement.parentElement?.innerText)==='resultado 2 goles de ventaja');
   const normal=options.find(n=>directClean(n.getAttribute('aria-label')||(n.id?document.querySelector('label[for="'+n.id+'"]')?.innerText:'')||n.parentElement.parentElement?.innerText)==='resultados');
   if(!(enhanced||normal))throw Error('No apareció el mercado de resultado final.');
   (enhanced||normal).click();
   await directWait(()=>['resultado 2 goles de ventaja','resultados'].includes(directClean(directBfSnapshot().market?.split('\n').pop())));
  }
 }
 await directWait(()=>wina?document.querySelector('[data-testid^="match-card-"] .odd-button-value'):document.querySelector('a[href*="/e-"] button')||document.querySelector('[class*="inlineSportsbookMarket"] button'));
 const events=new Map();
 const anchor=document.querySelector(wina?'[data-testid^="match-card-"]':'a[href*="/e-"]');
 const grid=directScrollHost(anchor);
 // Route changes can preserve an old scroll position. Always start at the top
 // of the list containing match cards, not the first virtual sidebar grid.
 if(grid&&grid.scrollTop>0)await directMoveGrid(grid,0,wina);
 for(let page=0;page<20;page++){
  const snapshot=wina?directWinaSnapshot():directBfSnapshot();
  for(const event of (wina?parseDirectWina:parseDirectBf)(snapshot,competition,settings))events.set(event.event_id,event);
  if(!grid||!String(grid.className||'').includes('ReactVirtualized')||grid.scrollHeight<=grid.clientHeight||grid.scrollTop+grid.clientHeight>=grid.scrollHeight-2)break;
  await directMoveGrid(grid,grid.scrollTop+Math.max(200,grid.clientHeight-100),wina);
 }
 return {observed_at:new Date().toISOString(),events:[...events.values()]};
}
function directDiagnostic(phase) {
 try{return typeof publicReaderDiagnostic==='function'?publicReaderDiagnostic(location.hostname==='www.winamax.es'?'winamax_es':'betfair_sb',phase):undefined;}catch(_){return undefined;}
}
if(typeof chrome!=='undefined')chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(message.type==='reader-ping'){respond({ok:true,url:location.href});return false;}
 if(message.type==='direct-discover'){discoverDirect(message.settings).then(competitions=>respond({ok:true,competitions})).catch(error=>respond({ok:false,blocked:/bloqueó/.test(error.message),reason:error.message,diagnostic:directDiagnostic('discover')}));return true;}
 if(message.type==='direct-read'){readDirectCompetition(message.competition,message.settings).then(payload=>respond({ok:true,payload,diagnostic:directDiagnostic('coupon')})).catch(error=>respond({ok:false,blocked:/bloqueó/.test(error.message),reason:error.message,diagnostic:directDiagnostic('coupon')}));return true;}
 return false;
});
