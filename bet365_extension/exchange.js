/* Public DOM only: never credentials, cookies, account balances or betting actions. */
function exchangeMadridDate(year,month,day,hour,minute){
 const wall=Date.UTC(year,month,day,hour,minute);
 const fmt=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 let utc=wall;
 for(let i=0;i<3;i++){
  const parts=Object.fromEntries(fmt.formatToParts(new Date(utc)).filter(p=>p.type!=='literal').map(p=>[p.type,Number(p.value)]));
  utc+=wall-Date.UTC(parts.year,parts.month-1,parts.day,parts.hour,parts.minute);
 }
 return new Date(utc);
}
function readExchangeCoupon(root=document,now=new Date()){
 const filter=root.querySelector('.market-type-filter .selected-option');
 if(!filter||!/^Cuotas de partido$|^Match Odds$/i.test(filter.textContent.trim()))throw Error('market');
 const events=[];
 const inspection={tables:0,headers:0,rows:0,teams:0,dates:0,future:0,buttons:0,prices:0};
 const months={'ene':0,'enero':0,'jan':0,'feb':1,'mar':2,'abr':3,'apr':3,'may':4,'jun':5,'jul':6,'ago':7,'aug':7,'sep':8,'sept':8,'oct':9,'nov':10,'dic':11,'dec':11};
 for(const table of root.querySelectorAll('table.coupon-table')){
  inspection.tables++;
  const headers=[...table.querySelectorAll('thead th')].map(e=>e.textContent.trim());
  if(!headers.some((h,i)=>h==='1'&&headers[i+1]==='X'&&headers[i+2]==='2'))continue;
  inspection.headers++;
  for(const row of table.querySelectorAll('tbody tr')){
   inspection.rows++;
   const link=row.querySelector('a[data-market-id][data-event-type-id="1"]'),names=[...row.querySelectorAll('.runners .name')].map(e=>e.textContent.trim());
   const runners=[...row.querySelectorAll('.coupon-runner')];
   if(!link||names.length!==2||runners.length!==3||row.querySelector('.in-play'))continue;
   inspection.teams++;
   const label=row.querySelector('.start-date-wrapper .label')?.textContent.trim()||'';
   const normalized=label.toLowerCase().replace(/\s+/g,' ').trim();
   let match=normalized.match(/^([a-zñ]+)\.?\s+(\d{1,2})\s+(\d{1,2}):(\d{2})$/);
   if(!match){const dayFirst=normalized.match(/^(\d{1,2})\s+([a-zñ]+)\.?\s+(\d{1,2}):(\d{2})$/);if(dayFirst)match=[dayFirst[0],dayFirst[2],dayFirst[1],dayFirst[3],dayFirst[4]];}
   // Competition coupons abbreviate a near-date row to "vie. 21:00".
   // Recover the explicit day/month only from that table's own visible card header.
   if(!match){
    const short=normalized.match(/^(lun|mar|mié|mie|jue|vie|sáb|sab|dom|hoy|ma[nñ]ana|today|tomorrow)\.?\s+(\d{1,2}):(\d{2})$/);
    const header=table.closest?.('.coupon-card')?.querySelector('.card-header-title')?.textContent?.trim().split('\n')[0]||'';
    const full=/^(?:lun|mar|mié|mie|jue|vie|sáb|sab|dom)\.?\s+(\d{1,2})\s+([a-zñ]+)\.?\s*$/i.exec(header);
    if(short&&full)match=[normalized,full[2].toLowerCase(),full[1],short[2],short[3]];
   }
   if(!match||months[match[1]]===undefined)continue;
   if(+match[2]<1||+match[2]>31||+match[3]>23||+match[4]>59)continue;
   inspection.dates++;
   const year=Number(new Intl.DateTimeFormat('en',{timeZone:'Europe/Madrid',year:'numeric'}).format(now));
   let start=exchangeMadridDate(year,months[match[1]],Number(match[2]),Number(match[3]),Number(match[4]));
   if(start.getTime()<now.getTime()-86400000*180)start=exchangeMadridDate(year+1,months[match[1]],Number(match[2]),Number(match[3]),Number(match[4]));
   if(/^(hoy|ma[nñ]ana|today|tomorrow)\b/.test(normalized)){
    const calendar=d=>Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Madrid',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d).map(p=>[p.type,p.value]));
    const today=calendar(now),shown=calendar(start);
    const expected=new Date(Date.UTC(+today.year,+today.month-1,+today.day+(/^(ma[nñ]ana|tomorrow)\b/.test(normalized)?1:0)));
    if(+shown.year!==expected.getUTCFullYear()||+shown.month!==expected.getUTCMonth()+1||+shown.day!==expected.getUTCDate())continue;
   }
   if(start<=now||start-now>86400000*8)continue;
   inspection.future++;
   const lays={};
   for(const [i,runner] of runners.entries()){
    const button=runner.querySelector('ours-price-button[type="lay"] button');
    if(!button||button.disabled)continue;
    inspection.buttons++;
    const labels=[...button.querySelectorAll('label')].map(e=>e.textContent.trim());
    if(labels.length!==2||!/^\d+([.,]\d+)?$/.test(labels[0]))continue;
    const price=Number(labels[0].replace(',','.'));
    const eur=labels[1].replace(/[\s\u00a0\u202f]/g,'');
    if(!/^(?:€[\d.,]+|[\d.,]+€)$/.test(eur))continue;
    const rawSize=eur.replace('€',''),comma=rawSize.lastIndexOf(','),dot=rawSize.lastIndexOf('.');
    const decimal=comma>=0&&dot>=0?(comma>dot?',':'.'):comma>=0&&/,\d{1,2}$/.test(rawSize)?',':dot>=0&&/\.\d{1,2}$/.test(rawSize)?'.':null;
    const amount=decimal?rawSize.split(decimal).slice(0,-1).join('').replace(/[.,]/g,'')+'.'+rawSize.split(decimal).at(-1):rawSize.replace(/[.,]/g,'');
    const size=Number(amount)-(decimal?0:1);
    if(price>=1.01&&price<=1000&&size>0){lays[['1','X','2'][i]]={price,size};inspection.prices++;}
   }
   if(Object.keys(lays).length){const url=new URL(link.getAttribute('href'),root.baseURI||location.href).href;
    events.push({home:names[0],away:names[1],market_id:link.getAttribute('data-market-id'),start:start.toISOString(),url,lays});}
  }
 }
 const next=[...root.querySelectorAll('a')].find(a=>/^(Siguiente|Next)$/.test(a.textContent.trim()));
 const nextUrl=next?.getAttribute('href')?new URL(next.getAttribute('href'),root.baseURI||location.href).href:null;
 return {events,next:nextUrl,market:'MATCH_ODDS',currency:'EUR',observed_at:now.toISOString(),inspection};
}
function waitForExchangeCoupon(milliseconds=30000){
 // Background tabs throttle repeated timers. Listen to the actual Angular DOM
 // updates and use one deadline, instead of sixty delayed half-second polls.
 return new Promise(resolve=>{
  let observer,timer,finished=false,lastPayload=null,reason='loading';
  const finish=result=>{if(finished)return;finished=true;observer?.disconnect();clearTimeout(timer);resolve(result);};
  const inspect=()=>{
   try{
    const payload=readExchangeCoupon();lastPayload=payload;
    if(payload.events.length)finish({ok:true,payload});
   }catch(error){reason=error.message==='market'?'market':'layout';}
  };
  observer=new MutationObserver(inspect);
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,characterData:true});
  timer=setTimeout(()=>{
   if(lastPayload&&document.querySelector('table.coupon-table tbody tr')){
    const d=lastPayload.inspection;
    reason=!d?'no_lay':!d.headers||!d.teams?'layout':!d.dates?'date_format':!d.future?'time_window':!d.buttons?'lay_buttons':!d.prices?'price_format':'no_lay';
   }
   finish({ok:false,reason,inspection:lastPayload?.inspection});
  },milliseconds);
  inspect();
 });
}
if(typeof chrome!=='undefined'&&chrome.runtime){chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(message.type==='exchange-ping'){respond({ok:true,url:location.href});return false;}
 if(message.type!=='exchange-coupon')return false;
 waitForExchangeCoupon().then(respond);return true;
});}
if(typeof module!=='undefined')module.exports={readExchangeCoupon};
