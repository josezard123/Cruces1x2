const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let now=Date.parse('2026-10-15T16:44:00Z'),searches=[],imports=0,advance=false;
class Clock extends Date{constructor(...args){super(...(args.length?args:[now]));}static now(){return now;}}
const early={home:'Union Saint-Gilloise',away:'Real Sociedad',canonical_home:'union saint gilloise',canonical_away:'real sociedad',start:'2026-10-15T16:45:00Z'};
const late={home:'Bournemouth',away:'Sturm Graz',canonical_home:'bournemouth',canonical_away:'sturm graz',start:'2026-10-15T19:00:00Z'};
const ctx={Date:Clock,URL,setTimeout,clearTimeout,setInterval,clearInterval,importScripts(){},chrome:{runtime:{onMessage:{addListener(){}}},
 storage:{local:{get:async()=>({enabled:true}),set:async()=>{}}},tabs:{remove:async()=>{}}},
 fetch:async url=>{if(url.endsWith('/bet365-scan-observation'))imports++;return {ok:true,json:async()=>url.includes('/bet365-targets')?{targets:[early,late],aliases:{}}:{cancelled:false}};},
 readerTask:async(id,message)=>({ok:true,payload:{events:[{enhanced_odds:{X:4}}]}}),retryEmptyPublicPage:async(tab,result)=>result};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/background.js','utf8'),ctx);
ctx.createBet365Tab=async()=>({id:17});ctx.waitForReader=async()=>{};
ctx.searchBetTeam=async(id,team,target)=>{searches.push(team);assert(target.readDeadline<=now+75000);
 if(advance&&target.home===early.home){now=Date.parse(early.start)+1;return {ok:false};}return {ok:true};};
(async()=>{
 now=Date.parse(early.start)+1;
 const skipped=await ctx.scanAutomatically('http://127.0.0.1:8802');
 assert.equal(skipped.captured,1);assert.equal(imports,1);assert.deepEqual(searches,[late.home]);assert.match(skipped.failures[0],/ya ha comenzado/);
 now=Date.parse('2026-10-15T16:44:00Z');searches=[];advance=true;
 const transition=await ctx.scanAutomatically('http://127.0.0.1:8802');
 assert.equal(transition.captured,1);assert.deepEqual(searches,[early.home,late.home]);assert.match(transition.failures[0],/ya ha comenzado/);
 assert.throws(()=>ctx.requireUpcomingTarget({...late,readDeadline:now-1}),/Límite de espera/);
 console.log('Bet365: omite partidos iniciados durante la cola o la búsqueda, limita cada partido y continúa con los siguientes.');
})().catch(error=>{console.error(error);process.exitCode=1;});
