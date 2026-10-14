const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const url='https://apuestas.retabet.es/deportes/futbol/europa/champions-league/roma-real-madrid/38230411';
let pings=0,reads=0,cancelled=false,wrongUrl=false,blocked=false,alwaysClosed=false;const progress=[];
const ctx={URL,Date,setTimeout:fn=>{queueMicrotask(fn);return 1;},readerTask:async(id,m)=>{
 assert.equal(id,7);
 if(m.type==='retabet-ping'){
  pings++;if(pings===1)throw Error('Receiving end does not exist.');
  return{ok:true,url:wrongUrl?'https://apuestas.retabet.es/deportes/futbol/1':url,ready:pings>=3};
 }
 reads++;
 if(alwaysClosed||reads===1)throw Error('A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received');
 return blocked?{ok:false,blocked:true,reason:'La web bloqueó la lectura pública.'}:{ok:true,payload:{events:[{event_id:'38230411'}]}};
}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/retabet_background.js','utf8'),ctx);
const task={type:'retabet-event',target:{url}};
(async()=>{
 const result=await ctx.retabetTask(7,task,url,async()=>cancelled,async text=>progress.push(text));
 assert.equal(result.ok,true);assert.equal(reads,2);assert.equal(pings,4);assert.equal(progress.length,1);
 assert.match(progress[0],/Reconectando/);
 pings=reads=0;blocked=true;
 const denied=await ctx.retabetTask(7,task,url,async()=>false,async()=>{});assert(denied.blocked);assert.equal(reads,2);
 pings=reads=0;wrongUrl=true;blocked=false;
 await assert.rejects(ctx.retabetTask(7,task,url,async()=>false,async()=>{}),/no se pudo restablecer/);assert.equal(reads,0);
 pings=reads=0;wrongUrl=false;alwaysClosed=true;
 await assert.rejects(ctx.retabetTask(7,task,url,async()=>false,async()=>{}),/no se pudo restablecer/);assert.equal(reads,3);
 pings=reads=0;cancelled=true;
 assert((await ctx.retabetTask(7,task,url,async()=>cancelled,async()=>{})).cancelled);assert.equal(pings,0);
 console.log('RETAbet: espera al lector específico y documento cargado; recupera canal cerrado, rechaza URL anterior, respeta bloqueo y cancela con límite de tres intentos.');
})().catch(error=>{console.error(error);process.exitCode=1;});
