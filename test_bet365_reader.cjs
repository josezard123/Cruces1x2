const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
class Element {
  constructor(text='',children=[],hidden=false){this.children=children;this.hidden=hidden;this.text=text;for(const n of children)n.parentElement=this;}
  get innerText(){return this.text||this.children.map(n=>n.innerText).join('\n');}
  getClientRects(){return this.hidden?[]:[{}];}
  querySelectorAll(){return this.children.flatMap(n=>[n,...n.querySelectorAll('*')]);}
  closest(){for(let node=this;node;node=node.parentElement)if(node.role==='button'||node.role==='heading')return node;return null;}
}
function fixture(title,draw,teams=['Croatia','Spain'],hidden=false){
  return new Element('',[new Element('',[new Element(title)]),new Element('',[teams[0],draw,teams[1]].map((name,index)=>new Element('',[new Element(name),new Element(['8.50','6.25','1.27'][index])],hidden)))],hidden);
}
function read(markets,teams=['Croatia','Spain'],separated=false){
  const header=separated?`International Match\n6 oct 19:00\n${teams[0]}\nV\n${teams[1]}`:`UEFA Nations League A\n•\n6 oct 20:45\n${teams[0]} v ${teams[1]}`;
  const main=new Element(header,markets);
  const context={document:{querySelector(){return main;}}};
  vm.createContext(context);vm.runInContext(fs.readFileSync('bet365_reader.js','utf8'),context);
  return context.readBet365VisibleMarket();
}
assert.equal(read([fixture('Full Time Result','Draw'),fixture('Full Time Result – Enhanced Prices','Draw')]).odds['1'],8.5);
assert.equal(read([fixture('Resultado final','Empate',['Croacia','España'])],['Croacia','España']).odds.X,6.25);
assert.equal(read([fixture('Full Time Result','Draw'),fixture('Full Time Result','Draw',undefined,true)]).odds['2'],1.27);
assert.throws(()=>read([fixture('First Half Result','Draw')]),/único mercado/);
assert.throws(()=>read([fixture('Full Time Result – Enhanced Prices','Draw')]),/único mercado/);
assert.throws(()=>read([fixture('Full Time Result','Draw'),fixture('Full Time Result','Draw')]),/único mercado/);
assert.throws(()=>read([fixture('Full Time Result','Home')]),/tres cuotas/);
assert.throws(()=>read([fixture('Full Time Result','Draw',['Croatia U21','Spain'])]),/tres cuotas/);
const collapsed=new Element('',[new Element('Full Time Result')]);
assert.throws(()=>read([collapsed,fixture('Full Time Result – Enhanced Prices','Draw')]),/único mercado/);
console.log('Lector sin clases CSS: español/inglés, duplicados ocultos, mercado colapsado y cuotas de mercados incorrectos comprobados.');

assert.equal(read([fixture('Full Time Result','Draw',['Jordan','Venezuela'])],['Jordan','Venezuela'],true).league,'International Match');

const normal=fixture('Resultado final','Empate',['Real Madrid','Villarreal']);
const enhanced=fixture('Resultado final – Cuotas mejoradas','Empate',['Real Madrid','Villarreal']);
enhanced.children[1].children.forEach((row,i)=>row.children[1].text=['1.370','5.800','8.000'][i]);
const both=read([normal,enhanced],['Real Madrid','Villarreal']);
assert.equal(both.odds['1'],8.5);
assert.equal(both.enhanced_odds['1'],1.37);
assert.equal(both.enhanced_odds['2'],8);
assert.equal(read([normal],['Real Madrid','Villarreal']).enhanced_odds,undefined);
assert.equal(read([normal,enhanced,enhanced],['Real Madrid','Villarreal']).enhanced_odds,undefined);
console.log('Cuotas mejoradas: lectura independiente, ausencia y ambigüedad comprobadas.');

// Public Bet365 layout: an Opta tip repeats the title and a single draw price.
function marketHeading(title,draw='Empate',teams=['Real Madrid','Villarreal']){
 const market=fixture(title,draw,teams);market.children[0].role='button';return market;
}
function informationTip(title='Resultado final'){
 return new Element('',[new Element(title),new Element('',[new Element('Empate'),new Element('99.00')])]);
}
const titledNormal=()=>marketHeading('Resultado final');
const titledEnhanced=()=>marketHeading('Resultado final – Cuotas mejoradas');
for(const language of [['Resultado final','Empate'],['Full Time Result','Draw']]){
 const active=marketHeading(...language);
 const info=informationTip(language[0]);
 for(const markets of [[info,active],[active,info]]){
  assert.equal(read(markets,['Real Madrid','Villarreal']).odds.X,6.25);
 }
}
const informationAndMarkets=read([informationTip(),titledNormal(),titledEnhanced()],['Real Madrid','Villarreal']);
assert.equal(informationAndMarkets.odds.X,6.25);
assert.equal(informationAndMarkets.enhanced_odds.X,6.25);
assert.throws(()=>read([informationTip(),titledNormal(),titledNormal()],['Real Madrid','Villarreal']),/único mercado/);
const closedNormal=new Element('',[new Element('Resultado final')]);closedNormal.role='button';
assert.throws(()=>read([informationTip(),closedNormal,titledEnhanced()],['Real Madrid','Villarreal']),/único mercado/);
const invalidNormal=titledNormal();invalidNormal.children[1].children[1].children[1].text='Suspendida';
assert.throws(()=>read([informationTip(),invalidNormal],['Real Madrid','Villarreal']),/tres cuotas/);
const onlyEnhanced=read([informationTip('Resultado final – Cuotas mejoradas'),titledNormal()],['Real Madrid','Villarreal']);
assert.equal(onlyEnhanced.enhanced_odds,undefined);
console.log('Bet365: títulos en tarjetas Opta excluidos; mercados reales, mejoradas opcionales y rechazo de duplicados o cuotas incompletas comprobados.');
