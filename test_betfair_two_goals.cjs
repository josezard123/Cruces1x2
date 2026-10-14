const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const competition={name:'UEFA Champions League',key:'ucl',country:'Europa'};
const settings={leagues:['ucl'],hours:36,aliases:{}};
let market='Resultados',enhancedAvailable=true,normalClicked=false;
const normal={id:'normal',getAttribute(){return null;},click(){normalClicked=true;market='Resultados';}};
const enhanced={id:'ppb:marketType:FULL_TIME_RESULT_-_2_UP',getAttribute(){return null;},click(){market='Resultado – 2 Goles de Ventaja';}};
const selector={get innerText(){return 'SELECCIONAR MERCADO:\n'+market;},click(){}};
const row={teams:['Local','Visitante'],date:'Wed Oct 14 2026 21:00:00 GMT+0200 (hora de verano de Europa central)',path:'f%C3%BAtbol/uefa-champions-league/local-visitante/e-123',buttons:['3.20','3.70','1.86'].map(price=>({price,active:true}))};
const ctx={URL,Intl,Date:class extends Date{constructor(...args){super(...(args.length?args:['2026-10-14T08:00:00Z']));}},setTimeout,clearTimeout,
 location:{hostname:'www.betfair.es'},MutationObserver:class{observe(){}disconnect(){}},
 document:{documentElement:{},body:{innerText:'Fútbol'},querySelectorAll(s){
  if(s==='button')return [selector];
  if(s.includes('radio'))return enhancedAvailable?[normal,enhanced]:[normal];
  return [];
 },querySelector(s){
  if(s.includes('input[type="radio"]'))return normal;
  if(s==='label[for="normal"]')return {innerText:'Resultados'};
  if(s.includes('FULL_TIME_RESULT_-_2_UP'))return {innerText:'Resultado – 2 Goles de Ventaja'};
  return null;
 }}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/direct.js','utf8'),ctx);
ctx.directBfSnapshot=()=>({market:selector.innerText,rows:[row]});
(async()=>{
 const result=await ctx.readDirectCompetition(competition,settings);
 assert.equal(result.events.length,1);assert.equal(result.events[0].payout,'two_goals');assert.equal(result.events[0].odds['1'],3.2);assert(!normalClicked);
 market='Resultados';enhancedAvailable=false;
 await assert.rejects(ctx.readDirectCompetition(competition,settings),/2 goles de ventaja/);assert(!normalClicked);
 // Known public Champions route opens directly, skipping the slow menu.
 const calls=[];
 Object.assign(ctx,{waitForReader:async()=>{},setInterval:()=>1,clearInterval:()=>{},chrome:{storage:{local:{get:async()=>({enabled:true}),set:async()=>{}}},tabs:{create:async x=>{calls.push(x.url);return{id:1};},update:async(id,x)=>calls.push(x.url),remove:async()=>{},sendMessage:async(id,m)=>{assert.equal(m.type,'direct-read');return{ok:true,payload:{events:result.events}};}}},fetch:async url=>({ok:true,json:async()=>url.endsWith('/direct-settings')?settings:url.endsWith('/update-status')?{cancelled:false}:{ok:true,captured:1}})});
 vm.runInContext(fs.readFileSync('bet365_extension/direct_background.js','utf8'),ctx);
 const scanned=await ctx.scanDirectSource('http://127.0.0.1:8802','betfair_sb',true);
 assert.equal(scanned.captured,1);assert(calls.every(url=>url.endsWith('/uefa-champions-league/c-228')));
 console.log('Sportsbook: Champions sin menú, selección explícita de 2 goles y rechazo del resultado normal comprobados.');
})().catch(error=>{console.error(error);process.exitCode=1;});
