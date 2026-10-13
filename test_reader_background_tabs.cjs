const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let ready=false,observer,cleared=0;
const ctx={Date,Intl,URL,document:{documentElement:{},body:{innerText:''}},
 setTimeout(){return 1;},clearTimeout(){cleared++;},
 MutationObserver:class{constructor(fn){observer=this;this.fn=fn;}observe(){}disconnect(){this.disconnected=true;}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/direct.js','utf8'),ctx);
(async()=>{
 const pending=ctx.directWait(()=>ready&&'loaded');ready=true;observer.fn();
 assert.equal(await pending,'loaded');assert(observer.disconnected);assert(cleared>0);
 ctx.document.body.innerText='Access denied';await assert.rejects(ctx.directWait(()=>true),/bloqueó/);ctx.document.body.innerText='';
 const grid={className:'ReactVirtualized__Grid',clientHeight:500,scrollHeight:900,parentElement:null};
 const anchor={parentElement:grid};ctx.getComputedStyle=()=>({overflowY:'auto'});
 assert.equal(ctx.directScrollHost(anchor),grid);
 // Initial scroll is at tomorrow; reset must recover today's Barcelona game.
 const stamp=new Date('2026-10-13T10:00:00Z');
 ctx.Date=class extends Date{constructor(...args){super(...(args.length?args:[stamp]));}};
 ctx.location={hostname:'www.winamax.es'};let scroll=400;
 Object.defineProperty(grid,'scrollTop',{get:()=>scroll,set:value=>{scroll=Math.min(400,Math.max(0,value));}});
 const card=(id,home,away,day)=>({id,lines:['Champions League',home,day,'21:00',away],odds:[{text:home+'\n2.00',price:'2.00',active:true},{text:'Empate\n3.00',price:'3.00',active:true},{text:away+'\n4.00',price:'4.00',active:true}]});
 const today=card('101','FC Barcelona','Galatasaray','Hoy'),tomorrow=card('102','Roma','Real Madrid','Mañana');
 const visibleCard=()=>({getAttribute:()=>scroll===0?'match-card-101':'match-card-102'});
 ctx.document.querySelector=()=>anchor;
 ctx.document.querySelectorAll=selector=>selector==='.filter-button'?[{innerText:'Resultado',click(){}}]:[visibleCard()];
 ctx.directWinaSnapshot=()=>({cards:[scroll===0?today:tomorrow]});
 const payload=await ctx.readDirectCompetition({name:'Champions League',country:'Europa',key:'ucl'},{hours:36,aliases:{}});
 assert.equal(payload.events.length,2);assert(payload.events.some(e=>e.home==='FC Barcelona'&&e.start==='2026-10-13T19:00:00.000Z'));
 console.log('Pestañas inactivas: DOM sin temporizadores recurrentes, bloqueo respetado, lista correcta y Barcelona de hoy recuperado al reiniciar desplazamiento.');
})().catch(error=>{console.error(error);process.exitCode=1;});
