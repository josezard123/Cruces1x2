const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let listener,tabUrl,enabled=true,targets=true;const calls=[];
const target={league_key:'laliga',home:'Valencia',away:'Levante',canonical_home:'valencia',canonical_away:'levante',start:'2026-10-10T19:00:00Z'};
const payload={market:'MATCH_ODDS',currency:'EUR',observed_at:'2026-10-07T05:00:00Z',events:[{...target,market_id:'1.123456789',url:'https://www.betfair.es/exchange/plus/es/fútbol/valencia-levante-apuestas-123456',lays:{X:{price:3.5,size:100}}}],next:'https://www.betfair.es/exchange/plus/es/f%C3%BAtbol-apuestas-1/2'};
const context={URL,Date,Set,setTimeout,clearTimeout,setInterval,clearInterval,activeScan:null,chrome:{runtime:{onMessage:{addListener(fn){listener=fn;}}},storage:{local:{get:async()=>({enabled})}},tabs:{create:async options=>{calls.push(['create',options]);tabUrl=options.url;return {id:10};},update:async(id,options)=>{calls.push(['update',options]);tabUrl=options.url;},remove:async id=>calls.push(['remove',id]),sendMessage:async(id,message)=>message.type==='exchange-ping'?{ok:true,url:tabUrl}:{ok:true,payload}}},fetch:async(url,options)=>{calls.push(['fetch',url,options]);return {ok:true,json:async()=>url.includes('/targets')?{targets:targets?[target]:[],aliases:{}}:{ok:true,captured:1}};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('bet365_extension/exchange_background.js','utf8'),context);
(async()=>{
 assert.equal(listener({type:'automatic-exchange-scan',source:'winamax_es'},{url:'https://evil.example'},()=>{}),false);
 assert.equal(calls.length,0);
 const result=await new Promise(resolve=>listener({type:'automatic-exchange-scan',source:'winamax_es'},{url:'http://127.0.0.1:8802/freebets'},resolve));
 assert.equal(result.captured,1);assert.equal(calls.filter(c=>c[0]==='update').length,0);assert.equal(calls.find(c=>c[0]==='create')[1].active,false);assert(calls.find(c=>c[0]==='create')[1].url.includes('la-liga-espa%C3%B1ola-apuestas-117'));assert.equal(calls.find(c=>c[0]==='remove')[1],10);
 assert(calls.filter(c=>c[0]==='fetch').every(c=>c[1].startsWith('http://127.0.0.1:8802/freebets/')));
 assert.equal(JSON.parse(calls.find(c=>c[0]==='fetch'&&c[1].endsWith('/exchange-observation'))[2].body).events[0].lays.X.price,3.5);
 vm.runInContext('activeScan=Promise.resolve()',context);const busy=await new Promise(resolve=>listener({type:'automatic-exchange-scan',source:'winamax_es'},{url:'http://127.0.0.1:8802/freebets'},resolve));assert.equal(busy.reason,'busy');vm.runInContext('activeScan=null',context);
 enabled=false;assert.equal((await context.scanExchange('http://127.0.0.1:8802','winamax_es')).reason,'disabled');enabled=true;
 // The first ping usually precedes injection of document_idle. Keep the tab
 // and retry; also reject replies from the previous document after navigation.
 let pings=0;context.setTimeout=fn=>{queueMicrotask(fn);return 1;};
 context.chrome.tabs.sendMessage=async(id,message)=>{
  if(message.type!=='exchange-ping')return {ok:true,payload};
  if(++pings<=2)throw Error('Receiving end does not exist.');
  return {ok:true,url:pings===3?'https://www.betfair.es/exchange/plus/old':tabUrl};
 };
 calls.length=0;const delayed=await context.scanExchange('http://127.0.0.1:8802','sportium');
 assert.equal(delayed.captured,1);assert.equal(pings,4);
 assert(!calls.some(c=>c[0]==='fetch'&&c[1].endsWith('/status')&&JSON.parse(c[2].body).state==='connection'));
 context.chrome.tabs.sendMessage=async()=>{throw Error('No receiver');};pings=0;
 const disconnected=await context.scanExchange('http://127.0.0.1:8802','sportium');
 assert.equal(disconnected.reason,'connection');assert(calls.some(c=>c[0]==='remove'));
 target.league_key='ucl';calls.length=0;
 context.chrome.tabs.sendMessage=async(id,message)=>message.type==='exchange-ping'?{ok:true,url:tabUrl}:{ok:true,payload};
 assert.equal((await context.scanExchange('http://127.0.0.1:8802','sportium')).captured,1);
 assert(calls.find(c=>c[0]==='create')[1].url.endsWith('uefa-champions-league-apuestas-228'));
 targets=false;assert.equal((await context.scanExchange('http://127.0.0.1:8802','winamax_es')).reason,'empty');
 console.log('Exchange automático: origen, filtros, pestaña propia, parada al cubrir objetivos, bloqueo concurrente, lectura pública y cierre verificados con navegador simulado.');
})().catch(e=>{console.error(e.message);process.exitCode=1;});
