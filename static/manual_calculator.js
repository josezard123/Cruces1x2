(()=>{
  const ids=['q1','qX','q2','stake1','stakeX','stake2'];
  const inputs=Object.fromEntries(ids.map(k=>[k,document.getElementById('manual-'+k)]));
  const mode=document.getElementById('manual-stakes'),status=document.getElementById('calculator-status'),results=document.getElementById('calculator-results');
  let timer,sequence=0;
  const euros=v=>Number(v).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})+' €';
  const save=()=>{try{sessionStorage.setItem('cruces.manualCalculator',JSON.stringify({...Object.fromEntries(ids.map(k=>[k,inputs[k].value])),manual_stakes:mode.checked}));}catch{}};
  const sync=()=>{inputs.stakeX.disabled=inputs.stake2.disabled=!mode.checked;};
  async function calculate(){
    const current=++sequence;
    save();sync();
    const data={...Object.fromEntries(ids.map(k=>[k,inputs[k].value])),manual_stakes:mode.checked};
    if(['q1','qX','q2','stake1',...(mode.checked?['stakeX','stake2']:[])].some(k=>!data[k].trim())){results.hidden=true;status.textContent='Completa las tres cuotas y los importes necesarios.';return;}
    status.textContent='Calculando…';
    try{
      const reply=await fetch('/calculate-manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      const payload=await reply.json();if(current!==sequence)return;
      if(!reply.ok||!payload.ok){results.hidden=true;status.textContent=payload.error||'No se pudo calcular.';return;}
      const r=payload.result;
      if(!mode.checked){inputs.stakeX.value=r.stakeX.toFixed(2);inputs.stake2.value=r.stake2.toFixed(2);}
      document.getElementById('calculator-rows').innerHTML=['1','X','2'].map(k=>`<tr><td>${k}</td><td class="num">${euros(r['stake'+k])}</td><td class="num">${euros(r['return'+k])}</td><td class="num ${r['profit'+k]>=0?'good':'bad'}">${r['profit'+k]>0?'+':''}${euros(r['profit'+k])}</td></tr>`).join('');
      document.getElementById('calculator-summary').textContent=`Total: ${euros(r.total)} · Cobro mínimo: ${euros(r.min_return)} · Peor caso: ${euros(r.worst_profit)}`;
      status.textContent=mode.checked?'Cobertura con tus importes.':'X y 2 calculados a céntimos con la apuesta al 1 fija.';
      results.hidden=false;save();
    }catch{if(current===sequence){results.hidden=true;status.textContent='No se pudo conectar con la calculadora local.';}}
  }
  const changed=()=>{editingSettings=true;sequence++;clearTimeout(timer);timer=setTimeout(calculate,180);};
  Object.values(inputs).forEach(input=>input.addEventListener('input',changed));mode.addEventListener('change',()=>{sync();changed();});
  document.querySelectorAll('.use-calculator').forEach(button=>button.addEventListener('click',()=>{
    inputs.q1.value=button.dataset.q1;inputs.qX.value=button.dataset.qx;inputs.q2.value=button.dataset.q2;inputs.stake1.value=button.dataset.stake;
    mode.checked=false;document.getElementById('calculator-match').textContent=button.dataset.match;
    document.getElementById('manual-calculator').scrollIntoView({behavior:'smooth',block:'start'});changed();
  }));
  try{const stored=JSON.parse(sessionStorage.getItem('cruces.manualCalculator')||'null');if(stored){ids.forEach(k=>{if(typeof stored[k]==='string')inputs[k].value=stored[k];});mode.checked=stored.manual_stakes===true;editingSettings=true;calculate();}}catch{}
  sync();
})();
