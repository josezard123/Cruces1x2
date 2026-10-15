const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let scroll=0,expanded=false,clicks=0;
const label='Europa League (Competiciones UEFA (Clubs))';
const group={querySelector:s=>s==='.ta-GroupHeader'?header:scroll===0||expanded?{}:null};
const header={innerText:label,click(){clicks++;expanded=true;}};
const unrelated={querySelector:s=>s==='.ta-GroupHeader'?{innerText:'Conference League (Competiciones UEFA (Clubs))',click(){throw Error('Wrong league expanded');}}:null};
const row=(id,home,away)=>({innerText:'Hoy, 21:00\n'+home+'\n'+away,getClientRects:()=>[{}],closest:()=>group,
 querySelector:()=>({innerText:home+'\n'+away,getAttribute:()=>'/apuestas/sports/soccer/events/'+id})});
const first=row('19457070','AFC Bournemouth','SK Sturm Graz'),last=row('19456925','O. Marsella','Olympiacos');
const scroller={clientHeight:500,scrollHeight:1300,parentElement:null};
Object.defineProperty(scroller,'scrollTop',{get:()=>scroll,set:value=>{scroll=Math.min(800,Math.max(0,value));}});
const rows=()=>scroll===0?[first]:scroll===800&&expanded?[last]:[];
const groups=()=>scroll===400?[unrelated]:[group];
const ctx={Date,Intl,setTimeout,clearTimeout,getComputedStyle:()=>({overflowY:'auto'}),MutationObserver:class{observe(){}disconnect(){}},
 chrome:{runtime:{onMessage:{addListener(){}}}},document:{body:{innerText:'Fútbol'},documentElement:{},querySelector:()=>scroller,
 querySelectorAll:s=>s==='.ta-EventListGroup'?groups():s.endsWith('.ta-GroupHeader')?groups().map(g=>g.querySelector('.ta-GroupHeader')):
 s.endsWith('a.ta-EventListItemDetails')?rows().map(r=>r.querySelector()):rows()}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/sportium.js','utf8'),ctx);
(async()=>{
 const warnings=[],events=await ctx.readCompleteSportiumCatalogue(['uel'],warnings);
 assert.equal(events.length,2);assert.equal(events[0].home,'AFC Bournemouth');assert.equal(events[1].home,'O. Marsella');
 assert.equal(clicks,1);assert.equal(warnings.length,0);assert.equal(scroll,800);
 console.log('Sportium: recorre cabeceras sin filas, abre grupos virtuales posteriores y conserva partidos previos, sin abrir otras competiciones.');
})().catch(error=>{console.error(error);process.exitCode=1;});
