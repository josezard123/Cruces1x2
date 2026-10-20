// Local diagnostics from public sports containers only. Never serialize a page,
// form, input value, cookie, network response or private account information.
function diagnosticText(value,max=200) {
 const text=String(value||'').trim().replace(/\s+/g,' ');
 if(!text||text.length>max||/[@<>=€£$]|password|contrase|correo|email|saldo|balance|usuario|account|sesion|sesión|token|cookie|api.?key/i.test(text))return null;
 return /^[\p{L}\p{N}\s.,:;()\[\]/+%•·–—^'-]+$/u.test(text)?text:null;
}
function diagnosticPath(node,root) {
 const result=[];
 for(let n=node;n&&n!==root&&result.length<4;n=n.parentElement){
  result.push({tag:String(n.tagName||'').toLowerCase().replace(/[^a-z0-9-]/g,'').slice(0,24),
   classes:String(n.className||'').split(/\s+/).filter(s=>/^[a-zA-Z0-9_-]{1,90}$/.test(s)).slice(0,8),
   role:['button','heading','main','link','group','list','listitem','row','cell'].includes(n.getAttribute?.('role'))?n.getAttribute('role'):''});
 }
 return result;
}
function publicReaderDiagnostic(source,phase,target={},aliases={}) {
 const root=document.querySelector('[role="main"]')||null;
 const visible=n=>n.getClientRects?.().length>0&&!n.closest?.('form,input,textarea,[contenteditable="true"]');
 const clean=s=>String(s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim();
 const team=s=>{let name=clean(s);name=aliases[name]||name;name=name.split(' ').filter(x=>!['fc','cf','afc','sc','ac','club','futbol','football'].includes(x)).join(' ');return clean(aliases[name]||name);};
 const home=team(target.home),away=team(target.away);
 const nodes=[];const counts={main:root?1:0,event_links:0,competition_links:0,match_cards:0,price_buttons:0,date_nodes:0,home_nodes:0,away_nodes:0,market_nodes:0,candidate_pairs:0};
 if(source==='bet365'&&root){
  for(const n of root.querySelectorAll('*')){
   if(!visible(n))continue;
   const text=diagnosticText(n.innerText);if(!text)continue;
   const leaf=!n.children.length||[...n.children].every(child=>!diagnosticText(child.innerText));
   let kind='';
   if(leaf&&(/\b\d{1,2}:\d{2}\b/.test(text)||/^(hoy|today|ma[nñ]ana|tomorrow)$/i.test(text)||/^\d{1,2}\/\d{1,2}(?:\/\d{4})?$/.test(text)||/\b\d{1,2}\s+(?:ene|jan|feb|mar|abr|apr|may|jun|jul|ago|aug|sep|oct|nov|dic|dec)\b/i.test(text)))kind='date';
   else if(leaf&&home&&team(text)===home)kind='home';
   else if(leaf&&away&&team(text)===away)kind='away';
   else if(leaf&&/^(?:resultado final|full time result)(?:\s*[–—-]\s*(?:cuotas mejoradas|enhanced prices))?$/i.test(text))kind='market';
   else if(home&&away&&clean(text).includes(home)&&clean(text).includes(away)&&![...n.children].some(c=>clean(c.innerText).includes(home)&&clean(c.innerText).includes(away)))kind='pair';
   if(!kind)continue;
   counts[{date:'date_nodes',home:'home_nodes',away:'away_nodes',market:'market_nodes',pair:'candidate_pairs'}[kind]]++;
   if(nodes.length<40)nodes.push({kind,text,path:diagnosticPath(n,root)});
  }
 }
 const competitions=[],rows=[],cards=[];
 if(source==='betfair_sb'){
  for(const a of document.querySelectorAll('a')){
   const href=a.getAttribute('href')||'';
   if(/^(?:\/apuestas\/)?f%C3%BAtbol\/[^/]+\/c-\d+$/i.test(href)){
    counts.competition_links++;const name=diagnosticText(a.innerText,120);
    if(name&&competitions.length<40)competitions.push({name,path:href});
   }
   const id=/\/e-(\d+)$/.exec(href)?.[1];if(!id||!visible(a))continue;
   counts.event_links++;
   const teams=[...a.querySelectorAll('[data-testid="team-name"]')].map(n=>diagnosticText(n.innerText,120));
   const date=diagnosticText(a.querySelector('time')?.getAttribute('datetime'),100)||'';
   const buttons=[...a.parentElement.querySelectorAll('button')].filter(n=>visible(n)&&/^\d+(?:[.,]\d+)?$/.test((n.innerText||'').trim()));
   counts.price_buttons+=buttons.length;
   if(rows.length<20&&teams.length===2&&teams.every(Boolean))rows.push({id,teams,date,prices:buttons.slice(0,12).map(n=>({price:n.innerText.trim(),active:!n.disabled&&n.getAttribute('aria-disabled')!=='true'})),path:diagnosticPath(a,null)});
  }
  for(const n of document.querySelectorAll('button')){
   const text=diagnosticText(n.innerText);
   if(visible(n)&&text&&/seleccionar mercado/i.test(text)){counts.market_nodes++;if(nodes.length<40)nodes.push({kind:'market',text,path:diagnosticPath(n,null)});}
  }
 }
 if(source==='winamax_es'){
  for(const n of document.querySelectorAll('[data-testid^="match-card-"]')){
   if(!visible(n))continue;counts.match_cards++;
   const id=(n.getAttribute('data-testid')||'').replace('match-card-','');
   const lines=(n.innerText||'').split('\n').map(s=>s.trim()).filter(Boolean).slice(0,14).map(s=>diagnosticText(s,120));
   if(/^\d+$/.test(id)&&lines.every(Boolean)&&cards.length<40)cards.push({id,lines});
  }
 }
 if(source==='sportium'){
  for(const n of document.querySelectorAll('.ta-EventListGroup .ta-EventListItem')){
   if(!visible(n))continue;counts.match_cards++;
   const href=n.querySelector('a.ta-EventListItemDetails')?.getAttribute('href')||'';
   const id=/^\/apuestas\/sports\/soccer\/events\/(\d+)$/.exec(href)?.[1];
   const lines=(n.innerText||'').split('\n').map(s=>s.trim()).filter(Boolean).slice(0,14).map(s=>diagnosticText(s,120));
   if(id&&lines.every(Boolean)&&cards.length<40)cards.push({id,lines});
  }
 }
 return {schema:1,reader_version:'2.1.4',source,phase,target:{home:diagnosticText(target.home,120)||'',away:diagnosticText(target.away,120)||''},event_id:source==='bet365'?(/\/E(\d+)\//.exec(location.hash||'')?.[1]||''):'',counts,nodes,competitions,rows,cards};
}
