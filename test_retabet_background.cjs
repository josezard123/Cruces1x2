const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let enabled=true,cancelled=false,ambiguous=false,blocked=false,currentUrl;const calls=[];
const competition={url:'https://apuestas.retabet.es/deportes/futbol/europa/champions-league/10',name:'Champions League',country:'Europa',key:'ucl'};
const event={url:'https://apuestas.retabet.es/deportes/futbol/europa/champions-league/roma-real-madrid/38230411',event_id:'38230411',home:'Roma',away:'Real Madrid',start:'2026-10-14T19:00:00Z',competition};
const target={home:event.home,away:event.away,start:event.start,canonical_home:'roma',canonical_away:'real madrid',league_key:'ucl'};
const ctx={URL,Date,setTimeout,clearTimeout,setInterval,clearInterval,waitForReader:async()=>{},chrome:{storage:{local:{get:async()=>({enabled}),set:async()=>{}}},tabs:{create:async x=>{currentUrl=x.url;calls.push(['create',x]);return{id:5};},update:async(id,x)=>{currentUrl=x.url;calls.push(['update',x]);},remove:async id=>calls.push(['remove',id])}},
 readerTask:async(id,m)=>{
  if(m.type==='retabet-ping')return{ok:true,url:currentUrl,ready:true};
  calls.push(['read',m.type]);
  if(blocked)return{ok:false,blocked:true,reason:'La web bloqueó la lectura pública.'};
  if(m.type==='retabet-discover')return{ok:true,competitions:[competition,{...competition,url:'https://evil.example/catalog'}]};
  if(m.type==='retabet-catalogue')return{ok:true,events:ambiguous?[event,{...event,event_id:'999',url:event.url.replace('38230411','999')}]:[event]};
  return{ok:true,payload:{events:[event]}};
 },fetch:async(url,options)=>{calls.push(['fetch',url,options]);return{ok:true,json:async()=>url.endsWith('/direct-settings')?{leagues:['ucl'],hours:36}:url.endsWith('/retabet-targets')?{targets:[target],aliases:{}}:url.endsWith('/update-status')?{cancelled}:{ok:true,captured:1}};}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/retabet_background.js','utf8'),ctx);
(async()=>{
 assert.equal((await ctx.scanRetabet('http://127.0.0.1:8802',false)).captured,1);
 assert.equal(calls.find(c=>c[0]==='create')[1].active,false);assert(calls.some(c=>c[0]==='remove'));
 assert(calls.filter(c=>c[0]==='update').every(c=>c[1].url.startsWith('https://apuestas.retabet.es/deportes/futbol/')));
 assert(calls.some(c=>c[0]==='fetch'&&c[1].endsWith('/direct-observation/retabet')));
 calls.length=0;ambiguous=true;
 const duplicate=await ctx.scanRetabet('http://127.0.0.1:8802',false);assert.equal(duplicate.captured,0);assert.match(duplicate.failures[0],/único partido/);assert(!calls.some(c=>c[0]==='read'&&c[1]==='retabet-event'));
 calls.length=0;ambiguous=false;blocked=true;
 const denied=await ctx.scanRetabet('http://127.0.0.1:8802',false);assert.equal(denied.captured,0);assert(calls.some(c=>c[0]==='remove'));assert.equal(calls.filter(c=>c[0]==='read').length,1);
 calls.length=0;blocked=false;cancelled=true;assert.equal((await ctx.scanRetabet('http://127.0.0.1:8802',false)).reason,'cancelled');assert(!calls.some(c=>c[0]==='create'));
 enabled=false;calls.length=0;assert.equal((await ctx.scanRetabet('http://127.0.0.1:8802',false)).reason,'disabled');assert.equal(calls.length,0);
 console.log('RETAbet automático: catálogo, referencias, pestaña propia, rechazo de rutas ajenas, duplicados, bloqueo, cancelación y cierre comprobados.');
})().catch(error=>{console.error(error);process.exitCode=1;});
