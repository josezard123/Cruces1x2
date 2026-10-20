// Exchange public match tasks only; never read forms or credentials.
document.documentElement.dataset.crucesReader='ready';
document.documentElement.dataset.crucesReaderVersion='2.1.5';
document.addEventListener('cruces-read-exchange',async event=>{
  try {
    const result=await chrome.runtime.sendMessage({type:'automatic-exchange-scan',source:String(event.detail?.source||'winamax_es')});
    document.dispatchEvent(new CustomEvent('cruces-exchange-finished',{detail:result}));
  }catch(_){document.dispatchEvent(new CustomEvent('cruces-exchange-finished',{detail:{ok:false}}));}
});
document.dispatchEvent(new CustomEvent('cruces-reader-ready'));
document.addEventListener('cruces-automatic-bet365',async event=>{
  try {
    const sources=Array.isArray(event.detail?.sources)?event.detail.sources.filter(s=>['winamax_es','betfair_sb','bet365','sportium','retabet'].includes(s)):['bet365'];
    const result=await chrome.runtime.sendMessage({type:'automatic-bet365-scan',filter:{home:String(event.detail?.home||'').slice(0,120),away:String(event.detail?.away||'').slice(0,120),sources,missing:event.detail?.missing===true}});
    document.dispatchEvent(new CustomEvent('cruces-automatic-finished',{detail:result}));
  } catch(_) {document.dispatchEvent(new CustomEvent('cruces-automatic-finished',{detail:{ok:false,reason:'reader-error'}}));}
});
document.addEventListener('cruces-refresh-bet365',async()=>{
  try {
    const result=await chrome.runtime.sendMessage({type:'refresh-open-bet365'});
    document.dispatchEvent(new CustomEvent('cruces-bet365-refreshed',{detail:result}));
  } catch(_) {document.dispatchEvent(new CustomEvent('cruces-bet365-refreshed',{detail:{ok:false,captured:0}}));}
});
