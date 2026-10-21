const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function node(value=''){
 const classes=new Set();return {value,textContent:'',disabled:false,checked:false,dataset:{},listeners:{},attrs:{},
  classList:{add:n=>classes.add(n),remove:(...names)=>names.forEach(n=>classes.delete(n)),toggle:(n,on)=>on?classes.add(n):classes.delete(n),contains:n=>classes.has(n)},
  addEventListener(type,fn){this.listeners[type]=fn;},setAttribute(key,value){this.attrs[key]=value;},matches:s=>s==='[data-calc-field]'};
}
function calculator(){
 const fields=Object.fromEntries(['q1','qX','q2','stake1','stakeX','stake2'].map((key,i)=>[key,node(['2.4','3.5','3.8','10','6.86','6.32'][i])]));
 const outputs=['return1','returnX','return2','profit1','profitX','profit2','total','min_return','worst_profit'].map(key=>Object.assign(node(),{dataset:{calcValue:key},textContent:'Inicial'}));
 const root=node(),manual=node(),status=node(),reset=node();
 root.querySelector=selector=>selector.startsWith('[data-calc-field=')?fields[selector.match(/"([^"]+)"/)[1]]:selector==='[data-calc-manual]'?manual:selector==='[data-calc-status]'?status:reset;
 root.querySelectorAll=()=>outputs;
 return {root,fields,outputs,manual,status,reset};
}
const a=calculator(),b=calculator(),timers=new Map(),calls=[],events=[];let next=0;
const ctx={WeakSet,AbortController,CustomEvent:class{constructor(type){this.type=type;}},
 document:{querySelectorAll:()=>[a.root,b.root],addEventListener(){},dispatchEvent:e=>events.push(e.type)},
 setTimeout:fn=>{const id=++next;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id),
 fetch:(url,options)=>new Promise(resolve=>calls.push({url,options,data:JSON.parse(options.body),resolve}))};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('static/cross_calculator.js','utf8'),ctx);
const edit=(c,key,value)=>{c.fields[key].value=value;c.root.listeners.input({target:c.fields[key]});};
const tick=()=>{const [id,fn]=timers.entries().next().value;timers.delete(id);return fn();};
const settle=(call,stake,ok=true)=>call.resolve({ok,json:async()=>ok?{ok:true,result:{stake1:stake,stakeX:12.35,stake2:5.67,total:38.02,min_return:37.85,worst_profit:-.17,return1:40,returnX:37.85,return2:39,profit1:1.98,profitX:-.17,profit2:.98}}:{ok:false,error:'Cuota no válida'}});
(async()=>{
 assert(a.fields.stakeX.disabled&&b.fields.stake2.disabled);assert.equal(calls.length,0);
 edit(a,'stake1','20');assert(a.outputs.every(n=>n.textContent==='—'));assert(b.outputs.every(n=>n.textContent==='Inicial'));
 let first=tick();assert.equal(calls[0].data.stake1,'20');assert.equal(calls[0].data.qX,'3.5');
 edit(a,'stake1','30');assert(calls[0].options.signal.aborted);let second=tick();
 settle(calls[1],30);await second;assert.equal(a.fields.stakeX.value,'12.35');assert.equal(a.fields.stake2.value,'5.67');
 assert.match(a.outputs.find(n=>n.dataset.calcValue==='profitX').textContent,/-0,17/);
 const latest=a.outputs.map(n=>n.textContent);settle(calls[0],20);await first;assert.deepEqual(a.outputs.map(n=>n.textContent),latest);
 assert.equal(b.fields.stake1.value,'10');assert.equal(a.root.attrs['aria-busy'],'false');
 a.manual.checked=true;a.manual.listeners.change();assert(!a.fields.stakeX.disabled);let manual=tick();
 assert.equal(calls[2].data.manual_stakes,true);assert.equal(calls[2].data.stakeX,'12.35');settle(calls[2],30);await manual;
 edit(b,'q1','');await tick();assert.equal(calls.length,3);assert.match(b.status.textContent,/Completa/);assert.equal(b.root.attrs['aria-busy'],'false');
 a.reset.listeners.click();assert.equal(a.fields.stake1.value,'10');assert.equal(a.fields.q1.value,'2.4');assert(!a.manual.checked&&a.fields.stakeX.disabled);
 let reset=tick();settle(calls[3],10);await reset;
 edit(a,'q1','1');let invalid=tick();settle(calls[4],10,false);await invalid;assert.match(a.status.textContent,/Cuota no válida/);assert(a.outputs.every(n=>n.textContent==='—'));
 assert(calls.every(call=>call.url==='/calculate-manual'));assert(events.every(type=>type==='cruces-calculator-edit'));
 console.log('Cruces: calculadoras independientes, edición automática/manual, respuestas tardías descartadas, restablecer y validación sin modificar cuotas guardadas.');
})().catch(error=>{console.error(error);process.exitCode=1;});
