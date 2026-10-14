const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const href='/apuestas/fútbol/uefa-champions-league/c-123';
const link={innerText:'UEFA Champions League',getAttribute:()=>href};
const ctx={URL,Date,Intl,setTimeout,clearTimeout,location:{hostname:'www.betfair.es'},document:{documentElement:{},body:{innerText:'Fútbol'},querySelectorAll:selector=>selector==='a'?[link]:[]},MutationObserver:class{observe(){}disconnect(){}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('bet365_extension/direct.js','utf8'),ctx);
(async()=>{
 const discovered=await ctx.discoverDirect({leagues:['ucl']});assert.equal(discovered.length,1);
 assert.equal(discovered[0].url,'https://www.betfair.es/apuestas/f%C3%BAtbol/uefa-champions-league/c-123');
 assert(ctx.directBfCompetitionURL('f%C3%BAtbol/uefa-champions-league/c-123'));
 assert(ctx.directBfCompetitionURL(discovered[0].url));
 for(const url of ['https://example.com/apuestas/fútbol/champions/c-123',href+'?key=secret',href+'#private','https://user:password@www.betfair.es'+href])assert.equal(ctx.directBfCompetitionURL(url),null);
 console.log('Betfair: enlaces públicos ya presentes sin pestaña Competiciones; rutas UTF-8, codificadas y absolutas del mismo origen validadas.');
})().catch(error=>{console.error(error);process.exitCode=1;});
