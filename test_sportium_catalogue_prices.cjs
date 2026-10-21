const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
process.env.TZ='Europe/Madrid';
const fixed=Date.parse('2026-10-21T09:00:00Z');
class Clock extends Date{constructor(...args){super(...(args.length?args:[fixed]));}static now(){return fixed;}}
const header={innerText:'Champions League (Competiciones UEFA (Clubs))\n1\nX\n2\nMás de\nMenos de'};
const group={querySelector:()=>header};
const selection=(price,options={})=>({
 getClientRects:()=>options.hidden?[]:[{}],disabled:!!options.disabled,
 getAttribute:()=>options.ariaDisabled?'true':null,classList:{contains:name=>name==='suspended'&&!!options.suspended},
 querySelector:()=>({innerText:price})
});
let buttons=['2.15','3.75','3.00'].map(p=>selection(p)),marketCount=1;
const market={getClientRects:()=>[{}],querySelectorAll:()=>buttons};
const row={innerText:'Hoy, 18:45\nLille OSC\nGalatasaray\n2.15\n3.75\n3.00\n2.5\n1.65\n2.5\n2.15',
 getClientRects:()=>[{}],closest:()=>group,
 querySelector:()=>({innerText:'Lille OSC\nGalatasaray',getAttribute:()=>'/apuestas/sports/soccer/events/19607359'}),
 querySelectorAll:selector=>{assert.equal(selector,'.ta-MarketType-MRES');return Array(marketCount).fill(market);}};
const ctx={Date:Clock,Intl,chrome:{runtime:{onMessage:{addListener(){}}}},
 document:{querySelectorAll:()=>[row]}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/sportium.js','utf8'),ctx);
const result=()=>ctx.readSportiumCatalogue(['ucl'])[0];
let event=result();
assert.deepEqual({...event.odds},{'1':2.15,'X':3.75,'2':3});
assert.equal(event.league,'Champions League (Competiciones UEFA (Clubs))');
assert.equal(event.league_key,'ucl');assert.equal(event.market,'FULL_TIME_1X2');
assert.equal(event.observed_at,'2026-10-21T09:00:00.000Z');assert.equal(event.event_id,'19607359');
for(const options of [{hidden:true},{disabled:true},{ariaDisabled:true},{suspended:true}]){
 buttons[1]=selection('3.75',options);assert.equal(result().odds,undefined);
}
for(const price of ['suspendida','3.75 4.00','1','NaN','']){
 buttons[1]=selection(price);assert.equal(result().odds,undefined);
}
buttons[1]=selection('3,75');assert.equal(result().odds.X,3.75);
marketCount=2;assert.equal(result().odds,undefined);marketCount=0;assert.equal(result().odds,undefined);marketCount=1;
buttons.push(selection('7'));assert.equal(result().odds,undefined);buttons.pop();
header.innerText='Champions League (Competiciones UEFA (Clubs))\n1\n2\nX';assert.equal(result()?.odds,undefined);
header.innerText='Champions League (F)\n1\nX\n2';assert.equal(ctx.readSportiumCatalogue(['ucl']).length,0);
console.log('Sportium: cuotas 1-X-2 del mercado MRES, columnas verificadas, fecha de lectura y competición; excluye suspensiones, duplicados y otros mercados.');
