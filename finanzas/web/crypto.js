'use strict';
Object.assign(labels,{operation:'Datos acreditados',effects:'Variaciones por activo',
  spot_buy:'Spot · compra',spot_sell:'Spot · venta',yield:'Rendimiento pagado',derivative:'Derivado · observación',bot_summary:'Bot · resumen observado',
  base_asset:'Activo base',quote_asset:'Activo cotizado',quote_amount:'Importe ejecutado sin comisión',fee_amount:'Comisión',fee_asset:'Activo de comisión',
  occurred_at:'Fecha y hora UTC acreditadas',order_id:'Orden',trade_id:'Ejecución',transaction_id:'Identificador de pago',bot_id:'Identificador del bot',
  contracts_unit:'Unidad de contratos',settlement_asset:'Activo de liquidación',realized_pnl:'PnL realizado observado',unrealized_pnl:'PnL no realizado observado',
  funding:'Funding observado',profit_amount:'Beneficio publicado del bot',asset:'Activo',recorded_change:'Variación registrada · no saldo',
  executed:'Ejecución acreditada',paid:'Pago acreditado',snapshot:'Resumen observado',component:'Componente',base:'Activo base',quote:'Contrapartida cotizada',fee:'Comisión',
});
const cryptoFields={
  spot_buy:['order_id','trade_id','base_asset','quote_asset','quantity','quote_amount','fee_amount','fee_asset'],
  spot_sell:['order_id','trade_id','base_asset','quote_asset','quantity','quote_amount','fee_amount','fee_asset'],
  yield:['transaction_id','asset','amount','fee_amount','fee_asset'],
  derivative:['order_id','trade_id','pair','contracts','contracts_unit','settlement_asset','realized_pnl','unrealized_pnl','funding','fee_amount','fee_asset'],
  bot_summary:['bot_id','profit_amount','asset'],
};
const cryptoOptional=new Set(['fee_amount','fee_asset','settlement_asset','realized_pnl','unrealized_pnl','funding','profit_amount']);
const cryptoNumbers=new Set(['quantity','quote_amount','amount','fee_amount','contracts','realized_pnl','unrealized_pnl','funding','profit_amount']);
async function showCryptoReview(){
  const panel=$('crypto-review');panel.hidden=false;panel.replaceChildren();const doc=current;
  const initial=await api('/api/documents/'+doc.id+'/crypto-plan');
  panel.append(el('h2','Registro revisado de operación cripto'));
  const source=el('details',undefined,'data-section');source.append(el('summary','Ver captura original'));const image=el('img');image.className='crypto-source';image.alt='Captura original para contrastar la operación';image.src='/api/documents/'+doc.id+'/image';image.onerror=()=>{image.hidden=true;source.append(el('p','Este navegador no representa el formato de la imagen. Descarga el original para revisarlo.'));};source.append(image);panel.append(source);
  if(initial.status==='confirmed'){
    panel.append(el('p','Esta captura ya tiene un registro confirmado. Su evidencia se conserva sin duplicar la operación.'));
    const open=el('button','Ver registro cripto');open.onclick=()=>run(openCryptoBook);panel.append(open);return;
  }
  for(const warning of initial.warnings||[])panel.append(el('p',warning,'footnote'));
  if(!initial.platform){for(const issue of initial.issues)panel.append(el('p',issue,'alert'));return;}
  const candidates=initial.candidates||[];
  const candidate=key=>{const all=candidates.filter(f=>f.name===key);return all.length===1&&!all[0].issues.length?all[0]:null;};
  const hint=key=>candidate(key)?.value??'';
  const account=el('input'),kind=el('select'),when=el('input'),status=el('select');account.type=when.type='text';
  account.setAttribute('aria-label','Cuenta cripto');account.placeholder='Alias estable por cuenta/subcuenta';when.setAttribute('aria-label','Fecha cripto con desplazamiento');
  when.value=String(hint('time')).replace(' ','T');when.placeholder='2026-01-05T12:00:00+00:00';
  kind.setAttribute('aria-label','Tipo de operación cripto');kind.append(new Option('Selecciona el tipo',''));
  for(const key of Object.keys(cryptoFields))kind.append(new Option(label(key),key));
  const detected=doc.result.views.investments.data.operation_kind;kind.value=Object.hasOwn(cryptoFields,detected)?detected:'';
  status.setAttribute('aria-label','Estado cripto acreditado');
  for(const [title,input] of [['Cuenta / subcuenta',account],['Tipo',kind],['Fecha y hora con desplazamiento horario explícito',when],['Estado acreditado',status]]){const caption=el('label',title);caption.append(input);panel.append(caption);}
  panel.append(el('p','No se presume la zona horaria de la plataforma. Usa el desplazamiento que acreditaste. El importe spot es el ejecutado sin comisión; no se calcula multiplicando precio y cantidad.','footnote'));
  const fields=el('div'),result=el('div'),check=el('input');check.type='checkbox';check.setAttribute('aria-label','Captura cripto verificada');const caption=el('label',undefined,'opening-review');
  caption.append(check,el('span','Verifiqué identidad de cuenta, ejecución/pago/resumen, importes, activos y zona horaria contra la captura y mis fuentes.'));
  let controls={},prepared=null;
  const invalidate=()=>{prepared=null;result.replaceChildren();check.checked=false;};
  function draw(){
    invalidate();fields.replaceChildren();controls={};status.replaceChildren(new Option('Seleccionar estado',''));
    const stateCode=kind.value==='bot_summary'?'snapshot':kind.value==='yield'?'paid':'executed';status.append(new Option(label(stateCode),stateCode));
    for(const key of cryptoFields[kind.value]||[]){
      const box=el('label',label(key)+(cryptoOptional.has(key)?' · opcional':'')),input=el('input');input.type='text';input.setAttribute('aria-label','Cripto '+key);if(cryptoNumbers.has(key))input.inputMode='decimal';
      let proposed=hint(key);
      if(key==='quote_amount')proposed=hint('total');
      if(['base_asset','quote_asset'].includes(key)){const pair=String(hint('pair')).split('/');proposed=pair.length===2?pair[key==='base_asset'?0:1]:'';}
      if(key==='fee_amount')proposed=hint('fee');if(key==='fee_asset')proposed=candidate('fee')?.unit??'';
      if(key==='profit_amount')proposed=hint('bot_profit');
      if(key==='contracts_unit')proposed=candidate('contracts')?.unit??'';
      if(key==='asset')proposed=candidate(kind.value==='yield'?'yield':'bot_profit')?.unit??'';
      if(key==='amount'&&kind.value==='yield')proposed=hint('yield');
      input.value=String(proposed??'');input.oninput=invalidate;controls[key]=input;box.append(input);fields.append(box);
    }
  }
  kind.onchange=draw;account.oninput=when.oninput=status.onchange=invalidate;draw();
  const prepare=el('button','Preparar registro cripto');prepare.onclick=()=>run(async()=>{
    const review={account:account.value.trim(),kind:kind.value,occurred_at:when.value.trim(),status:status.value,verified:check.checked};
    for(const [key,input] of Object.entries(controls)){const val=input.value.trim();review[key]=val===''&&(cryptoOptional.has(key)||(key==='asset'&&kind.value==='bot_summary'))?null:val;}
    prepared=await api('/api/documents/'+doc.id+'/crypto-plan',{revision:doc.revision,review});result.replaceChildren();
    for(const issue of prepared.issues)result.append(el('p',issue,'alert'));
    if(!prepared.can_confirm)return;
    if(prepared.duplicate_operation)result.append(el('p','Esta ejecución/pago ya existe con los mismos datos. Se añadirá solo esta evidencia.','alert success'));
    renderObject({operation:prepared.operation,effects:prepared.effects},result);
    const confirm=el('button','Confirmar registro cripto','primary');confirm.onclick=()=>run(async()=>{
      if(!prepared||!check.checked)throw new Error('Vuelve a verificar y preparar la captura.');
      await api('/api/documents/'+doc.id+'/crypto-confirm',{revision:doc.revision,review:prepared.review,plan_hash:prepared.plan_hash});await showCryptoReview();message('Operación/evidencia cripto registrada sin duplicación.');
    });result.append(confirm);
  });panel.append(fields,caption,prepare,result);
}
async function openCryptoBook(){
  financialPassword=null;selected=null;const data=await api('/api/crypto');renderNavigation();
  for(const id of ['overview','detail','book'])$(id).hidden=true;$('crypto').hidden=false;$('all').classList.remove('selected');$('book-nav').classList.remove('selected');$('crypto-nav').classList.add('selected');$('crumb').textContent='Registro cripto';
  const target=$('crypto-content');target.replaceChildren(el('p',data.note,'footnote'));
  target.append(el('p',`${data.operations.length} operaciones/resúmenes · ${data.documents} capturas · ${data.unknown_fee_operations} comisiones desconocidas`,'subtitle'));
  if(!data.operations.length){target.append(el('p','Sube una captura BingX/Pionex y prepara su registro revisado.','empty'));return;}
  for(const platform of ['bingx','pionex']){
    const ops=data.operations.filter(o=>o.platform===platform);if(!ops.length)continue;
    target.append(el('h2',name(platform)));
    renderArray(data.asset_changes.filter(a=>a.platform===platform).map(a=>({account_name:a.account,asset:a.asset,recorded_change:a.recorded_change})),target);
    for(const kind of Object.keys(cryptoFields)){
      const selected=ops.filter(o=>o.kind===kind);if(!selected.length)continue;
      const group=el('details',undefined,'data-section');group.append(el('summary',label(kind)+' · '+selected.length));
      let page=0;const rows=el('div'),pager=el('div',undefined,'pager'),prev=el('button','←'),next=el('button','→'),count=el('span');
      function draw(){rows.replaceChildren();for(const op of selected.slice(page*25,(page+1)*25)){
        const item=el('details',undefined,'data-section');item.append(el('summary',op.occurred_at+' · '+op.account));
        renderObject(Object.fromEntries(Object.entries(op).filter(([key])=>!['sources','effects','id','platform'].includes(key))),item);
        if(op.effects.length)renderArray(op.effects,item);
        for(const source of op.sources){const open=el('button','Abrir captura · '+source.document_id.slice(0,10));open.onclick=()=>run(()=>openDocument(source.document_id));item.append(open);}
        rows.append(item);
      }prev.disabled=page===0;next.disabled=(page+1)*25>=selected.length;count.textContent=`${page*25+1}–${Math.min((page+1)*25,selected.length)} de ${selected.length}`;}
      prev.onclick=()=>{page--;draw();};next.onclick=()=>{page++;draw();};pager.append(prev,count,next);group.append(rows,pager);draw();target.append(group);
    }
  }
}
$('crypto-nav').onclick=()=>run(openCryptoBook);$('crypto-refresh').onclick=()=>run(openCryptoBook);
