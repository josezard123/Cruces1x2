const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
let listener;
const calls=[];
let tabUrl='';let firstRead=true;let selectedTarget=null;let cancelAfterRead=false;
const target={home:'Croacia',away:'España',canonical_home:'croacia',canonical_away:'espana',start:'2026-10-06T18:45:00Z'};
const payload={source_url:'https://www.bet365.es/#/AC/B1/C1/D8/E201151094/',events:[{home:'Croacia',away:'España',odds:{'1':8.5,'X':6.25,'2':1.27},enhanced_odds:{'1':8.75,'X':6.5,'2':1.3}}]};
let sportRecords=[{...target,event_id:'19514722',source_url:'https://www.sportium.es/apuestas/sports/soccer/events/19514722'}];
const chrome={
  windows:{getAll:async()=>[{id:1,incognito:false,focused:true}]},
  runtime:{onMessage:{addListener(fn){listener=fn;}}},
  storage:{local:{async get(){return {enabled:true};},async set(value){calls.push(['status',value]);}}},
  tabs:{query:async()=>[{id:6,windowId:1,incognito:false}],async create(options){calls.push(['create',options]);tabUrl=options.url;return {id:17};},async update(id,options){calls.push(['update',options]);tabUrl=options.url;},async remove(id){calls.push(['remove',id]);},async sendMessage(id,message){calls.push(['message',message]);if(message.type==='reader-ping')return {ok:true,url:tabUrl};if(message.type==='sportium-catalogue')return {ok:true,events:sportRecords};if(message.type==='scan-target'){selectedTarget=message.target;if(message.target.home==='India')return {ok:false,reason:'No encontrado'};return {ok:true,navigated:true,verifiedStart:message.target.start};}if(firstRead){firstRead=false;throw new Error('Message channel closed after navigation');}return {ok:true,payload:{...payload,source_url:tabUrl.startsWith('https://www.sportium.es/')?'https://www.sportium.es/apuestas/sports/soccer/events/19514722':payload.source_url,events:[{...payload.events[0],home:selectedTarget.home,away:selectedTarget.away}]}};}}
};
const context={chrome,URL,Date,setTimeout,clearTimeout,setInterval,clearInterval,fetch:async(url,options)=>{
  calls.push(['fetch',url,options]);
  if(url.endsWith('/update-status'))return {json:async()=>({cancelled:cancelAfterRead&&calls.some(c=>c[0]==='message'&&c[1].type==='read-target')})};
  if(url.includes('/bet365-targets'))return {json:async()=>({targets:url.includes('?home=')?[target]:[{...target,home:'India',away:'Uruguay',canonical_home:'india',canonical_away:'uruguay'},target,{...target,home:'Moldavia',away:'Eslovaquia',canonical_home:'moldavia',canonical_away:'eslovaquia'}],aliases:{}})};
  return {ok:true,json:async()=>({ok:true})};
}};
vm.createContext(context);
context.importScripts=(...paths)=>paths.forEach(path=>vm.runInContext(fs.readFileSync('bet365_extension/'+path,'utf8'),context));
vm.runInContext(fs.readFileSync('bet365_extension/background.js','utf8'),context);
(async()=>{
  const blocked=listener({type:'automatic-bet365-scan'},{url:'https://example.com'},()=>{});
  assert.equal(blocked,false);
  assert.equal(calls.length,0);
  const result=await new Promise(resolve=>listener({type:'automatic-bet365-scan',filter:{home:'Croacia',away:'España'}},{url:'http://127.0.0.1:8802/update'},resolve));
  assert.equal(result.captured,1);
  assert(calls.some(c=>c[0]==='fetch'&&c[1].includes('?home=Croacia&away=Espa%C3%B1a')));
  assert.equal(calls.filter(c=>c[0]==='message'&&c[1].type==='read-target').length,2);
  assert(calls.some(c=>c[0]==='update'&&c[1].url.includes('/AX/K%5ECroacia/')));
  assert.equal(calls.find(c=>c[0]==='create')[1].active,false);
  assert.equal(calls.find(c=>c[0]==='remove')[1],17);
  const post=calls.find(c=>c[0]==='fetch'&&c[1].endsWith('/bet365-scan-observation'));
  assert.deepEqual(JSON.parse(post[2].body),payload);
  assert(calls.filter(c=>c[0]==='fetch').every(c=>c[1].startsWith('http://127.0.0.1:8802/')));
  const general=await new Promise(resolve=>listener({type:'automatic-bet365-scan'},{url:'http://127.0.0.1:8802/update'},resolve));
  assert.equal(general.captured,2);
  assert.equal(general.failures.length,1);
  assert(calls.some(c=>c[0]==='update'&&c[1].url.includes('/AX/K%5EMoldavia/')));
  const both=await new Promise(resolve=>listener({type:'automatic-bet365-scan',filter:{home:'Croacia',away:'España',sources:['bet365','sportium']}},{url:'http://127.0.0.1:8802/update'},resolve));
  assert.equal(both.captured,2);
  assert(calls.some(c=>c[0]==='create'&&c[1].url.endsWith('/matches/48h')));
  assert(calls.some(c=>c[0]==='update'&&c[1].url.endsWith('/events/19514722')));
  assert.equal(calls.filter(c=>c[0]==='message'&&c[1].type==='sportium-catalogue').length,1);
  const sportPost=calls.find(c=>c[0]==='fetch'&&c[1].endsWith('/sportium-scan-observation'));
  assert.equal(JSON.parse(sportPost[2].body).source_url,'https://www.sportium.es/apuestas/sports/soccer/events/19514722');
  assert(calls.some(c=>c[0]==='message'&&c[1].target?.verifiedStart===target.start));
  assert(calls.some(c=>c[0]==='fetch'&&c[1].endsWith('/bet365-scan-complete')&&JSON.parse(c[2].body).continuing===true));
  const catalogueCalls=calls.filter(c=>c[0]==='message'&&c[1].type==='sportium-catalogue').length;
  const searchCalls=calls.filter(c=>c[0]==='message'&&c[1].type==='scan-target').length;
  const sportGeneral=await new Promise(resolve=>listener({type:'automatic-bet365-scan',filter:{sources:['sportium']}},{url:'http://127.0.0.1:8802/'},resolve));
  assert.equal(sportGeneral.captured,1);assert.equal(sportGeneral.failures.length,2);
  assert.equal(calls.filter(c=>c[0]==='message'&&c[1].type==='sportium-catalogue').length,catalogueCalls+1);
  assert.equal(calls.filter(c=>c[0]==='message'&&c[1].type==='scan-target').length,searchCalls);
  sportRecords=[...sportRecords,...sportRecords];
  const ambiguous=await new Promise(resolve=>listener({type:'automatic-bet365-scan',filter:{sources:['sportium'],home:'Croacia',away:'España'}},{url:'http://127.0.0.1:8802/'},resolve));
  assert.equal(ambiguous.captured,0);assert.equal(ambiguous.failures.length,1);
  sportRecords=[{...sportRecords[0],source_url:'https://evil.example/events/1'}];
  const unsafe=await new Promise(resolve=>listener({type:'automatic-bet365-scan',filter:{sources:['sportium'],home:'Croacia',away:'España'}},{url:'http://127.0.0.1:8802/'},resolve));
  assert.equal(unsafe.captured,0);
  calls.length=0;cancelAfterRead=true;
  const stopped=await new Promise(resolve=>listener({type:'automatic-bet365-scan',filter:{home:'Croacia',away:'España',sources:['bet365','sportium']}},{url:'http://127.0.0.1:8802/'},resolve));
  assert.equal(stopped.reason,'cancelled');
  assert(!calls.some(c=>c[0]==='fetch'&&c[1].endsWith('/bet365-scan-observation')));
  assert.equal(calls.filter(c=>c[0]==='create').length,1);
  assert(calls.some(c=>c[0]==='remove'));
  calls.length=0;cancelAfterRead=false;sportRecords=[{...target,event_id:'19514722',source_url:'https://www.sportium.es/apuestas/sports/soccer/events/19514722'}];chrome.tabs.query=async()=>[];
  const withoutBet=await new Promise(resolve=>listener({type:'automatic-bet365-scan',filter:{home:'Croacia',away:'España',sources:['bet365','sportium']}},{url:'http://127.0.0.1:8802/'},resolve));
  assert(withoutBet.ok);assert.equal(withoutBet.captured,1);assert.match(withoutBet.failures[0],/Abre Bet365.*otras casas/);
  assert.equal(calls.filter(c=>c[0]==='create').length,1);assert(calls.find(c=>c[0]==='create')[1].url.includes('sportium.es'));
  console.log('Extensión: origen local verificado, búsqueda en pestaña propia, entrega pública y cierre comprobados con navegador simulado.');
})().catch(error=>{console.error(error.message);process.exitCode=1;});
