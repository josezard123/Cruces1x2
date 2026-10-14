const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let listener,reads=0,observer,deadline,disconnected=false,cleared=false;
const context={module:{exports:{}},chrome:{runtime:{onMessage:{addListener(fn){listener=fn;}}}},
 document:{documentElement:{},querySelector(){return {}; }},location:{href:'https://www.betfair.es/exchange/plus/'},
 MutationObserver:class{constructor(fn){observer=fn;}observe(){}disconnect(){disconnected=true;}},
 setTimeout:fn=>{deadline=fn;return 1;},clearTimeout:()=>{cleared=true;},URL,Date,Intl};
vm.createContext(context);
vm.runInContext(fs.readFileSync('bet365_extension/exchange.js','utf8'),context);
context.readExchangeCoupon=()=>({events:++reads<4?[]:[{home:'Valencia',away:'Levante'}]});
(async()=>{
 const pending=new Promise(resolve=>listener({type:'exchange-coupon'},null,resolve));
 assert.equal(reads,1);observer();observer();observer();
 const result=await pending;
 assert.equal(reads,4);assert.equal(result.ok,true);assert.equal(result.payload.events.length,1);
 assert(disconnected&&cleared);
 reads=0;context.readExchangeCoupon=()=>{reads++;return {events:[]};};
 const pendingEmpty=new Promise(resolve=>listener({type:'exchange-coupon'},null,resolve));
 assert.equal(reads,1);deadline();const empty=await pendingEmpty;
 assert.equal(reads,1);assert.equal(empty.ok,false);assert.equal(empty.reason,'no_lay');
 context.readExchangeCoupon=()=>({events:[],inspection:{headers:1,teams:1,dates:0}});
 const pendingDate=new Promise(resolve=>listener({type:'exchange-coupon'},null,resolve));deadline();
 assert.equal((await pendingDate).reason,'date_format');
 console.log('Exchange: espera cuotas tras aparecer la tabla y distingue carga vacía de lectura válida.');
})().catch(e=>{console.error(e.message);process.exitCode=1;});
