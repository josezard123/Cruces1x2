const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let current='https://www.bet365.es/#/AX/K%5ELASK/';
const ctx={URL,Date,setTimeout,clearTimeout,importScripts(){},chrome:{runtime:{onMessage:{addListener(){}}}},readerTask:async(id,message)=>{if(message.type==='scan-target')throw Error('response channel closed');return {ok:true,url:current};}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/background.js','utf8'),ctx);
(async()=>{
 assert.equal((await ctx.selectBetTarget(17,{start:new Date(Date.now()+3600000).toISOString()},{})).ok,false);
 current='https://www.bet365.es/#/AC/B1/C1/D8/E201058115/F3/';
 assert.equal((await ctx.selectBetTarget(17,{start:new Date(Date.now()+3600000).toISOString()},{})).ok,true);
 current='https://example.com/#/E201058115/';
 assert.equal((await ctx.selectBetTarget(17,{start:new Date(Date.now()+3600000).toISOString()},{})).ok,false);
 console.log('Bet365: canal cerrado solo aceptado cuando se confirma una ruta real de evento del origen autorizado; búsquedas colgadas excluidas.');
})().catch(error=>{console.error(error);process.exitCode=1;});
