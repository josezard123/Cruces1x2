const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx={URL,Date,Intl};vm.createContext(ctx);
for(const name of ['direct','retabet'])vm.runInContext(fs.readFileSync('bet365_extension/'+name+'.js','utf8'),ctx);
const path='/deportes/futbol/europa/champions-league/roma-real-madrid/38230411',url='https://apuestas.retabet.es'+path;
const compPath='/deportes/futbol/europa/champions-league/10';
const competition=ctx.retaCompetition('Champions League',compPath),settings={leagues:['ucl'],hours:36,aliases:{'as roma':'roma','r madrid':'real madrid'}};
const now=new Date('2026-10-14T09:00:00Z');
const rows=[{path,teams:['Roma','Real Madrid'],day:'Hoy',time:'21:00',live:'0'}];
const targets=ctx.parseRetaCatalogue(rows,competition,settings,now);assert.equal(targets.length,1);assert.equal(targets[0].start,'2026-10-14T19:00:00.000Z');
const target=targets[0],market=(title,prices)=>({title,selections:prices.map((price,i)=>({name:['1','X','2'][i],price,active:true}))});
const snapshot={url,home:'AS Roma',away:'R. Madrid',date:['Hoy','21:00'],competitions:[{name:'Champions League',path:compPath}],markets:[
 market('1-X-2',['3,56','3,99','1,96']),market('1-X-2 / Ventaja 2 goles',['3,49','3,96','1,94']),market('1-X-2 / Ventaja 1 gol',['1,91','3,73','1,41'])]};
for(const zone of ['UTC','Europe/Madrid','America/New_York']){
 process.env.TZ=zone;const event=ctx.parseRetaEvent(snapshot,target,settings,now);
 assert.equal(event.payout,'two_goals');assert.equal(event.odds['1'],3.49);assert.equal(event.odds.X,3.96);assert.equal(event.odds['2'],1.94);assert.equal(event.start,target.start);
 assert.equal(event.normal_odds['1'],3.56);assert.equal(event.normal_odds.X,3.99);assert.equal(event.normal_odds['2'],1.96);
 assert.equal(ctx.retaDate('16/10','21:00',now).toISOString(),'2026-10-16T19:00:00.000Z');
 assert.equal(ctx.retaDate('01/01','21:00',new Date('2026-12-31T10:00:00Z')).toISOString(),'2027-01-01T20:00:00.000Z');
}
assert.throws(()=>ctx.retaDate('31/02','21:00',now));assert.throws(()=>ctx.retaDate('16/10','25:00',now));
const bad=change=>{const s=structuredClone(snapshot);change(s);assert.throws(()=>ctx.parseRetaEvent(s,target,settings,now));};
bad(s=>s.markets.splice(1,1));bad(s=>s.markets.push(structuredClone(s.markets[1])));bad(s=>s.markets[1].selections[0].active=false);
bad(s=>s.markets[1].selections[0].price='1,00');bad(s=>s.markets[1].selections[1].name='1X');bad(s=>s.home='Roma U19');
bad(s=>s.date=['Mañana','21:00']);bad(s=>s.url=url+'?private=1');bad(s=>s.url=url.replace('38230411','999'));
assert.throws(()=>ctx.parseRetaEvent(snapshot,{...target,start:'invalid'},settings,now));
assert.equal(ctx.parseRetaCatalogue([{...rows[0],live:'1'}],competition,settings,now).length,0);
assert.equal(ctx.parseRetaCatalogue([{...rows[0],path:path.replace('champions-league','uefa-youth-league')}],competition,settings,now).length,0);
const europa=ctx.retaCompetition('UEFA Europa League','/deportes/futbol/europa/uefa-europa-league/11');
const europaRow={...rows[0],path:'/deportes/futbol/europa/uefa-europa-league-/stade-rennais-ofi-creta/38365925',teams:['Stade Rennais','OFI Creta']};
const europaTargets=ctx.parseRetaCatalogue([europaRow],europa,{...settings,leagues:['uel']},now);
assert.equal(europaTargets.length,1);assert.equal(europaTargets[0].event_id,'38365925');
for(const replacement of ['uefa-conference-league-','uefa-europa-league-u19-','uefa-youth-league']){
 assert.equal(ctx.parseRetaCatalogue([{...europaRow,path:europaRow.path.replace('uefa-europa-league-',replacement)}],europa,settings,now).length,0);
}
assert.equal(ctx.parseRetaCatalogue([{...europaRow,path:europaRow.path.replace('/europa/','/espana/')}],europa,settings,now).length,0);
const europaSnapshot={...snapshot,url:europaTargets[0].url,home:'Stade Rennais',away:'OFI Creta',competitions:[{name:'UEFA Europa League',path:europa.url}]};
assert.equal(ctx.parseRetaEvent(europaSnapshot,europaTargets[0],{...settings,leagues:['uel']},now).payout,'two_goals');
assert.equal(ctx.retaCompetition('LaLiga','/deportes/futbol/guatemala/laliga/1'),null);
assert.equal(ctx.retaCompetition('UEFA Youth League','/deportes/futbol/europa/uefa-youth-league/2617'),null);
for(const change of [s=>s.markets.splice(0,1),s=>s.markets.push(structuredClone(s.markets[0])),s=>s.markets[0].selections[1].active=false,s=>s.markets[0].selections[1].name='1X']){
 const copy=structuredClone(snapshot);change(copy);
 const event=ctx.parseRetaEvent(copy,target,settings,now);assert.equal(event.normal_odds,undefined);assert.equal(event.odds.X,3.96);
}
for(const badURL of ['http://apuestas.retabet.es'+path,'https://other.example'+path,'https://user:password@apuestas.retabet.es'+path,url+'#account'])assert.equal(ctx.retaURL(badURL,true),null);
console.log('RETAbet: mercado de 2 goles separado del normal y de 1 gol, fechas Madrid, signos, equipos, suspensión, duplicados y dominio verificados.');
