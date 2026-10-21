const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const now=Date.now(),observed=new Date(now).toISOString(),start=new Date(now+3600000).toISOString();
const names=['Como','Lille','Bayern Múnich','Aston Villa','Inter Milán','Sporting Portugal','Club Brujas','Real Betis','Real Madrid'];
const targets=names.map((home,i)=>({home,away:'Visitante '+i,canonical_home:'home '+i,canonical_away:'away '+i,league_key:'ucl',start}));
let events=targets.map((target,i)=>({...target,league:'Champions League (Competiciones UEFA (Clubs))',event_id:String(1000+i),source_url:'https://www.sportium.es/apuestas/sports/soccer/events/'+(1000+i),market:'FULL_TIME_1X2',observed_at:observed,odds:{'1':2.15,'X':3.75,'2':3}}));
let stopped=false,fallback=false,readCalls=0;const imports=[],navigations=[];
const ctx={URL,Date,setTimeout,clearTimeout,setInterval,clearInterval,
 chrome:{runtime:{onMessage:{addListener(){}}},storage:{local:{get:async()=>({enabled:true}),set:async()=>{}}},
  tabs:{create:async()=>({id:17}),remove:async()=>{},update:async(id,change)=>{navigations.push(change.url);},query:async()=>[{id:17}],
   sendMessage:async(id,message)=>{
    if(message.type==='sportium-catalogue')return {ok:true,events};
    if(message.type==='read-target'){readCalls++;if(!fallback)throw Error('Las páginas individuales están atascadas en el cargador');return {ok:false,reason:'No apareció el evento de Sportium.'};}
    return {ok:true};
   }}},
 fetch:async(url,options)=>{
  if(url.endsWith('/sportium-scan-observation')){imports.push(JSON.parse(options.body));}
  return {ok:true,json:async()=>url.includes('/bet365-targets')?{targets,aliases:{}}:{cancelled:stopped}};
 }};
vm.createContext(ctx);ctx.importScripts=(...names)=>names.forEach(name=>vm.runInContext(fs.readFileSync('bet365_extension/'+name,'utf8'),ctx));
vm.runInContext(fs.readFileSync('bet365_extension/background.js','utf8'),ctx);ctx.waitForReader=async()=>{};
const copy=()=>JSON.parse(JSON.stringify(events[0]));
(async()=>{
 const result=await ctx.scanAutomatically('http://127.0.0.1:8802',{},'sportium');
 assert.equal(result.captured,9);assert.equal(imports.length,9);assert.equal(readCalls,0);assert.equal(navigations.length,0);
 assert(imports.every(payload=>payload.observed_at===observed&&payload.events.length===1));
 for(const mutate of [e=>e.source_url='https://evil.example/events/1000',e=>e.event_id='999',e=>e.market='HANDICAP',e=>e.canonical_away='wrong',e=>e.league_key='uel',e=>e.start=new Date(now+7200000).toISOString(),e=>e.start=new Date(now-1).toISOString(),e=>e.observed_at=new Date(now-121000).toISOString(),e=>e.observed_at=new Date(now+60000).toISOString(),e=>e.odds.X=1,e=>e.odds.X='3.75',e=>e.odds.extra=4]){
  const event=copy();mutate(event);assert.equal(ctx.sportiumCatalogueObservation(event,targets[0]),null);
 }
 const missingExpected={...targets[0],start:'invalid'};assert.equal(ctx.sportiumCatalogueObservation(events[0],missingExpected),null);
 stopped=true;assert.equal((await ctx.scanAutomatically('http://127.0.0.1:8802',{},'sportium')).reason,'cancelled');assert.equal(imports.length,9);
 stopped=false;fallback=true;events=events.map(e=>{const value={...e};delete value.odds;return value;});
 await ctx.scanAutomatically('http://127.0.0.1:8802',{},'sportium');assert.equal(readCalls,9);assert.equal(navigations.length,9);assert.equal(imports.length,9);
 console.log('Sportium: nueve partidos importados desde el catálogo aunque los eventos no carguen; conserva fecha real, valida referencia y mantiene la lectura individual como alternativa.');
})().catch(error=>{console.error(error);process.exitCode=1;});
