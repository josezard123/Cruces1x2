const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let windows=[{id:3,incognito:true,focused:true},{id:8,incognito:false,focused:false},{id:9,incognito:false,focused:true}],opened=[{id:6,windowId:8,incognito:false},{id:7,windowId:9,incognito:false}],listener;const created=[];
const ctx={URL,Date,importScripts(){},chrome:{windows:{getAll:async()=>windows},tabs:{query:async()=>opened,create:async options=>{created.push(options);return{id:1};}},runtime:{onMessage:{addListener:fn=>listener=fn}}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/background.js','utf8'),ctx);
(async()=>{
 await ctx.createBet365Tab('https://www.bet365.es/#/AX/');
 assert.equal(created[0].windowId,9);assert.equal(created[0].active,false);
 windows=[{id:3,incognito:true,focused:true},{id:8,incognito:false,focused:false}];
 await ctx.createBet365Tab('https://www.bet365.es/#/AX/');assert.equal(created[1].windowId,8);
 opened=[];windows=[{id:3,incognito:true,focused:true},{id:8,incognito:false,focused:false},{id:9,incognito:false,focused:true}];
 await ctx.createBet365Tab('https://www.bet365.es/#/AX/');assert.equal(created[2].windowId,9);assert.equal(created[2].active,false);
 opened=[{id:3,windowId:3,incognito:true}];await ctx.createBet365Tab('https://www.bet365.es/#/AX/');assert.equal(created[3].windowId,9);
 windows=[{id:3,incognito:true}];await assert.rejects(ctx.createBet365Tab('https://www.bet365.es/#/AX/'),/No se pudieron obtener.*otras casas/);assert.equal(created.length,4);
 let response;listener({type:'bet365-observation',payload:{}},{url:'https://www.bet365.es/#/AC/',tab:{incognito:true}},result=>response=result);
 assert.equal(response.reason,'incognito');
 console.log('Bet365: abre su propia pestaña si la casa está cerrada, prefiere la sesión existente y excluye incógnito sin pedir que se abra la casa.');
})().catch(error=>{console.error(error);process.exitCode=1;});
