const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const target={home:'Bodø/Glimt',away:'Borussia Dortmund',canonical_home:'bodo glimt',canonical_away:'dortmund',start:'2026-10-14T19:00:00Z'};
const urls=[];let blocked=false,imports=0;
const ctx={URL,Date,setTimeout,clearTimeout,setInterval,clearInterval,chrome:{windows:{getAll:async()=>[{id:1,incognito:false,focused:true}]},runtime:{onMessage:{addListener(){}}},storage:{local:{get:async()=>({enabled:true}),set:async()=>{}}},tabs:{query:async()=>[{id:6,windowId:1,incognito:false}],create:async()=>({id:17}),remove:async()=>{},update:async(id,change)=>urls.push(change.url),sendMessage:async(id,message)=>message.type==='scan-target'?(blocked?{ok:false,blocked:true,reason:'Access denied'}:{ok:true}):{ok:true,payload:{events:[{home:target.home,away:target.away,start:target.start}]}}}},fetch:async(url)=>{if(url.endsWith('/bet365-scan-observation'))imports++;return {ok:true,json:async()=>url.includes('/bet365-targets')?{targets:[target],aliases:{}}:{cancelled:false}};}};
vm.createContext(ctx);ctx.importScripts=(...names)=>names.forEach(name=>vm.runInContext(fs.readFileSync('bet365_extension/'+name,'utf8'),ctx));vm.runInContext(fs.readFileSync('bet365_extension/background.js','utf8'),ctx);
ctx.waitForReader=async(id,expected)=>{if(expected&&!expected.includes('Borussia'))throw Error('home route not ready');};
(async()=>{
 const result=await ctx.scanAutomatically('http://127.0.0.1:8802',{},'bet365');
 assert.equal(result.captured,1);assert.equal(imports,1);assert(urls.some(url=>url.includes('K%5EBorussia%20Dortmund/')));
 urls.length=0;blocked=true;ctx.waitForReader=async()=>{};
 const denied=await ctx.scanAutomatically('http://127.0.0.1:8802',{},'bet365');
 assert.equal(denied.captured,0);assert.equal(urls.length,1);assert.equal(imports,1);
 console.log('Bet365: búsqueda por rival tras fallar las dos rutas del local; un bloqueo detiene los reintentos y no importa cuotas.');
})().catch(error=>{console.error(error);process.exitCode=1;});
