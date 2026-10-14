const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const node=(text,classes='sport-date')=>({innerText:text,tagName:'SPAN',className:classes,children:[],getClientRects:()=>[{}],closest:()=>null,getAttribute:()=>null,parentElement:null});
const forbidden={children:[],getClientRects:()=>[{}],closest:()=>({}),get innerText(){throw Error('private form read');}};
const leafs=[node('14 oct'),node('18:45'),node('LASK'),node('Liverpool'),node('Resultado final'),node('person@example.com'),node('Saldo 1200'),forbidden];
const root={querySelectorAll:()=>leafs,get innerText(){throw Error('whole page read');}};
for(const n of leafs)n.parentElement=root;
const document={querySelector:()=>root,querySelectorAll:()=>[],get body(){throw Error('whole body read');},get cookie(){throw Error('cookie read');}};
const context={document,location:{hash:'#/AC/B1/E123/'}};
vm.createContext(context);vm.runInContext(fs.readFileSync('bet365_extension/diagnostic.js','utf8'),context);
const value=context.publicReaderDiagnostic('bet365','event',{home:'LASK',away:'Liverpool'});
assert.equal(value.event_id,'123');assert.equal(value.counts.date_nodes,2);assert.equal(value.counts.home_nodes,1);assert.equal(value.counts.market_nodes,1);
const serialized=JSON.stringify(value);assert(!serialized.includes('person@example.com'));assert(!serialized.includes('Saldo'));assert(!serialized.includes('private'));
for(const text of ['api_key SECRET','password SECRET','10€','<input>'])assert.equal(context.diagnosticText(text),null);
// Capture price buttons alongside an event link without requiring the buttons
// to be descendants of the link: this is exactly what the live diagnosis needs.
const buttons=[node('2.90'),node('3.40'),node('2.84')];
const event=node('');event.getAttribute=()=>'/apuestas/f%C3%BAtbol/champions/lask-liverpool/e-123';
event.querySelectorAll=()=>[node('LASK'),node('Liverpool')];event.querySelector=()=>({getAttribute:()=> '2026-10-14T16:45:00Z'});
event.parentElement={querySelectorAll:()=>buttons};
document.querySelectorAll=selector=>selector==='a'?[event]:[];
const bf=context.publicReaderDiagnostic('betfair_sb','coupon');
assert.equal(bf.counts.event_links,1);assert.equal(bf.counts.price_buttons,3);assert.equal(bf.rows[0].prices[1].price,'3.40');
fs.mkdirSync('distribucion/pruebas_diagnostico',{recursive:true});
fs.writeFileSync('distribucion/pruebas_diagnostico/sample.json',JSON.stringify(bf));
console.log('Diagnóstico: fechas, estructura y cuotas públicas; formularios, página completa, cookies y datos de cuenta excluidos.');
