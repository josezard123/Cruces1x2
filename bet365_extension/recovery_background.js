// Retry an empty public sports page once with our own scanner tab visible.
// Never reload an unrelated tab or attempt to overcome an access-denied page.
function emptyPublicPage(result) {
 const d=result?.diagnostic,c=d?.counts;
 if(result?.blocked)return false;
 if(result?.retryPublicLoad===true&&['sportium','bet365'].includes(result.source))return true;
 if(!c)return false;
 if(result?.ok&&!(d.source==='sportium'&&Array.isArray(result.events)&&result.events.length===0))return false;
 if(d.source==='bet365')return d.phase==='search'?c.candidate_pairs===0||c.date_nodes<=1:c.market_nodes===0&&c.home_nodes===0&&c.away_nodes===0;
 if(d.source==='betfair_sb')return c.event_links===0&&c.competition_links===0&&c.market_nodes===0;
 if(d.source==='sportium')return c.match_cards===0;
 return false;
}
async function retryEmptyPublicPage(tab,result,retry,cancelled,progress,deadline) {
 if(!emptyPublicPage(result)||typeof chrome.tabs.query!=='function'||await cancelled())return result;
 const query=Number.isInteger(tab.windowId)?{active:true,windowId:tab.windowId}:{active:true,currentWindow:true};
 let previous;
 try {
  const active=await chrome.tabs.query(query);
  if(active.length!==1)return result;
  previous=active[0].id;
  await progress('Recuperando la carga de la página; mostrando la pestaña del lector');
  if(previous!==tab.id)await chrome.tabs.update(tab.id,{active:true});
  if(await cancelled())return result;
  // A hash navigation can leave Bet365 showing only its footer or suggestions.
  // Reload only this scanner tab and reconnect to its new content script.
  if(result.diagnostic?.source==='bet365'&&typeof chrome.tabs.reload==='function'){
   if(deadline&&Date.now()>=deadline)return result;
   await chrome.tabs.reload(tab.id);
   if(typeof waitForReader==='function')await waitForReader(tab.id,undefined,deadline);
   if(await cancelled())return result;
  }
  return await retry();
 }finally{
  if(previous!==undefined&&previous!==tab.id){
   try{
    const active=await chrome.tabs.query(query);
    // Do not take focus back if the user switched to another tab meanwhile.
    if(active.length===1&&active[0].id===tab.id)await chrome.tabs.update(previous,{active:true});
   }catch(_){}
  }
 }
}
