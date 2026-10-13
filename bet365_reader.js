function readBet365Result() {
  if (location.hostname !== 'www.bet365.es') throw new Error('Abre Bet365 España.');
  if (Intl.DateTimeFormat().resolvedOptions().timeZone !== 'Europe/Madrid')
    throw new Error('El navegador debe tener la zona horaria Europe/Madrid.');
  const {league,date,teams,odds,enhanced_odds}=readBet365VisibleMarket();
  const months = {ene:0,jan:0,feb:1,mar:2,abr:3,apr:3,may:4,jun:5,jul:6,ago:7,aug:7,sep:8,oct:9,nov:10,dic:11,dec:11};
  const now = new Date();
  let start = new Date(now.getFullYear(), months[date[2].toLowerCase()], Number(date[1]), Number(date[3]), Number(date[4]));
  if (start < new Date(now.getTime() - 180*86400000)) start.setFullYear(start.getFullYear()+1);
  if (start <= now || start-now > 168*3600000) throw new Error('El partido debe empezar en los próximos siete días.');
  const eventId = /\/E(\d+)\//.exec(location.hash)?.[1];
  if (!eventId) throw new Error('No se reconoce el identificador del encuentro.');
  return {source_url:location.href, observed_at:now.toISOString(), events:[{
    event_id:eventId, home:teams[0], away:teams[1], league, start:start.toISOString(), market:'FULL_TIME_1X2', odds, ...(enhanced_odds?{enhanced_odds}:{}),
  }]};
}

function readBet365VisibleMarket() {
  const main = document.querySelector('[role="main"]');
  if (!main) throw new Error('Abre la página de un partido de fútbol.');
  const lines = main.innerText.split('\n').map(s => s.trim()).filter(Boolean);
  const league=lines[0];
  const dateIndex=lines[1]==='•'?2:1;
  const dateLabel=lines[dateIndex];
  const date = /^(\d{1,2})\s+(ene|jan|feb|mar|abr|apr|may|jun|jul|ago|aug|sep|oct|nov|dic|dec)\s+(\d{2}):(\d{2})$/i.exec(dateLabel);
  if (!date) throw new Error('Se necesita la fecha de un partido prepartido.');
  const match=lines[dateIndex+1]||'';
  const teams = /^v$/i.test(lines[dateIndex+2]||'')?
    [match,lines[dateIndex+3]]:match.split(/\s+v\s+/i);
  if (teams.length !== 2) throw new Error('No se reconocen ambos equipos.');
  // Bet365 changes its generated CSS classes. Identify the exact visible title
  // and the smallest enclosing market with the three named selections instead.
  const visible=n=>n.getClientRects().length>0;
  function extractMarket(names) {
  const titles=[...main.querySelectorAll('*')].filter(n=>!n.children.length && visible(n) &&
    names.includes((n.innerText?.trim().toLowerCase()||'').replace(/[–—]/g,'-').replace(/\s+/g,' ')));
  const markets=titles.map(title=>{
    for(let container=title.parentElement;container && container!==main;container=container.parentElement){
      if([...container.querySelectorAll('*')].some(n=>n!==title && !n.children.length && visible(n) &&
        /^(resultado final|full time result)/i.test(n.innerText?.trim()||'')))return null;
      const rows=[...container.querySelectorAll('*')].filter(n=>{
        if(!visible(n))return false;
        const parts=n.innerText?.split('\n').map(s=>s.trim()).filter(Boolean)||[];
        return parts.length===2 && [teams[0],teams[1],'Empate','Draw'].includes(parts[0]);
      }).filter(n=>![...n.children].some(child=>child.innerText===n.innerText));
      if(rows.length){
        // Never climb into a neighbouring market or take an enhanced-price row.
        return {container,rows};
      }
    }
    return null;
  }).filter(Boolean);
  if (markets.length !== 1) throw new Error('No hay un único mercado Resultado final.');
  const selections = markets[0].rows.map(n => {
    const [name,price]=n.innerText.split('\n').map(s=>s.trim()).filter(Boolean);
    return {name,odds:/^\d+(?:[.,]\d+)?$/.test(price)?Number(price.replace(',','.')):NaN,visible:visible(n)};
  });
  if (selections.length !== 3 || selections.some(s => !s.visible || !Number.isFinite(s.odds) || s.odds <= 1))
    throw new Error('El 1-X-2 no tiene tres cuotas activas visibles.');
  if (selections[0].name !== teams[0] || !['empate','draw'].includes(selections[1].name?.toLowerCase()) || selections[2].name !== teams[1])
    throw new Error('Las selecciones no coinciden con los equipos de la cabecera.');
  return {'1':selections[0].odds,'X':selections[1].odds,'2':selections[2].odds};
  }
  const odds=extractMarket(['resultado final','full time result']);
  let enhanced_odds;
  // Optional enhanced market must independently pass the same three-selection validation.
  try {enhanced_odds=extractMarket(['resultado final - cuotas mejoradas','full time result - enhanced prices']);} catch(_) {}
  return {league,date,teams,odds,enhanced_odds};
}
