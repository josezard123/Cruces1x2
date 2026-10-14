const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('templates/index.html','utf8');
const readerVersion=JSON.parse(fs.readFileSync('bet365_extension/manifest.json','utf8')).version;
const start=html.indexOf('(async()=>{');
const source=html.slice(start,html.indexOf('{% endif %}',start)).replace('{{automatic_filter|tojson}}','{}');
async function run(version,result,direct='0'){
 const status={textContent:''},listeners={},calls=[];let poll;
 const context={updateForm:{dataset:{direct}},editingSettings:false,location:{href:'initial'},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options?.detail;}},document:{documentElement:{dataset:{crucesReader:'ready',crucesReaderVersion:version}},getElementById:()=>status,addEventListener:(type,fn)=>listeners[type]=fn,removeEventListener(){},dispatchEvent(event){calls.push(event.type);listeners['cruces-automatic-finished']({detail:result});}},setTimeout:()=>1,clearTimeout(){},setInterval(fn){poll=fn;return 2;},clearInterval(){calls.push('clear');},fetch:async()=>({json:async()=>context.progress})};
 context.renderScanProgress=p=>{status.textContent=`${p.label}: ${p.processed}/${p.total}`;};
 vm.createContext(context);await vm.runInContext(source,context);
 return {context,status,calls,poll};
}
(async()=>{
 const old=await run(undefined,{ok:true});assert.equal(old.calls.length,0);assert(old.status.textContent.includes(readerVersion));
 const busy=await run('1.8.0',{ok:false,reason:'busy'});assert(!busy.calls.includes('clear'));
 busy.context.progress={running:true,label:'Sportium ES',processed:4,total:10,captured:3,current:'Croacia'};await busy.poll();assert.match(busy.status.textContent,/Sportium ES: 4\/10/);
 busy.context.progress={running:false};await busy.poll();assert.equal(busy.context.location.href,'/');assert(busy.calls.includes('clear'));
 const done=await run('1.8.0',{ok:true});assert.equal(done.context.location.href,'/');
 const oldDirect=await run('1.9.4',{ok:true},'1');assert.equal(oldDirect.calls.length,0);assert.doesNotMatch(oldDirect.status.textContent,/PulseScore/);
 const newDirect=await run(readerVersion,{ok:true},'1');assert.equal(newDirect.context.location.href,'/');
 const upgraded=await run('1.9.0',{ok:true});assert.equal(upgraded.context.location.href,'/');
 console.log('Interfaz: bloquea lectores antiguos, conserva progreso de búsquedas existentes y vuelve al resultado al terminar.');
})().catch(error=>{console.error(error.message);process.exitCode=1;});
