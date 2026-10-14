// Public sports DOM only. Uses the date/team helpers in direct.js.
function retaURL(path,event=false){
 try{
  const u=new URL(path,'https://apuestas.retabet.es');
  const pattern=event?/^\/deportes\/futbol\/[^/]+\/[^/]+\/[^/]+\/\d+$/:/^\/deportes\/futbol\/[^/]+\/[^/]+\/\d+$/;
  if(u.protocol!=='https:'||u.hostname!=='apuestas.retabet.es'||u.search||u.hash||u.username||u.password||!pattern.test(decodeURIComponent(u.pathname)))return null;
  return u.href;
 }catch(_){return null;}
}
function retaCompetition(name,path){
 const url=retaURL(path);if(!url)return null;
 const region=decodeURIComponent(new URL(url).pathname).split('/')[3];
 const countries={espana:'España',inglaterra:'Inglaterra',italia:'Italia',alemania:'Alemania',francia:'Francia',portugal:'Portugal','paises-bajos':'Países Bajos',europa:'Europa'};
 const country=countries[region];if(!country)return null;
 let normalized=name.trim();
 if(/^UEFA Nations League - Liga [ABCD]$/i.test(normalized))normalized='UEFA Nations League';
 const key=directCompetition(normalized.replace(/^UEFA Nations League$/i,'Nations League'),country);
 if(!key||(['ucl','uel','uecl'].includes(key)&&region!=='europa'))return null;
 return {url,name:normalized,country,key};
}
async function discoverReta(settings){
 await directWait(()=>document.querySelector('main a.verticalnav__link[href*="/deportes/futbol/"]'));
 const found=new Map();
 // These are public competition links in the navigation menu, including
 // collapsed country sections. No application state or network responses.
 for(const a of document.querySelectorAll('main a.verticalnav__link[href]')){
  const competition=retaCompetition(a.textContent.trim(),a.getAttribute('href'));
  if(competition&&settings.leagues.includes(competition.key))found.set(competition.url,competition);
 }
 return [...found.values()].slice(0,40);
}
function retaCatalogueSnapshot(){
 return [...document.querySelectorAll('main .event__item')].filter(n=>n.getClientRects().length).map(n=>({
  path:n.querySelector('a.event__players')?.getAttribute('href'),
  teams:[...n.querySelectorAll('.event__players-name span')].map(e=>e.innerText.trim()),
  day:n.querySelector('.event__day')?.innerText.trim(),time:n.querySelector('.event__time')?.innerText.trim(),live:n.getAttribute('data-il')
 }));
}
function retaDate(day,time,now=new Date()){
 const numeric=/^(\d{1,2})\/(\d{1,2})(?:\/(\d{4}))?$/.exec(String(day||'').trim());
 if(!numeric)return directWinaDate(day,time,now);
 const clock=/^(\d{1,2}):(\d{2})$/.exec(String(time||''));
 if(!clock||+clock[1]>23||+clock[2]>59||+numeric[2]<1||+numeric[2]>12)throw Error('Fecha pública de RETAbet no válida.');
 let year=+(numeric[3]||directMadridParts(now).year);
 let date=directMadridDate(year,+numeric[2]-1,+numeric[1],+clock[1],+clock[2]);
 if(!numeric[3]&&date<now-180*86400000)date=directMadridDate(++year,+numeric[2]-1,+numeric[1],+clock[1],+clock[2]);
 return date;
}
function parseRetaCatalogue(rows,competition,settings,now=new Date()){
 const events=new Map();
 for(const row of rows){try{
  const url=retaURL(row.path,true);if(!url||row.live!=='0'||row.teams.length!==2)continue;
  if(new URL(url).pathname.split('/').slice(0,5).join('/')!==new URL(competition.url).pathname.split('/').slice(0,5).join('/'))continue;
  const start=retaDate(row.day,row.time,now);
  if(start<=now||start-now>settings.hours*3600000)continue;
  events.set(url,{url,event_id:new URL(url).pathname.split('/').pop(),home:row.teams[0],away:row.teams[1],start:start.toISOString(),competition});
 }catch(_){}}
 return [...events.values()];
}
async function readRetaCatalogue(competition,settings){
 await directWait(()=>document.querySelector('main .event__item'));
 return parseRetaCatalogue(retaCatalogueSnapshot(),competition,settings);
}
function retaEventSnapshot(){
 const header=document.querySelector('main .info-event');
 return {url:location.href,home:header?.querySelector('.players-left__player')?.innerText.trim(),away:header?.querySelector('.players-right__player')?.innerText.trim(),
  date:[...header?.querySelectorAll('.info-event__players-center span')||[]].map(n=>n.innerText.trim()),
  competitions:[...header?.querySelectorAll('.breadcrumbs__item a[href]')||[]].map(a=>({name:a.innerText.trim(),path:a.getAttribute('href')})).filter(x=>retaURL(x.path)),
  markets:[...document.querySelectorAll('main .detail__bets-wrapper .bets__wrapper')].filter(n=>n.getClientRects().length).map(n=>({
   title:n.querySelector('.bets__tit .mt')?.innerText.trim(),
   selections:[...n.querySelectorAll('.bets__option-list .betbox')].map(b=>({name:b.querySelector('.betbox__option')?.innerText.trim(),price:b.querySelector('.jpr')?.innerText.trim(),
    active:!!b.getClientRects().length&&b.getAttribute('aria-disabled')!=='true'&&!/disabled|suspend|locked/i.test(b.className)&&![...b.querySelectorAll('.icon-lock')].some(lock=>lock.getClientRects().length>0)}))
  }))};
}
function parseRetaEvent(snapshot,target,settings,now=new Date()){
 const url=retaURL(snapshot.url,true);
 if(!url||url!==target.url||new URL(url).pathname.split('/').pop()!==target.event_id)throw Error('No coincide el evento de RETAbet.');
 if(directTeam(snapshot.home,settings.aliases)!==directTeam(target.home,settings.aliases)||directTeam(snapshot.away,settings.aliases)!==directTeam(target.away,settings.aliases))throw Error('Los equipos de RETAbet no coinciden.');
 if(snapshot.date.length!==2)throw Error('Falta la fecha pública de RETAbet.');
 const start=retaDate(snapshot.date[0],snapshot.date[1],now);
 if(start<=now||start-now>settings.hours*3600000||!Number.isFinite(Date.parse(target.start))||Math.abs(+start-Date.parse(target.start))>60000)throw Error('La fecha de RETAbet no coincide con el partido prepartido.');
 const competitions=snapshot.competitions.map(c=>retaCompetition(c.name,c.path)).filter(Boolean);
 if(competitions.length!==1||competitions[0].key!==target.competition.key||!settings.leagues.includes(competitions[0].key))throw Error('La competición de RETAbet no coincide.');
 const markets=snapshot.markets.filter(m=>directClean(m.title)==='1 x 2 ventaja 2 goles');
 if(markets.length!==1)throw Error('No hay un único 1-X-2 / Ventaja 2 goles en RETAbet.');
 const selections=markets[0].selections;
 if(selections.length!==3||selections.some((s,i)=>s.name!==['1','X','2'][i]))throw Error('No se reconocen los signos 1, X y 2 de RETAbet.');
 const odds=directPrices(selections);if(!odds)throw Error('RETAbet no tiene tres cuotas activas de Ventaja 2 goles.');
 return {event_id:target.event_id,home:snapshot.home,away:snapshot.away,league:competitions[0].name,country:competitions[0].country,start:start.toISOString(),odds,market:'FULL_TIME_1X2',payout:'two_goals',source_url:url};
}
async function readRetaEvent(target,settings){
 await directWait(()=>{
  const s=retaEventSnapshot();return s.date.length===2&&directTeam(s.home,settings.aliases)===directTeam(target.home,settings.aliases)&&directTeam(s.away,settings.aliases)===directTeam(target.away,settings.aliases)&&s.markets.length;
 });
 let snapshot=retaEventSnapshot();
 const market=snapshot.markets.filter(m=>directClean(m.title)==='1 x 2 ventaja 2 goles');
 if(market.length===1&&!market[0].selections.length){
  const node=[...document.querySelectorAll('main .detail__bets-wrapper .bets__wrapper')].find(n=>n.getClientRects().length&&directClean(n.querySelector('.bets__tit .mt')?.innerText)==='1 x 2 ventaja 2 goles');
  node?.querySelector('.bets__tit')?.click();
  await directWait(()=>retaEventSnapshot().markets.some(m=>directClean(m.title)==='1 x 2 ventaja 2 goles'&&m.selections.length===3));snapshot=retaEventSnapshot();
 }
 return {observed_at:new Date().toISOString(),events:[parseRetaEvent(snapshot,target,settings)]};
}
if(typeof chrome!=='undefined')chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(location.hostname!=='apuestas.retabet.es')return false;
 if(message.type==='retabet-ping'){respond({ok:true,url:location.href,ready:document.readyState==='complete'});return false;}
 const handlers={'retabet-discover':()=>discoverReta(message.settings),'retabet-catalogue':()=>readRetaCatalogue(message.competition,message.settings),'retabet-event':()=>readRetaEvent(message.target,message.settings)};
 if(!handlers[message.type])return false;
 handlers[message.type]().then(data=>respond({ok:true,...(message.type==='retabet-discover'?{competitions:data}:message.type==='retabet-catalogue'?{events:data}:{payload:data})})).catch(error=>respond({ok:false,blocked:/bloqueó/.test(error.message),reason:error.message}));return true;
});
