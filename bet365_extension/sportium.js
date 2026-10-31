function readSportiumVisibleMarket() {
  const main=document.querySelector('main');
  if(!main)throw new Error('No apareció el evento de Sportium.');
  const home=main.querySelector('.ta-firstParticipantName')?.innerText.trim();
  const away=main.querySelector('.ta-secondParticipantName')?.innerText.trim();
  const league=main.querySelector('.ta-titleText')?.innerText.trim();
  if(!home||!away||!league)throw new Error('Falta la cabecera de Sportium.');
  const markets=[...main.querySelectorAll('.ta-AggregatedMarket')].filter(n=>n.getClientRects().length &&
    n.querySelector('.headerText')?.innerText.trim()==='Ganador (1X2)');
  if(markets.length!==1)throw new Error('No hay un único Ganador (1X2) normal.');
  const rows=[...markets[0].querySelectorAll('.ta-SelectionButtonView')].map(n=>{
    const [name,price]=n.innerText.split('\n').map(s=>s.trim()).filter(Boolean);
    return {name,price:/^\d+(?:[.,]\d+)?$/.test(price||'')?Number(price.replace(',','.')):NaN,
      active:n.getClientRects().length>0 && n.getAttribute('aria-disabled')!=='true' && !n.classList.contains('suspended')};
  });
  if(rows.length!==3||rows.some(n=>!n.active||!Number.isFinite(n.price)||n.price<=1)||
    rows[0].name!==home||rows[1].name!=='Empate'||rows[2].name!==away)throw new Error('El 1-X-2 no tiene tres selecciones verificadas.');
  return {home,away,league,odds:{'1':rows[0].price,'X':rows[1].price,'2':rows[2].price}};
}
function sportiumTeam(value,aliases) {
  const clean=s=>s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/&/g,' and ').replace(/[^a-z0-9]+/g,' ').trim();
  let name=clean(value);name=aliases[name]||name;
  name=name.split(' ').filter(s=>!['fc','cf','afc','sc','ac','club','futbol','football'].includes(s)).join(' ');
  return clean(aliases[name]||name);
}
function sportiumStart(label,now=new Date()) {
  const match=/^(Hoy|Mañana|\d{1,2}\s+(?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\s+(\d{1,2}):(\d{2})$/i.exec(label);
  if(!match||Number(match[2])>23||Number(match[3])>59)throw new Error('No se reconoce la fecha pública de Sportium.');
  const date=new Date(now.getFullYear(),now.getMonth(),now.getDate(),Number(match[2]),Number(match[3]));
  if(match[1].toLowerCase()==='mañana')date.setDate(date.getDate()+1);
  else if(match[1].toLowerCase()!=='hoy'){
    const [day,month]=match[1].toLowerCase().split(/\s+/);
    date.setMonth(['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'].indexOf(month),Number(day));
    if(date<now-180*86400000)date.setFullYear(date.getFullYear()+1);
  }
  if(date<=now||date-now>168*3600000)throw new Error('El evento de Sportium no está en la ventana prepartido.');
  return date.toISOString();
}
function sportiumWait(check,milliseconds=20000){
  return new Promise((resolve,reject)=>{
    let observer,timer,done=false;
    const finish=(value,error)=>{if(done)return;done=true;observer?.disconnect();clearTimeout(timer);error?reject(error):resolve(value);};
    const inspect=()=>{try{if(/access denied|acceso denegado|verify you are human|verifica que eres humano/i.test(document.body.innerText))throw new Error('Sportium bloqueó el acceso; lectura detenida.');const result=check();if(result)finish(result);}catch(error){finish(null,error);}};
    observer=new MutationObserver(inspect);observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true});
    timer=setTimeout(()=>finish(null,new Error('Sportium no cargó el elemento esperado.')),milliseconds);inspect();
  });
}
function sportiumCompetitionKey(label) {
  let text=String(label||'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').replace(/\s+1\s+x\s+2\b.*$/,'');
  if(/\(f\)|women|femen|juvenil|\bu[ -]?(17|18|19|20|21|23)\b|virtual|simulated|srl/.test(text))return null;
  // Category spelling observed in the public Sportium event header.
  text=text.replace(/^competiciones uefa \(clubs\)\s*\/\s*/,'').replace(/\(competiciones uefa \(clubs\)\)$/,'(europa)').replace(/^futbol internacional\s*\/\s*/,'');
  const countries=[...text.matchAll(/\(([^)]+)\)/g)].map(m=>m[1].trim());
  const countryPrefix=/^(espana|inglaterra|italia|alemania|francia|portugal|paises bajos|holanda)\s*\/\s*/.exec(text);
  if(countryPrefix){countries.push(countryPrefix[1]);text=text.slice(countryPrefix[0].length);}
  const name=text.replace(/\([^)]*\)/g,'').trim().replace(/\s+/g,' ');
  const domestic=[
   ['laliga',/^(la liga|laliga|la liga espanola)$/,['espana']],
   ['segunda',/^segunda division$/,['espana']],
   ['copadelrey',/^copa del rey$/,['espana']],
   ['premier',/^(premier league|premier league inglesa)$/,['inglaterra']],
   ['seriea',/^serie a$/,['italia']],
   ['bundesliga',/^bundesliga$/,['alemania']],
   ['ligue1',/^ligue 1$/,['francia']],
   ['primeira',/^(primeira liga|liga portugal|liga portugal betclic)$/,['portugal']],
   ['eredivisie',/^eredivisie$/,['paises bajos','holanda']]
  ];
  for(const [key,pattern,allowed] of domestic)if(pattern.test(name)&&countries.every(c=>allowed.includes(c)))return key;
  if(countries.some(c=>!['europa','futbol internacional','internacional'].includes(c)))return null;
  if(/^(uefa )?(champions league|liga de campeones)$/.test(name))return 'ucl';
  if(/^(uefa )?europa league$/.test(name))return 'uel';
  if(/^(uefa )?conference league$/.test(name))return 'uecl';
  if(/^(?:(uefa|concacaf|afc|caf|conmebol|ofc) )?(nations league|liga de naciones)$/.test(name)||/^(amistosos selecciones|amistosos internacionales|copa africa|mundial|eurocopa|copa america|copa del golfo)$/.test(name))return 'internationals';
  return null;
}
function sportiumAllowedGroup(label,leagues=[]) {
  const key=sportiumCompetitionKey(label);return key!==null&&(!leagues.length||leagues.includes(key));
}
function sportiumListPrices(row,header) {
  // The public coupon labels its three MRES columns 1 / X / 2. Other markets
  // in the same row (totals, handicaps or enhanced prices) are never reused.
  if(!header||!row.querySelectorAll||!/\s+1\s+X\s+2(?:\s|$)/i.test(header.innerText))return null;
  const markets=[...row.querySelectorAll('.ta-MarketType-MRES')].filter(n=>n.getClientRects().length);
  if(markets.length!==1)return null;
  const selections=[...markets[0].querySelectorAll('.ta-SelectionButtonView')];
  if(selections.length!==3)return null;
  const prices=selections.map(n=>{
    const text=n.querySelector('.ta-price_text')?.innerText.trim()||'';
    const active=n.getClientRects().length>0&&!n.disabled&&n.getAttribute('aria-disabled')!=='true'&&!n.classList.contains('suspended');
    return active&&/^\d+(?:[.,]\d+)?$/.test(text)?Number(text.replace(',','.')):NaN;
  });
  if(prices.some(n=>!Number.isFinite(n)||n<=1))return null;
  return {'1':prices[0],'X':prices[1],'2':prices[2]};
}
function readSportiumCatalogue(leagues=[]) {
  const events=new Map();
  for(const row of document.querySelectorAll('.ta-EventListGroup .ta-EventListItem')) {
    if(!row.getClientRects().length)continue;
    const group=row.closest?.('.ta-EventListGroup'),header=group?.querySelector('.ta-GroupHeader');
    if(header&&!sportiumAllowedGroup(header.innerText,leagues))continue;
    const link=row.querySelector('a.ta-EventListItemDetails');
    const href=link?.getAttribute('href')||'';
    if(!/^\/apuestas\/sports\/soccer\/events\/\d+$/.test(href))continue;
    const teams=link.innerText.split('\n').map(s=>s.trim()).filter(Boolean);
    const date=row.innerText.split('\n').map(s=>s.trim()).find(s=>/^(Hoy|Mañana|\d{1,2}\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)),?\s+\d{1,2}:\d{2}$/i.test(s));
    if(teams.length!==2||!date)continue;
    const event={home:teams[0],away:teams[1],dateLabel:date.replace(',',''),source_url:'https://www.sportium.es'+href,event_id:href.split('/').pop()};
    const odds=sportiumListPrices(row,header);
    if(odds){
      event.league=header.innerText.trim().replace(/\s+1\s+X\s+2\b[\s\S]*$/i,'').trim();
      event.league_key=sportiumCompetitionKey(event.league);
      event.odds=odds;event.market='FULL_TIME_1X2';event.observed_at=new Date().toISOString();
    }
    events.set(href,event);
  }
  return [...events.values()];
}
function sportiumListSignature() {
  return [...document.querySelectorAll('.ta-EventListGroup .ta-GroupHeader')].map(n=>n.innerText.trim()).join('|')+'::'+
    [...document.querySelectorAll('.ta-EventListGroup .ta-EventListItem a.ta-EventListItemDetails')].map(n=>n.getAttribute('href')).join('|');
}
async function readCompleteSportiumCatalogue(leagues=[],warnings=[],targets=[],aliases={}) {
  const deadline=Date.now()+55000,collected=new Map(),expanded=new Set();
  const collect=()=>{for(const event of readSportiumCatalogue(leagues))collected.set(event.source_url,event);};
  const covered=()=>targets.length>0&&targets.every(target=>[...collected.values()].filter(event=>{
    try{return sportiumTeam(event.home,aliases)===target.canonical_home&&sportiumTeam(event.away,aliases)===target.canonical_away&&Math.abs(Date.parse(sportiumStart(event.dateLabel))-Date.parse(target.start))<=900000;}catch(_){return false;}
  }).length===1);
  const collectGroups=async()=>{
    for(const group of document.querySelectorAll('.ta-EventListGroup')){
      if(Date.now()>=deadline)break;
      const header=group.querySelector('.ta-GroupHeader'),label=header?.innerText.trim();
      if(!header||!sportiumAllowedGroup(label,leagues)||group.querySelector('.ta-EventListItem')||expanded.has(label))continue;
      expanded.add(label);header.click();
      try{await sportiumWait(()=>group.querySelector('.ta-EventListItem'),Math.max(1,Math.min(8000,deadline-Date.now())));}
      catch(error){if(/bloqueó/.test(error.message))throw error;warnings.push('No cargaron los partidos de '+label.slice(0,100));}
    }
    collect();
  };
  // Some layouts scroll the whole document (overflow: visible), while others
  // virtualize a nested pane. Retain every page and allow a late second batch.
  for(let pass=0;pass<(targets.length?2:1)&&Date.now()<deadline;pass++){
    await collectGroups();if(covered())break;
    const anchor=document.querySelector('.ta-EventListGroups');let scroller=null;
    for(let node=anchor;node;node=node.parentElement){
      if(node.clientHeight>0&&node.scrollHeight>node.clientHeight+2&&/auto|scroll/.test(getComputedStyle(node).overflowY)){scroller=node;break;}
    }
    const pageScroller=document.scrollingElement||document.documentElement;
    if(!scroller&&pageScroller?.clientHeight>0&&pageScroller.scrollHeight>pageScroller.clientHeight+2)scroller=pageScroller;
    if(scroller){
      const move=async position=>{
        const before=sportiumListSignature();scroller.scrollTop=position;
        try{await sportiumWait(()=>sportiumListSignature()!==before,Math.max(1,Math.min(1000,deadline-Date.now())));}catch(error){if(/bloqueó/.test(error.message))throw error;}
        await collectGroups();
      };
      if(scroller.scrollTop>0)await move(0);
      for(let page=0;page<20&&Date.now()<deadline&&!covered()&&scroller.scrollTop+scroller.clientHeight<scroller.scrollHeight-2;page++){
        const before=scroller.scrollTop;await move(before+Math.max(200,scroller.clientHeight-100));
        if(scroller.scrollTop===before)break;
      }
    }
    if(covered()||pass>0||!targets.length)break;
    const before=sportiumListSignature();
    try{await sportiumWait(()=>sportiumListSignature()!==before,Math.max(1,Math.min(3000,deadline-Date.now())));}catch(error){if(/bloqueó/.test(error.message))throw error;}
  }
  return [...collected.values()];
}
function sportiumDiagnostic(phase) {
  try{return typeof publicReaderDiagnostic==='function'?publicReaderDiagnostic('sportium',phase):undefined;}catch(_){return undefined;}
}
async function sportiumCatalogue(aliases,leagues=[],targets=[],snapshotOnly=false) {
  try {
    if(Intl.DateTimeFormat().resolvedOptions().timeZone!=='Europe/Madrid')throw new Error('Usa la zona horaria Europe/Madrid.');
    if(/access denied|acceso denegado|verify you are human|verifica que eres humano/i.test(document.body.innerText))return {ok:false,blocked:true,reason:'Sportium bloqueó el acceso; lectura detenida.'};
    await sportiumWait(()=>document.querySelector('.ta-EventListGroups .ta-GroupHeader'));
    const warnings=[];
    const catalogue=snapshotOnly?readSportiumCatalogue(leagues):await readCompleteSportiumCatalogue(leagues,warnings,targets,aliases);
    const events=catalogue.flatMap(event=>{
      try{return [{...event,start:sportiumStart(event.dateLabel),canonical_home:sportiumTeam(event.home,aliases),canonical_away:sportiumTeam(event.away,aliases)}];}catch{return [];}
    });
    return {ok:true,events,warnings,diagnostic:sportiumDiagnostic('catalogue')};
  }catch(error){return {ok:false,blocked:/bloqueó/.test(error.message),reason:error.message,diagnostic:sportiumDiagnostic('catalogue')};}
}
async function sportiumRead(target,aliases){
  try{
    if(!target.verifiedStart)throw new Error('Falta la fecha verificada en la búsqueda.');
    let lastError='No apareció Ganador (1X2).';
    const result=await sportiumWait(()=>{
      try{
        const event=readSportiumVisibleMarket();
        if(sportiumTeam(event.home,aliases)!==target.canonical_home||sportiumTeam(event.away,aliases)!==target.canonical_away)return null;
        return event;
      }catch(error){lastError=error.message;return null;}
    }).catch(()=>{throw new Error(lastError);});
    const id=/\/sports\/soccer\/events\/(\d+)$/.exec(location.pathname)?.[1];
    if(!id||location.hostname!=='www.sportium.es'||(target.expectedEventId&&id!==target.expectedEventId))throw new Error('No se reconoce el evento de fútbol de Sportium.');
    return {ok:true,payload:{source_url:location.href,observed_at:new Date().toISOString(),events:[{...result,event_id:id,start:target.verifiedStart,market:'FULL_TIME_1X2'}]}};
  }catch(error){return {ok:false,reason:error.message};}
}
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  if(message.type==='reader-ping'){respond({ok:true,url:location.href});return false;}
  if(message.type==='sportium-catalogue-snapshot'){sportiumCatalogue(message.aliases||{},Array.isArray(message.leagues)?message.leagues:[],[],true).then(respond);return true;}
  if(message.type==='sportium-catalogue'){sportiumCatalogue(message.aliases||{},Array.isArray(message.leagues)?message.leagues:[],Array.isArray(message.targets)?message.targets:[]).then(respond);return true;}
  if(message.type==='read-target'){sportiumRead(message.target,message.aliases).then(respond);return true;}
  return false;
});
