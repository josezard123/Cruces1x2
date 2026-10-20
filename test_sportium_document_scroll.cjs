const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
process.env.TZ='Europe/Madrid';
const fixed=Date.parse('2026-10-20T06:00:00Z');
class Clock extends Date{constructor(...args){super(...(args.length?args:[fixed]));}static now(){return fixed;}}
let scroll=0,delayed=false,loaded=false,waits=0;
const header={innerText:'Champions League (Competiciones UEFA (Clubs))',click(){throw Error('Already expanded');}};
const group={querySelector:s=>s==='.ta-GroupHeader'?header:mounted()[0]};
const all=Array.from({length:18},(_,i)=>({innerText:(i<9?'Hoy':'Mañana')+', 21:00\nHome '+i+'\nAway '+i,
 getClientRects:()=>[{}],closest:()=>group,querySelector:()=>({innerText:'Home '+i+'\nAway '+i,getAttribute:()=>'/apuestas/sports/soccer/events/'+(1000+i)})}));
const mounted=()=>delayed?(loaded?all:all.slice(0,8)):scroll===0?all.slice(0,8):scroll<800?all.slice(8,16):all.slice(16);
const page={clientHeight:500,scrollHeight:1500,parentElement:null};
Object.defineProperty(page,'scrollTop',{get:()=>scroll,set:value=>{scroll=Math.min(1000,Math.max(0,value));}});
const anchor={clientHeight:1500,scrollHeight:1500,parentElement:page};
const ctx={Date:Clock,Intl,setTimeout,clearTimeout,getComputedStyle:()=>({overflowY:'visible'}),chrome:{runtime:{onMessage:{addListener(){}}}},
 document:{documentElement:page,scrollingElement:page,body:{innerText:'Fútbol'},querySelector:()=>anchor,
 querySelectorAll:s=>s==='.ta-EventListGroup'?[group]:s.endsWith('.ta-GroupHeader')?[header]:s.endsWith('a.ta-EventListItemDetails')?mounted().map(r=>r.querySelector()):mounted()}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/sportium.js','utf8'),ctx);
ctx.sportiumWait=async check=>{waits++;if(delayed)loaded=true;const value=check();if(!value)throw Error('Sportium no cargó el elemento esperado.');return value;};
const targets=all.map((_,i)=>({canonical_home:'home '+i,canonical_away:'away '+i,start:i<9?'2026-10-20T19:00:00Z':'2026-10-21T19:00:00Z'}));
(async()=>{
 const events=await ctx.readCompleteSportiumCatalogue(['ucl'],[],targets,{});
 assert.equal(events.length,18);assert.equal(scroll,800);assert(waits>=2);
 assert(events.some(e=>e.home==='Home 0'));assert(events.some(e=>e.home==='Home 17'));
 delayed=true;loaded=false;scroll=0;page.scrollHeight=500;anchor.scrollHeight=anchor.clientHeight=500;waits=0;
 const late=await ctx.readCompleteSportiumCatalogue(['ucl'],[],targets,{});
 assert.equal(late.length,18);assert.equal(waits,1);
 console.log('Sportium: desplazamiento del documento con overflow visible y segunda tanda tardía; recupera los 18 partidos de hoy y mañana sin perder filas anteriores.');
})().catch(error=>{console.error(error);process.exitCode=1;});
