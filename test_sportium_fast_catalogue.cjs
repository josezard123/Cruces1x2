const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const now=Date.now(),start=new Date(now+3600000).toISOString(),observed_at=new Date(now).toISOString();
const targets=[1,2].map(i=>({home:'Local '+i,away:'Visitante '+i,canonical_home:'local '+i,canonical_away:'visitante '+i,league_key:'laliga',start}));
const events=targets.map((t,i)=>({...t,event_id:String(100+i),source_url:'https://www.sportium.es/apuestas/sports/soccer/events/'+(100+i),league:'La Liga (España)',market:'FULL_TIME_1X2',observed_at,odds:{'1':2,'X':3,'2':4}}));
let snapshot={ok:true,events},full={ok:true,events},fullFailure=false,stopped=false,recovered=0;const calls=[];
const ctx={URL,Date,chrome:{runtime:{onMessage:{addListener(){}}}},importScripts(){},
 readerTask:async(id,message,limit)=>{calls.push([message.type,limit]);if(message.type==='sportium-catalogue-snapshot')return snapshot;if(fullFailure)throw Error('La página no respondió a tiempo; se continúa con las demás casas.');return full;},
 retryEmptyPublicPage:async(tab,result,retry)=>{if(result.retryPublicLoad){recovered++;snapshot={ok:true,events};return retry();}return result;}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/background.js','utf8'),ctx);
const tab={id:17},task={type:'sportium-catalogue',targets,aliases:{},leagues:['laliga']};
const cancelled=async()=>stopped,progress=async()=>{};
(async()=>{
 const fast=await ctx.sportiumLoadCatalogue(tab,task,cancelled,progress);
 assert.equal(fast.events.length,2);assert.deepEqual(calls,[['sportium-catalogue-snapshot',30000]]);
 calls.length=0;snapshot={ok:true,events:[events[0]]};fullFailure=true;
 const partial=await ctx.sportiumLoadCatalogue(tab,task,cancelled,progress);
 assert.equal(partial.ok,true);assert.equal(partial.events.length,1);assert.equal(partial.events[0].observed_at,observed_at);assert.match(partial.warnings[0],/parcial/);
 fullFailure=false;full={ok:true,events:[events[1]]};
 const merged=await ctx.sportiumLoadCatalogue(tab,task,cancelled,progress);
 assert.equal(merged.events.length,2);
 full={ok:true,events:[events[0],events[0],events[1]]};
 const duplicate=await ctx.sportiumLoadCatalogue(tab,task,cancelled,progress);
 assert.equal(duplicate.events.length,3);assert(!ctx.sportiumReferencesCovered(duplicate,targets));
 full={ok:false,blocked:true,reason:'Sportium bloqueó el acceso'};
 assert.equal((await ctx.sportiumLoadCatalogue(tab,task,cancelled,progress)).blocked,true);
 stopped=true;calls.length=0;
 await ctx.sportiumLoadCatalogue(tab,task,cancelled,progress);assert.equal(calls.length,1);stopped=false;
 const original=ctx.readerTask;ctx.readerTask=async(id,message,limit)=>{if(message.type==='sportium-catalogue-snapshot'&&!recovered)throw Error('La página no respondió a tiempo');return original(id,message,limit);};
 full={ok:true,events};
 assert.equal((await ctx.sportiumLoadCatalogue(tab,task,cancelled,progress)).events.length,2);assert.equal(recovered,1);
 assert(!ctx.sportiumReferencesCovered({ok:true,events:[{...events[0],odds:{'1':2,X:1,'2':4}},events[1]]},targets));
 assert(!ctx.sportiumReferencesCovered({ok:true,events:[events[0],events[0],events[1]]},targets));
 console.log('Sportium: catálogo inmediato, conservación parcial tras espera agotada, combinación de páginas, cancelación, bloqueo y recuperación de carga verificados.');
})().catch(error=>{console.error(error);process.exitCode=1;});
