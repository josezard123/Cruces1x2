const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
process.env.TZ='Europe/Madrid';
const ctx={Date,Intl,setInterval(){},document:{body:{innerText:'Full Time Result'}},location:{hash:'/AC/B1/C1/D8/E201058118/F3/G40/'},chrome:{storage:{local:{get:async()=>({})},onChanged:{addListener(){}}},runtime:{onMessage:{addListener(){}}}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/content.js','utf8'),ctx);
const target={canonical_home:'shakhtar donetsk',canonical_away:'aek atenas',start:new Date(Date.now()+3600000).toISOString()};
const payload={events:[{home:'Shakhtar Donetsk',away:'AEK Athens',start:target.start}]};
let reads=0;
ctx.readBet365Result=()=>{if(++reads===1)throw Error('Se necesita la fecha de un partido prepartido.');return payload;};
ctx.readWithEnhanced=async p=>p;ctx.bet365Diagnostic=()=>({counts:{market_nodes:2,home_nodes:6,away_nodes:0}});
ctx.waitFor=async check=>{check();const result=check();if(!result)throw Error('La web no cargó el elemento esperado.');return result;};
(async()=>{
 const good=await ctx.readTarget(target,{'aek athens':'aek atenas'});assert(good.ok);assert.equal(good.payload.events[0].away,'AEK Athens');
 reads=0;const mismatch=await ctx.readTarget(target,{});assert(!mismatch.ok);assert.match(mismatch.reason,/equipos/);assert(!mismatch.reason.includes('fecha'));
 console.log('Bet365: Shakhtar–AEK Athens se reconoce tras la carga; una falta de correspondencia no conserva un aviso anterior de fecha.');
})().catch(error=>{console.error(error);process.exitCode=1;});
