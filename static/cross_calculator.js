(()=>{
  const fields=['q1','qX','q2','stake1','stakeX','stake2'],bound=new WeakSet();
  const euros=(value,signed=false)=>`${signed&&value>0?'+':''}${Number(value).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} €`;
  function bind(root){
    if(bound.has(root))return;bound.add(root);
    const inputs=Object.fromEntries(fields.map(key=>[key,root.querySelector(`[data-calc-field="${key}"]`)]));
    const manual=root.querySelector('[data-calc-manual]'),status=root.querySelector('[data-calc-status]');
    const outputs=[...root.querySelectorAll('[data-calc-value]')];
    const original=Object.fromEntries(fields.map(key=>[key,inputs[key].value]));
    let timer,sequence=0,request;
    const sync=()=>{inputs.stakeX.disabled=inputs.stake2.disabled=!manual.checked;};
    const clear=()=>{outputs.forEach(node=>{node.textContent='—';node.classList.remove('good','bad','warn');});};
    async function calculate(current){
      const data={...Object.fromEntries(fields.map(key=>[key,inputs[key].value])),manual_stakes:manual.checked};
      const required=['q1','qX','q2','stake1',...(manual.checked?['stakeX','stake2']:[])];
      if(required.some(key=>!data[key].trim())){root.setAttribute('aria-busy','false');status.textContent='Completa las cuotas y los importes de este cruce.';return;}
      request=new AbortController();
      try{
        const response=await fetch('/calculate-manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:request.signal});
        const payload=await response.json();if(current!==sequence)return;
        if(!response.ok||!payload.ok){status.textContent=payload.error||'No se pudo calcular este cruce.';status.classList.add('bad');return;}
        const result=payload.result;
        if(!manual.checked){inputs.stakeX.value=result.stakeX.toFixed(2);inputs.stake2.value=result.stake2.toFixed(2);}
        outputs.forEach(node=>{
          const key=node.dataset.calcValue,signed=key==='worst_profit'||key.startsWith('profit');
          node.textContent=euros(result[key],signed);
          if(signed){node.classList.toggle('good',result[key]>=0);node.classList.toggle('bad',result[key]<0);}
        });
        status.textContent=manual.checked?'Cobertura con tus tres importes.':'X y 2 recalculados a céntimos con la apuesta al 1 fija.';
      }catch(error){if(current===sequence&&error.name!=='AbortError'){status.textContent='No se pudo conectar con la calculadora local.';status.classList.add('bad');}}
      finally{if(current===sequence){request=null;root.setAttribute('aria-busy','false');}}
    }
    const changed=()=>{
      document.dispatchEvent(new CustomEvent('cruces-calculator-edit'));
      const current=++sequence;clearTimeout(timer);request?.abort();sync();clear();
      root.setAttribute('aria-busy','true');status.classList.remove('bad');status.textContent='Calculando…';
      timer=setTimeout(()=>calculate(current),180);
    };
    root.addEventListener('input',event=>{if(event.target.matches('[data-calc-field]'))changed();});
    manual.addEventListener('change',changed);
    root.querySelector('[data-calc-reset]').addEventListener('click',()=>{fields.forEach(key=>{inputs[key].value=original[key];});manual.checked=false;changed();});
    sync();
  }
  document.querySelectorAll('[data-cross-calculator]').forEach(bind);
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-inline-toggle]');if(!button)return;
    const panel=document.getElementById(button.dataset.inlineToggle);if(!panel)return;
    const opening=panel.hidden;
    if(opening){
      const host=panel.querySelector('[data-inline-host]');
      if(!host.querySelector('[data-cross-calculator]')){host.appendChild(panel.querySelector('template').content.cloneNode(true));bind(host.querySelector('[data-cross-calculator]'));}
    }
    panel.hidden=!opening;button.setAttribute('aria-expanded',String(opening));button.textContent=opening?'Cerrar calculadora':'Calcular aquí';
    if(opening)panel.querySelector('[data-calc-field="stake1"]').focus({preventScroll:true});
  });
})();
