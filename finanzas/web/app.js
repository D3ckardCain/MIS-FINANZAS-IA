'use strict';
const $ = id => document.getElementById(id);
let state, current, financialPlan, financialPassword = null, selected = null, lane = 'debit', busy = false;
const labels = {
  nu_summary_observation:'Resumen global Nu observado',nu_changes_observation:'Cambios documentales por Cajita',nu_freeze_observations:'Congelamientos y liberaciones observados',
  cajitas_aggregate:'Cajitas · agregado',cajita:'Cajita',collateral:'Crédito con garantía',guarantee:'Garantía',
  calculated_final:'Cierre calculado desde el libro vigente',closing_difference:'Diferencia: calculado menos documental',cash_change:'Cambio neto de efectivo',
  external_contributions:'Aportaciones externas / cashback acreditados',cashback_contributions:'Aportaciones de cashback',
  own_transfer_in:'Aportaciones desde cuentas propias',own_transfer_out:'Reducciones hacia cuentas propias',
  reinvestment_in:'Aportaciones por reinversión vinculada',reinvestment_out:'Reducciones por reinversión vinculada',
  interest_documented:'Interés clasificado en el libro',boundary_difference:'Diferencia con cierre contiguo anterior',
  period_movement_count:'Movimientos del período',
  summary:'Resumen publicado', rows:'Movimientos', entries:'Registros', observations:'Evidencia extraída',
  initial:'Saldo inicial', final:'Saldo final', deposits:'Depósitos', withdrawals:'Retiros',
  deposits_and_income:'Depósitos y rendimientos', gross_income_reported:'Interés bruto publicado',
  isr_withheld_printed:'ISR retenido publicado', other_charges_printed:'Otros cargos publicados',
  withdrawals_printed:'Retiros publicados', commissions_printed:'Comisiones publicadas',
  vat_withheld_printed:'IVA retenido publicado',
  annual_rate_reported:'Tasa anual publicada', average_balance_reported:'Saldo promedio publicado',
  gat_nominal_reported:'GAT nominal publicado', gat_real_reported:'GAT real publicado',
  interest:'Interés', withholding:'Retención', fees:'Comisiones', vat:'IVA', isr:'ISR',
  cash_withdrawals:'Retiros en efectivo',other_charges:'Otros cargos',
  identity_source:'Origen de la identidad',explicit_debit_account:'Cuenta de débito publicada',
  parent_debit_account_and_product:'Cuenta padre y producto publicados',
  debit_movement:'Movimiento operativo',to_investments:'Reducción hacia Apartado',
  from_investments:'Entrada desde Apartado',from_debit:'Aportación desde débito',to_debit:'Reducción hacia débito',
  movements:'Movimientos propuestos',
  account_name:'Cuenta / producto',
  product:'Producto',locator:'Referencia de evidencia',
  shared_account:'Cuenta compartida entre vistas',payment_groups:'Cobros de interés e ISR vinculados',
  interest_net_of_withholding:'Interés menos ISR retenido',credits:'Depósitos',gross_interest:'Interés bruto',
  charges_fees_and_vat:'Comisiones e IVA',commission:'Comisión',commission_vat:'IVA de comisión',
  cash_deposit:'Depósito de efectivo',transfer:'Transferencia pendiente de enlazar',transfer_return:'Devolución de transferencia',
  transfer_unmatched:'Transferencia pendiente de enlazar',rate_disclosure:'Condiciones históricas publicadas',
  annual_rates_reported:'Tasas anuales publicadas (%)',direction:'Sentido',average:'Saldo promedio',
  internal_transfer:'Traspaso pendiente de identificar',term_transfer:'Apartado pendiente de identificar',
  deposit_unmatched:'Aportación pendiente de origen',investment_transfer_evidence:'Evidencia de traspasos o Apartados',
  destination_unverified:'Destino y propiedad pendientes de comprobar',
  withdrawals_or_spending:'Retiros o gastos publicados',purchases:'Compras publicadas',
  currency_markers:'Monedas reconocidas en el documento',issuer_printed:'Emisor publicado',scope:'Alcance',
  operational_cash:'Cuenta operativa',account_statement:'Estado de cuenta',movement_report:'Reporte de movimientos',
  format:'Formato',investment_balance:'Saldo de inversión',commissions:'Comisiones',
  role:'Uso de la cuenta',transit:'Cuenta de paso',
  commissions_reported:'Comisiones publicadas',vat_reported:'IVA publicado',average_balance:'Saldo promedio',
  portfolio_initial_reported:'Posición inicial publicada',portfolio_final_reported:'Posición final publicada',
  gat_nominal:'GAT nominal',gat_real:'GAT real',other_positions:'Otros productos publicados',
  description_printed:'Descripción publicada',income_groups:'Cobros vinculados',gross:'Interés bruto',
  net:'Interés menos retención',reference_root:'Grupo de referencias',
  interest_reference:'Referencia del interés',withholding_reference:'Referencia del ISR',
  accrual_start:'Inicio del rango remunerado',accrual_end:'Fin del rango remunerado',
  operation_date:'Fecha de operación', posting_date:'Fecha de cargo', effective_date:'Fecha efectiva',
  date:'Fecha', description:'Descripción', amount:'Importe', deposit:'Abono', withdrawal:'Cargo',
  balance:'Saldo', category:'Tipo de movimiento', currency:'Moneda', exchange_rate:'Tipo de cambio',
  reference:'Referencia', period_start:'Inicio del período', period_end:'Fin del período',
  page:'Página', line:'Línea', outside_period:'Fuera del período', contracts:'Contratos',
  positions:'Posiciones', portfolio:'Cartera', loans:'Préstamos', fields:'Campos extraídos',
  transfer_candidates:'Transferencias candidatas', aggregate:'Resumen global del documento',
  aggregate_isr_basis:'Base observada del ISR global', annex_pages:'Páginas de anexo excluidas',
  issues:'Alertas', detail_issues:'Alertas de detalle', cash_issues:'Alertas de efectivo',
  contract_issues:'Alertas de contratos', document_preview:'Lectura documental', evidence:'Evidencia',
  confidence:'Confianza OCR', text:'Texto', unit:'Unidad', value:'Valor', raw_value:'Valor original',
  status:'Estado', periods:'Períodos detectados', account_fingerprint:'Huella de cuenta',
  term_snapshots:'Posiciones a plazo · observaciones documentales',
  renewal_proposals:'Propuestas de reinversión pendientes', investment_summary_observation:'Resumen de inversiones observado',
  as_of:'Fecha del estado', projected_gross:'Interés bruto proyectado', projected_retention:'Retención proyectada',
  projected_net:'Interés neto proyectado', documentary_observation:'Observación documental',
  capital_at_maturity_reported:'Capital al vencimiento publicado', maturity_amount_form:'Forma del capital al vencimiento',
  principal_only:'Solo principal', principal_plus_net:'Principal más interés neto',
  source_document:'Documento de origen', snapshot_key:'Huella de posición',
  document_id:'Huella documental', relationship_fingerprint:'Huella de relación', id:'Identificador',
  evidence_id:'Identificador de evidencia', name:'Campo', operation_kind:'Tipo de operación',
  timezone:'Zona horaria', account:'Cuenta', source_lines:'Líneas de origen',
  principal:'Capital', principal_paid:'Capital pagado', interest_paid:'Interés pagado',
  maturity:'Vencimiento', rate:'Tasa', start:'Inicio', end:'Fin', quantity:'Cantidad',
  debit:'Cargo', credit:'Abono', investments:'Inversiones', reconciled:'Conciliación',
  cuenta_a_la_vista_remunerada:'Cuenta a la vista remunerada',
  candidate_requires_review:'Candidato pendiente de revisión', interest_received:'Interés cobrado',
  first_period:'Primer período importado', through:'Cierre al', closing:'Saldo de cierre documental',
  pending_origins:'Orígenes pendientes', gaps:'Huecos entre períodos importados',
  devolucion_comision:'Devolución de comisión',
  reverso_interes:'Cancelación de interés',reverso_iva_recibido:'Cancelación de IVA recibido',devolucion_isr:'Devolución de ISR',devolucion_iva_pagado:'Devolución de IVA retenido',
  ordinary_interest:'Interés ordinario',late_interest:'Interés moratorio',ordinary_vat:'IVA ordinario',late_vat:'IVA moratorio',
  retention_isr:'ISR retenido',retention_vat:'IVA retenido',cancellation_links:'Cancelaciones enlazadas',history_checks:'Continuidad y cambios acumulados cotejados',payment_flow_observation:'Pagos informados · bruto y neto de cancelaciones',gross:'Bruto',net:'Neto',indistinguishable:'Bruto y neto coinciden',unexplained:'Sin conciliar',
  iva_recibido:'IVA recibido',iva_pagado:'IVA pagado',recompensa:'Recompensa',
  vat_received:'IVA recibido',vat_paid:'IVA pagado',rewards:'Recompensas',
  withholding_documented:'Retención documentada · cobertura parcial',
  fund_initial_positions:'Fondos · posición anterior observada',fund_final_positions:'Fondos · posición actual observada',
  cobro_valores_sin_desglose:'Cobro de valores · desglose pendiente',security_proceeds:'Cobros de valores sin desglose',
  interest_reported:'Interés informado · sin asignación a cobros',security_receipts:'Cobros pendientes de separar en capital/interés',
  security_initial_positions:'Valores · posición inicial observada',security_final_positions:'Valores · posición final observada',
  security_summary_observation:'Resumen de valores observado',reported_results_observation:'Resultados informativos',
  principal_interest_unallocated:'Capital/interés sin asignación',
  dividends:'Dividendos cobrados',foreign_withholding:'Retención extranjera',income_net_foreign_withholding:'Ingresos menos retención extranjera',
  dividendo_cobrado:'Dividendo cobrado',retencion_extranjera:'Retención extranjera',stock_positions:'Posiciones observadas de acciones/ETF',
  stock_summary_observation:'Resumen bursátil observado',trade_observations:'Operaciones observadas',memo_observations:'Anotaciones Memopost',
  fund_summary_observation:'Resumen de fondos observado',
  loan_snapshots:'Cartera de préstamos · observaciones documentales',arrears_observations:'Atrasos y cobranza observados',
  aportacion:'Aportación',retiro:'Retiro',interes_cobrado:'Interés cobrado',isr_retenido:'ISR retenido',
  transferencia_propia:'Transferencia propia',pendiente:'Origen pendiente',
  capital_externo:'Capital externo confirmado',kind:'Tipo',origin:'Origen',
  cashback_contribution:'Aportación de cashback', own_transfer_in:'Aportación desde cuenta propia',
  own_transfer_out:'Reducción por transferencia propia', isr_withholding:'Retención ISR',
  spei_in:'Entrada SPEI', spei_out:'Salida SPEI', unmapped:'Concepto por clasificar',
  section_missing:'Sección no presente', review_required:'Revisión necesaria',
  arithmetic_included_in_other_charges:'ISR incluido en otros cargos',
  indistinguishable_zero_retention:'Retención cero: base no distinguible',
};
const label = key => Object.hasOwn(labels,key) ? labels[key] : key.replaceAll('_',' ').replace(/^./, c=>c.toUpperCase());
const laneLabel = lane => lane==='debit'?'Cuenta operativa':label(lane);
const value = data => data === null ? 'No publicado / desconocido' : typeof data === 'boolean' ? (data ? 'Sí' : 'No') : Object.hasOwn(labels,data) ? labels[data] : String(data);
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function message(text) { $('notice').textContent = text; }
function connection(ok) {
  $('connection').textContent = ok ? 'Servicio local disponible' : 'Servicio local desconectado';
  $('connection').classList.toggle('offline', !ok);
}
async function api(path, body, raw = false) {
  let response;
  try {
    response = await fetch(path, body === undefined ? {} : {method:'POST',
      headers:{'X-Local-Token':state?.token || '', 'Content-Type':raw?'application/octet-stream':'application/json', ...(raw?{'X-Filename':encodeURIComponent(body.name)}:{})},
      body:raw?body:JSON.stringify(body)});
  } catch (_) { connection(false); throw new Error('El servicio local no responde. Inicia la aplicación y vuelve a abrirla.'); }
  connection(true);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'No se pudo completar la operación');
  return data;
}
async function run(action) {
  if (busy) return;
  busy = true;
  for (const id of ['choose','first-upload','reprocess','review','save-category','prepare','confirm','book-refresh']) $(id).disabled = true;
  try { await action(); } catch (error) { message(error.message); $('notice').scrollIntoView({block:'center'}); }
  finally {
    busy = false;
    for (const id of ['choose','first-upload','reprocess','review','save-category','prepare','book-refresh']) $(id).disabled = false;
    $('confirm').disabled = !financialPlan?.can_confirm;
  }
}
function name(key) { return state.catalog.institutions.find(i=>i.key===key)?.name || 'Sin identificar'; }
function periods(doc) { return doc.periods.length ? doc.periods.map(p=>p.join(' → ')).join(' / ') : 'Por identificar'; }
function renderNavigation() {
  $('total').textContent = state.documents.length;
  $('navigation').replaceChildren();
  for (const category of state.catalog.categories) {
    const group = el('details');
    group.open = state.catalog.institutions.some(i=>i.category===category && state.documents.some(d=>d.institution===i.key));
    group.append(el('summary', category));
    const institutions = state.catalog.institutions.filter(i=>i.category===category);
    for (const institution of institutions) {
      const button = el('button', institution.name, 'nav');
      const count = state.documents.filter(d=>d.institution===institution.key).length;
      button.append(el('span', String(count)));
      button.classList.toggle('selected', selected === institution.key);
      button.onclick = () => {selected=institution.key; current=null; showList();};
      group.append(button);
    }
    if (!institutions.length) group.append(el('p', 'Sin instituciones incorporadas', 'subtext nested'));
    $('navigation').append(group);
  }
  $('all').classList.toggle('selected', selected === null);
}
function showList() {
  financialPassword=null;
  $('overview').hidden = false; $('detail').hidden = true;
  $('book').hidden = true; $('book-nav').classList.remove('selected');
  $('page-title').textContent = selected ? name(selected) : 'Archivo financiero';
  $('crumb').textContent = selected ? name(selected) : 'Archivo financiero';
  renderNavigation(); renderDocuments();
}
function renderDocuments() {
  const query = $('search').value.toLocaleLowerCase('es');
  const all = state.documents.filter(d=>!selected || d.institution===selected);
  const docs = all.filter(d=>(d.filename+' '+name(d.institution)).toLocaleLowerCase('es').includes(query));
  $('stat-docs').textContent = all.length;
  $('stat-pending').textContent = all.filter(d=>d.review!=='reviewed').length;
  $('stat-institutions').textContent = new Set(all.map(d=>d.institution).filter(Boolean)).size;
  $('documents').replaceChildren(); $('empty').hidden = !!docs.length;
  $('empty').querySelector('h2').textContent = query ? 'Sin coincidencias' : 'Empieza con un documento';
  for (const doc of docs) {
    const tr = el('tr'), file = el('td'), button = el('button', doc.filename, 'filename');
    button.onclick = ()=>run(()=>openDocument(doc.id));
    file.append(button, el('span', name(doc.institution), 'subtext'));
    const review=el('td'); review.append(el('span', doc.review==='reviewed'?'Revisado':'Por revisar','badge '+doc.review));
    const action = el('td'), open = el('button','Abrir'); open.onclick=button.onclick; action.append(open);
    tr.append(file,el('td',periods(doc)),review,el('td',String(doc.issues)),action); $('documents').append(tr);
  }
}
async function refresh() { state=await api('/api/state'); renderNavigation(); renderDocuments(); }
const hiddenKeys = new Set(['document_id','account_fingerprint','recipient_fingerprint','relationship_fingerprint','evidence_id','lane','institution','ready_to_import','account','transfer_id','id','view_lanes']);
function renderObject(data, container, level=0) {
  if (data===null || typeof data!=='object') {container.append(el('p',value(data))); return;}
  if (Array.isArray(data)) { renderArray(data,container); return; }
  const scalar=el('dl',undefined,'kv');
  for (const [key,val] of Object.entries(data)) {
    if (hiddenKeys.has(key) || (val!==null && typeof val==='object')) continue;
    scalar.append(el('dt',label(key)),el('dd',value(val)));
  }
  if (scalar.children.length) {const box=el('div',undefined,'panel');box.append(scalar);container.append(box);}
  const preferred = ['summary','aggregate','rows','entries','observations','contracts','positions','fields'];
  const keys=Object.keys(data).filter(k=>!hiddenKeys.has(k) && data[k]!==null && typeof data[k]==='object');
  keys.sort((a,b)=>(preferred.includes(a)?preferred.indexOf(a):99)-(preferred.includes(b)?preferred.indexOf(b):99));
  for (const key of keys) {
    const val=data[key];
    if (Array.isArray(val) && !val.length) continue;
    const details=el('details',undefined,'data-section');
    details.open = ['summary','rows','entries','observations','fields','movements','periods'].includes(key) && level<2;
    details.append(el('summary',label(key)+(Array.isArray(val)?' · '+val.length:'')));
    const content=el('div',undefined,'nested');renderObject(val,content,level+1);details.append(content);container.append(details);
  }
}
function renderArray(data, container) {
  if (!data.length) {container.append(el('p','Sin registros en esta sección.','muted'));return;}
  if (!data.every(v=>v!==null && typeof v==='object' && !Array.isArray(v))) {
    const list=el('ul');for(const item of data)list.append(el('li',typeof item==='object'?JSON.stringify(item):value(item)));container.append(list);return;
  }
  const keys=[...new Set(data.flatMap(Object.keys))].filter(k=>!hiddenKeys.has(k));
  const panel=el('div',undefined,'panel'), scroll=el('div',undefined,'table-scroll'), table=el('table'),head=el('thead'),hr=el('tr'),body=el('tbody');
  keys.forEach(k=>hr.append(el('th',label(k))));head.append(hr);table.append(head,body);scroll.append(table);panel.append(scroll);container.append(panel);
  let page=0;const size=100, pager=el('div',undefined,'pager');panel.append(pager);
  function draw() {
    body.replaceChildren();
    for(const item of data.slice(page*size,(page+1)*size)) {
      const tr=el('tr');for(const key of keys){const v=item[key];const td=el('td');
        if(v && typeof v==='object') {const details=el('details');details.append(el('summary','Ver detalle'));renderObject(v,details,3);td.append(details);}
        else td.textContent=v===undefined?'—':value(v);
        tr.append(td);
      }body.append(tr);
    }
    const prev=el('button','←'),next=el('button','→');prev.disabled=page===0;next.disabled=(page+1)*size>=data.length;
    prev.onclick=()=>{page--;draw();};next.onclick=()=>{page++;draw();};
    pager.replaceChildren(prev,el('span',`${page*size+1}–${Math.min((page+1)*size,data.length)} de ${data.length}`),next);
  }draw();
}
function renderView() {
  for(const view of ['debit','investments']) $('tab-'+view).setAttribute('aria-selected',String(lane===view));
  $('view').replaceChildren();$('alerts').replaceChildren();
  const result=current.result, view=result.views[lane];
  const issues=[...result.issues,...(view?.issues||[])];
  if(issues.length) {
    const alert=el('div',undefined,'alert');alert.append(el('strong','Revisión necesaria'));const ul=el('ul');
    for(const issue of [...new Set(issues)])ul.append(el('li',issue));alert.append(ul);$('alerts').append(alert);
  }
  if(!view) $('view').append(el('p','Completa la identificación para abrir esta vista.','muted'));
  else if(view.status==='not_applicable') $('view').append(el('p','No aplica una cuenta bancaria de débito a esta plataforma.','muted'));
  else if(view.data) {
    const mode=view.mode==='specialized'?'Lector específico':view.mode==='ocr'?'Lectura OCR local':'Lectura documental';
    const text=mode+' · '+(view.reconciled?'Controles del lector sin diferencias detectadas.':'Hay controles pendientes de revisión.');
    $('view').append(el('p',text,'footnote'));renderObject(view.data,$('view'));
  } else $('view').append(el('p','Esta vista no pudo extraerse con el formato disponible. El original está conservado.','muted'));
}
async function openDocument(id) {
  current=await api('/api/documents/'+id);const result=current.result;
  $('overview').hidden=true;$('book').hidden=true;$('detail').hidden=false;$('notice').textContent='';
  financialPlan=null;financialPassword=null;$('financial-plan').hidden=true;$('confirm').hidden=true;
  $('crumb').textContent=name(result.institution);$('detail-institution').textContent=name(result.institution)+(result.portfolio_unit?' · '+result.portfolio_unit:'');
  $('detail-name').textContent=current.filename;
  const item=state.documents.find(d=>d.id===id);$('detail-period').textContent=item?'Período interior: '+periods(item):'';
  $('original').href='/api/documents/'+id+'/original';
  $('resolve').hidden=result.status==='pending_review';
  $('resolve-title').textContent=result.status==='needs_password'?'PDF protegido':'Completar identificación';
  $('resolve-explanation').textContent=result.issues.join(' ');
  $('password-label').hidden=result.status!=='needs_password';$('password').value='';
  $('institution-label').hidden=result.status==='needs_password';
  $('institution').replaceChildren(el('option','Detectar automáticamente'));
  $('institution').firstChild.value='';
  for(const i of state.catalog.institutions){const option=el('option',i.name);option.value=i.key;$('institution').append(option);}
  $('institution').value=result.institution||'';
  $('category').replaceChildren();for(const group of state.catalog.categories){const option=el('option',group);option.value=group;$('category').append(option);}
  $('category').value=state.catalog.institutions.find(i=>i.key===result.institution)?.category||'Por clasificar';
  $('save-category').disabled=!result.institution;
  $('review-state').textContent=current.review==='reviewed'?'Documento marcado como revisado':'Revisión documental pendiente';
  $('review').textContent=current.review==='reviewed'?'Devolver a pendientes':'Marcar como revisado';
  renderView();
  if(['openbank','mifel','bancoppel','didi','fondeadora','plata','supertasas','hey','kapital','doopla','fintual','yotepresto','cetesdirecto','nu'].includes(result.institution) && result.format==='pdf')showPlan(await api('/api/documents/'+id+'/plan'));
}
$('all').onclick=()=>{selected=null;current=null;showList();};
$('back').onclick=()=>{current=null;showList();};
$('search').oninput=renderDocuments;
for(const id of ['choose','first-upload']) $(id).onclick=()=>$('file').click();
$('file').onchange=()=>run(async()=>{
  const file=$('file').files[0];if(!file)return;
  if(file.size>32*1024*1024)throw new Error('El archivo supera 32 MiB.');
  message('Procesando '+file.name+'… Conserva esta ventana abierta.');
  const doc=await api('/api/upload',file,true);
  await refresh();await openDocument(doc.id);
  message(doc.duplicate?'Este archivo ya estaba guardado. Se abrió su registro original.':'Documento guardado y procesado. Revisa sus dos vistas.');
  $('file').value='';
});
for(const view of ['debit','investments']) $('tab-'+view).onclick=()=>{lane=view;renderView();};
$('reprocess').onclick=()=>run(async()=>{
  const password=$('password').value;$('password').value='';
  const doc=await api('/api/documents/'+current.id+'/reprocess',{revision:current.revision,institution:$('institution').value,password});
  await refresh();await openDocument(doc.id);
});
$('review').onclick=()=>run(async()=>{
  const doc=await api('/api/documents/'+current.id+'/review',{revision:current.revision,decision:current.review==='reviewed'?'pending':'reviewed'});
  await refresh();await openDocument(doc.id);
});
$('save-category').onclick=()=>run(async()=>{
  if(!current.result.institution)throw new Error('Primero identifica la institución.');
  await api('/api/group',{institution:current.result.institution,category:$('category').value});await refresh();message('Categoría guardada.');
});
function showPlan(plan) {
  financialPlan=plan;
  const panel=$('financial-plan');panel.hidden=false;panel.replaceChildren();
  panel.append(el('h2',plan.status==='imported'?'Importación confirmada':plan.can_confirm?'Plan listo para confirmar':'Plan pendiente de resolver'));
  for(const issue of plan.issues)panel.append(el('p',issue,'alert'));
  for(const warning of plan.warnings)panel.append(el('p',warning,'footnote'));
  if(plan.password_required) {
    financialPassword=null;
    const group=el('div'), caption=el('label','Contraseña para releer el PDF protegido');
    const input=el('input');input.type='password';input.autocomplete='off';
    input.setAttribute('aria-label','Contraseña para el plan financiero');caption.append(input);
    const unlock=el('button','Desbloquear plan');
    unlock.onclick=()=>run(async()=>{
      financialPassword=input.value;input.value='';
      try {showPlan(await api('/api/documents/'+current.id+'/plan',{revision:plan.revision,password:financialPassword}));}
      catch(error) {financialPassword=null;throw error;}
    });
    group.append(caption,unlock,el('p','Solo se mantiene en memoria durante esta revisión; no se guarda en el plan ni en la base de datos.','footnote'));panel.append(group);
  }
  if(plan.status==='imported')financialPassword=null;
  if(plan.cash_opening_confirmation_required && plan.cash_opening_candidate!==null) {
    const group=el('div'),caption=el('label');const check=el('input');check.type='checkbox';caption.className='opening-review';
    check.setAttribute('aria-label','Apertura de efectivo verificada con mis fuentes');
    caption.append(check,el('span',` Verifiqué con mis fuentes la apertura de efectivo de ${plan.cash_opening_candidate} MXN. Es un candidato aritmético; no está publicado en el estado.`));
    const apply=el('button','Acreditar apertura de efectivo');apply.onclick=()=>run(async()=>{
      if(!check.checked)throw new Error('El documento queda pendiente hasta acreditar la apertura de efectivo.');
      showPlan(await api('/api/documents/'+current.id+'/plan',{revision:plan.revision,
        cash_opening_confirmation:plan.cash_opening_candidate,operation_review:plan.operation_review||null,currency_confirmation:plan.currency_confirmation||null,password:financialPassword}));
    });group.append(caption,apply);panel.append(group);
  }
  if(plan.cash_opening_source)panel.append(el('p',plan.cash_opening_source==='user_review'?
    'Apertura de efectivo acreditada expresamente por el usuario.':'Apertura de efectivo enlazada al cierre contiguo confirmado.','footnote'));
  if(plan.currency_confirmation_required) {
    const group=el('div');const caption=el('label','Moneda revisada del estado');
    const select=el('select');select.setAttribute('aria-label','Moneda revisada del estado');
    for(const [code,text] of [['','Seleccionar'],['MXN','Pesos mexicanos (MXN)'],['unknown','Otra moneda / no puedo confirmarla']]) {
      const option=el('option',text);option.value=code;select.append(option);
    }
    caption.append(select);const apply=el('button','Aplicar revisión de moneda');
    apply.onclick=()=>run(async()=>{
      if(select.value!=='MXN')throw new Error('El documento queda pendiente hasta acreditar una moneda admitida.');
      showPlan(await api('/api/documents/'+current.id+'/plan',{revision:plan.revision,currency_confirmation:'MXN',cash_opening_confirmation:plan.cash_opening_confirmation||null,operation_review:plan.operation_review||null,password:financialPassword}));
    });
    group.append(caption,apply);panel.append(group);
  }
  if(plan.nu_buckets?.length && (plan.nu_review_required||plan.operation_review?.nu) && plan.status!=='imported') {
    const form=el('div',undefined,'panel resolution');form.append(el('h2','Acreditar distribución Nu por producto'));
    form.append(el('p','El estado publica totales globales. Verifica con fuentes adicionales las aperturas y la distribución del interés e ISR: no son saldos individuales por Cajita ni pagos diarios. Usa 0 solo si lo acreditaste.','footnote'));
    const controls={};let aggregateBox;
    for(const bucket of plan.nu_buckets) {
      const box=el('fieldset');box.append(el('legend',bucket.label));
      if(bucket.key==='investments')aggregateBox=box;
      box.append(el('p',`Cierre publicado: ${bucket.final} MXN · Cambio por filas, sin interés/ISR global: ${bucket.changes_without_income} MXN`,'footnote'));
      controls[bucket.key]={};
      for(const [key,title] of [['initial','Saldo inicial acreditado'],['gross_interest','Interés bruto acreditado'],['withholding','ISR retenido acreditado']]) {
        const caption=el('label',title),input=el('input');input.type='text';input.inputMode='decimal';
        input.setAttribute('aria-label',title+' '+bucket.label);
        input.value=plan.operation_review?.nu?.buckets?.[bucket.key]?.[key]??(key==='initial'?bucket.previous_initial??'':'');
        controls[bucket.key][key]=input;caption.append(input);box.append(caption);
      }
      if(bucket.previous_initial!==null)box.append(el('p','Apertura enlazada al cierre contiguo confirmado: '+bucket.previous_initial+' MXN.','footnote'));
      form.append(box);
    }
    const modeLabel=el('label',undefined,'opening-review'),mode=el('input');mode.type='checkbox';mode.checked=!!plan.operation_review?.nu?.cajitas;
    modeLabel.append(mode,el('span','Acreditar cada Cajita por separado, sin registrar también el agregado.'));form.append(modeLabel);
    const individual=el('div'),entries=[];
    individual.append(el('p','Incluye las Cajitas sin movimientos y las históricas cerradas con cero acreditado. Los nombres no se fusionan automáticamente. Los totales se verifican en la aplicación.','footnote'));
    function addCajita(data={}) {
      const box=el('fieldset');box.append(el('legend','Cajita individual'));const fields={};
      for(const [key,title] of [['name','Nombre de Cajita'],['initial','Saldo inicial'],['final','Saldo final'],['gross_interest','Interés bruto'],['withholding','ISR retenido']]) {
        const caption=el('label',title),input=el('input');input.type='text';input.value=data[key]??'';input.setAttribute('aria-label',title+' individual');
        if(key!=='name')input.inputMode='decimal';fields[key]=input;caption.append(input);box.append(caption);
      }
      const entry={box,fields,active:true},remove=el('button','Quitar Cajita');remove.onclick=()=>{entry.active=false;box.remove();};box.append(remove);entries.push(entry);individual.append(box);
    }
    for(const row of plan.operation_review?.nu?.cajitas||plan.nu_cajita_candidates.map(name=>({name})))addCajita(row);
    const add=el('button','Añadir Cajita sin movimientos');add.onclick=()=>addCajita();individual.append(add);form.append(individual);
    function changeMode(){individual.hidden=!mode.checked;if(aggregateBox)aggregateBox.hidden=mode.checked;}
    mode.onchange=changeMode;changeMode();
    const caption=el('label',undefined,'opening-review'),check=el('input');check.type='checkbox';
    caption.append(check,el('span','Verifiqué con mis fuentes las aperturas y esta distribución por producto.'));form.append(caption);
    const apply=el('button','Aplicar revisión Nu');apply.onclick=()=>run(async()=>{
      if(!check.checked)throw new Error('Acredita el desglose Nu con tus fuentes antes de aplicarlo.');
      const buckets={};
      for(const [bucket,fields] of Object.entries(controls)){
        if(bucket==='investments'&&mode.checked)continue;
        buckets[bucket]={};for(const [key,input] of Object.entries(fields)){
          const amount=input.value.trim();if(!/^[0-9]+(?:\.[0-9]+)?$/.test(amount))throw new Error('Completa cada importe Nu con punto decimal y sin signos.');
          buckets[bucket][key]=amount;
        }
      }
      const nu={document_id:current.id,revision:plan.revision,buckets};
      if(mode.checked){
        nu.cajitas=[];for(const entry of entries.filter(e=>e.active)){
          const row={};for(const [key,input] of Object.entries(entry.fields)){
            const val=input.value.trim();if(key!=='name'&&!/^[0-9]+(?:\.[0-9]+)?$/.test(val))throw new Error('Completa los importes de cada Cajita con punto decimal.');
            if(key==='name'&&!val)throw new Error('Identifica cada Cajita.');row[key]=val;
          }nu.cajitas.push(row);
        }
      }
      showPlan(await api('/api/documents/'+current.id+'/plan',{revision:plan.revision,password:financialPassword,
        currency_confirmation:plan.currency_confirmation||null,operation_review:{nu}}));
    });form.append(apply);panel.append(form);
  }
  if(plan.review_rows?.length) {
    const form=el('div',undefined,'panel resolution');form.append(el('h2','Completar desglose de operaciones'));
    form.append(el('p','Verifica cada componente con tus fuentes. No se reparten totales mensuales por porcentaje. Las cancelaciones requieren elegir su original; no se borrarán operaciones.','footnote'));
    const entries=[];
    for(const row of plan.review_rows) {
      const box=el('fieldset');box.append(el('legend',`${row.date} · ${row.description} · ${row.reference} · ${row.total} MXN`));
      const controls={};
      if(row.type==='cancellations') {
        const select=el('select');select.setAttribute('aria-label','Original de cancelación '+row.id);
        const empty=el('option','Seleccionar original');empty.value='';select.append(empty);
        for(const original of row.candidates) {
          const option=el('option',`${original.date} · ${original.reference} · ${original.total} MXN · ${original.document_id.slice(0,10)}`);
          option.value=original.id;select.append(option);
        }
        if(!row.candidates.length)box.append(el('p','No hay un original compatible disponible. Incorpora el documento original o revisa referencia, fecha e importe.','alert'));
        box.append(select);controls.original=select;
        if(row.loans?.length) {
          const caption=el('label','Préstamo cancelado acreditado'),loanSelect=el('select');
          const emptyLoan=el('option','Seleccionar préstamo');emptyLoan.value='';loanSelect.append(emptyLoan);
          for(const loan of row.loans) {const option=el('option',`${loan.id} · ${loan.status}`);option.value=loan.id;loanSelect.append(option);}
          caption.append(loanSelect);box.append(caption);controls.loan_id=loanSelect;
        }
      } else {
        if(row.type==='payments') {
          const caption=el('label','Préstamo acreditado');const select=el('select');
          const empty=el('option','Seleccionar préstamo');empty.value='';select.append(empty);
          for(const loan of row.loans) {const option=el('option',`${loan.id} · ${loan.status}`);option.value=loan.id;select.append(option);}
          select.value=row.loan_id||'';caption.append(select);box.append(caption);controls.loan_id=select;
        }
        for(const field of row.fields) {
          const caption=el('label',label(field)),input=el('input');input.type='text';input.inputMode='decimal';
          input.setAttribute('aria-label',label(field)+' '+row.id);input.value=row.values?.[field]??'';
          caption.append(input);box.append(caption);controls[field]=input;
        }
      }
      entries.push({row,controls});form.append(box);
    }
    const caption=el('label',undefined,'opening-review'),checked=el('input');checked.type='checkbox';
    caption.append(checked,el('span','Verifiqué estos desgloses y originales con mis fuentes.'));form.append(caption);
    const apply=el('button','Aplicar revisión de operaciones');apply.onclick=()=>run(async()=>{
      if(!checked.checked)throw new Error('Verifica los desgloses y originales antes de aplicar.');
      const review=JSON.parse(JSON.stringify(plan.operation_review||{payments:{},retentions:{},cancellations:{}}));
      for(const {row,controls} of entries) {
        review[row.type] ||= {};
        if(row.type==='cancellations') {
          if(!controls.original.value)throw new Error('Selecciona el original de cada cancelación.');
          if(controls.loan_id && !controls.loan_id.value)throw new Error('Acredita el préstamo de la cancelación.');
          review.cancellations[row.id]=controls.loan_id?{original_event_id:controls.original.value,loan_id:controls.loan_id.value}:controls.original.value;
        } else {
          const values={};for(const field of row.fields) {
            if(!/^(?:[0-9]+)(?:\.[0-9]+)?$/.test(controls[field].value.trim()))throw new Error('Indica cada componente con punto decimal; usa 0 solo si lo acreditaste.');
            values[field]=controls[field].value.trim();
          }
          if(controls.loan_id)values.loan_id=controls.loan_id.value;
          review[row.type][row.id]=values;
        }
      }
      showPlan(await api('/api/documents/'+current.id+'/plan',{revision:plan.revision,operation_review:review,
        cash_opening_confirmation:plan.cash_opening_confirmation||null,currency_confirmation:plan.currency_confirmation||null,password:financialPassword}));
    });form.append(apply);panel.append(form);
  }
  if(plan.currency_source==='user_review')panel.append(el('p','Moneda del plan: MXN, indicada expresamente por el usuario.','footnote'));
  const product=row=>row.role==='cajita'?'Cajita · '+row.product_name:row.role==='cajitas_aggregate'?'Cajitas · agregado':row.role==='collateral'?'Crédito con garantía':row.role==='fund_cash'?'Efectivo del portafolio':row.role==='transit'?'Cuenta de paso':row.shared_account?'Cuenta remunerada · ambas vistas':laneLabel(row.lane);
  renderObject({periods:plan.periods.map(p=>({product:product(p),...p})),
    movements:plan.movements.map(m=>({product:product(m),...m,origin:m.origin===null?'No aplica':m.origin})),
    ...(plan.term_snapshots?{term_snapshots:plan.term_snapshots}:{}),
    ...(plan.renewal_proposals?{renewal_proposals:plan.renewal_proposals}:{}),
    ...(plan.investment_summary_observation?{investment_summary_observation:plan.investment_summary_observation}:{}),
    ...(plan.security_initial_positions?{security_initial_positions:plan.security_initial_positions}:{}),
    ...(plan.security_final_positions?{security_final_positions:plan.security_final_positions}:{}),
    ...(plan.security_summary_observation?{security_summary_observation:plan.security_summary_observation}:{}),
    ...(plan.reported_results_observation?{reported_results_observation:plan.reported_results_observation}:{}),
    ...(plan.security_receipts?{security_receipts:plan.security_receipts}:{}),
    ...(plan.stock_positions?{stock_positions:plan.stock_positions}:{}),
    ...(plan.stock_summary_observation?{stock_summary_observation:plan.stock_summary_observation}:{}),
    ...(plan.trade_observations?{trade_observations:plan.trade_observations}:{}),
    ...(plan.memo_observations?{memo_observations:plan.memo_observations}:{}),
    ...(plan.fund_initial_positions?{fund_initial_positions:plan.fund_initial_positions}:{}),
    ...(plan.fund_final_positions?{fund_final_positions:plan.fund_final_positions}:{}),
    ...(plan.fund_summary_observation?{fund_summary_observation:plan.fund_summary_observation}:{}),
    ...(plan.nu_summary_observation?{nu_summary_observation:plan.nu_summary_observation,nu_changes_observation:plan.nu_changes_observation,nu_freeze_observations:plan.nu_freeze_observations}:{}),
    ...(plan.loan_snapshots?{loan_snapshots:plan.loan_snapshots}:{}),
    ...(plan.arrears_observations?{arrears_observations:plan.arrears_observations}:{}),
    ...(plan.platform_summary_observation?{platform_summary_observation:plan.platform_summary_observation}:{}),
    ...(plan.commission_components_observation?{commission_components_observation:plan.commission_components_observation}:{}),
    ...(plan.payment_flow_observation?{payment_flow_observation:plan.payment_flow_observation}:{}),
    ...(plan.history_checks?{history_checks:plan.history_checks}:{}),
    ...(plan.cancellation_links?{cancellation_links:plan.cancellation_links}:{}),
    ...(plan.payment_groups?{payment_groups:plan.payment_groups}:{}),
    ...(plan.investment_transfer_evidence?{investment_transfer_evidence:plan.investment_transfer_evidence}:{})},panel);
  $('confirm').hidden=!plan.can_confirm;$('confirm').disabled=!plan.can_confirm;
}
$('prepare').onclick=()=>run(async()=>showPlan(await api('/api/documents/'+current.id+'/plan',{
  revision:current.revision,currency_confirmation:financialPlan?.currency_confirmation||null,cash_opening_confirmation:financialPlan?.cash_opening_confirmation||null,operation_review:financialPlan?.operation_review||null,password:financialPassword})));
$('confirm').onclick=()=>run(async()=>{
  if(!financialPlan?.can_confirm)return;
  const plan=await api('/api/documents/'+current.id+'/confirm',{revision:financialPlan.revision,plan_hash:financialPlan.plan_hash,
    currency_confirmation:financialPlan.currency_confirmation||null,cash_opening_confirmation:financialPlan.cash_opening_confirmation||null,operation_review:financialPlan.operation_review||null,password:financialPassword});
  showPlan(plan);message(plan.duplicate?'El documento ya estaba importado; no se duplicó.':'Importación confirmada. Los movimientos están guardados en el libro financiero.');
});
function accountTitle(account) {
  return name(account.institution)+(account.portfolio?' · '+account.portfolio:'')+' · '+
    (account.role==='cajita'?'Cajita':account.role==='cajitas_aggregate'?'Cajitas · agregado':account.role==='collateral'?'Crédito con garantía':account.role==='fund_cash'?'Efectivo del portafolio':account.role==='transit'?'Cuenta de paso':account.shared_account?'Cuenta remunerada':laneLabel(account.lane));
}
function renderEvolution(data,target) {
  const section=el('section',undefined,'evolution');section.append(el('h2','Evolución por período'),el('p',data.note,'footnote'));
  if(data.unassigned_movements.length){
    section.append(el('p',`${data.unassigned_movements.length} movimientos vigentes quedan fuera de los períodos confirmados. Revisa sus fechas, cuentas y evidencias.`,'alert'));
    const missing=el('details',undefined,'data-section');missing.append(el('summary','Movimientos fuera de cobertura'));
    for(const m of data.unassigned_movements){
      const box=el('div',undefined,'panel resolution');
      renderObject({effective_date:m.effective_date,kind:m.kind,amount:m.amount,unit:m.unit,reference:m.account},box);
      const source=el('button','Abrir documento de evidencia');source.onclick=()=>run(()=>openDocument(m.evidence.document_id));box.append(source);missing.append(box);
    }
    section.append(missing);
  }
  if(!data.accounts.length){target.append(section);return;}
  const filterLabel=el('label','Cuenta / producto'),filter=el('select'),history=el('div');
  filter.append(new Option('Todas las cuentas',''));
  data.accounts.forEach((a,i)=>filter.append(new Option(accountTitle(a)+' · '+a.unit+' · '+a.account.slice(-8),String(i))));
  filterLabel.append(filter);section.append(filterLabel,history);
  const money=v=>v===null?'Desconocido':v;
  function draw() {
    history.replaceChildren();
    const chosen=data.accounts.filter((a,i)=>filter.value===''||filter.value===String(i));
    const categories=[...new Set(chosen.map(a=>state.catalog.institutions.find(i=>i.key===a.institution)?.category||'Por clasificar'))];
    for(const category of categories){
      history.append(el('h3',category));
      for(const a of chosen.filter(a=>(state.catalog.institutions.find(i=>i.key===a.institution)?.category||'Por clasificar')===category)){
        const panel=el('div',undefined,'panel'),top=el('div',undefined,'panel-top');
        top.append(el('h2',accountTitle(a)),el('span',a.unit+' · '+a.account.slice(-8),'muted'));panel.append(top);
        const scroll=el('div',undefined,'table-scroll'),table=el('table'),head=el('thead'),hr=el('tr'),body=el('tbody');
        const caption=el('caption',accountTitle(a)+' · importes en '+a.unit);table.append(caption);
        for(const title of ['Período','Inicial','Aportaciones','Retiros','Interés','ISR retenido','Interés menos ISR','Cierre','Control / evidencia']){const th=el('th',title);th.scope='col';hr.append(th);}
        head.append(hr);
        for(const row of a.history){
          if(row.gap_before){const gap=el('tr',undefined,'coverage-gap'),td=el('td',`Sin cobertura documental: ${row.gap_before.start} → ${row.gap_before.end}. No se reconstruyen movimientos.`);td.colSpan=9;gap.append(td);body.append(gap);}
          const tr=el('tr');tr.append(el('td',row.start+' → '+row.end));
          for(const key of ['initial','contributions','withdrawals','interest','withholding','interest_net_of_withholding','final'])tr.append(el('td',money(row[key]),'money'));
          const control=el('td'),details=el('details'),toggle=el('summary',row.reconciled?'Cierre conciliado':'Revisar diferencias');
          details.append(toggle);
          if(row.pending_origins)control.append(el('span',`${row.pending_origins} orígenes pendientes`,'subtext'));
          if(row.pending_transfer_ids.length)control.append(el('span',`${row.pending_transfer_ids.length} vínculos sin contraparte`,'subtext'));
          for(const issue of row.issues)details.append(el('p',issue,'alert'));
          renderObject({calculated_final:row.calculated_final,closing_difference:row.closing_difference,cash_change:row.cash_change,
            external_contributions:row.external_contributions,cashback_contributions:row.cashback_contributions,
            own_transfer_in:row.own_transfer_in,own_transfer_out:row.own_transfer_out,
            reinvestment_in:row.reinvestment_in,reinvestment_out:row.reinvestment_out,
            interest_documented:row.interest_documented,withholding_documented:row.withholding_documented,
            dividends:row.dividends,foreign_withholding:row.foreign_withholding,security_proceeds:row.security_proceeds,
            vat_received:row.vat_received,vat_paid:row.vat_paid,fees:row.fees,rewards:row.rewards,
            boundary_difference:row.boundary_difference===null?'Sin cierre contiguo':row.boundary_difference,period_movement_count:row.movements},details);
          const source=el('button','Abrir documento');source.onclick=()=>run(()=>openDocument(row.document_id));details.append(source);
          control.append(details);tr.append(control);body.append(tr);
        }
        table.append(head,body);scroll.append(table);panel.append(scroll);history.append(panel);
      }
    }
  }
  filter.onchange=draw;draw();target.append(section);
}
async function openBook() {
  financialPassword=null;
  const [data,evolution]=await Promise.all([api('/api/book'),api('/api/book/evolution')]);
  selected=null;renderNavigation();
  $('overview').hidden=true;$('detail').hidden=true;$('book').hidden=false;
  $('crumb').textContent='Libro financiero';$('all').classList.remove('selected');$('book-nav').classList.add('selected');
  const target=$('book-content');target.replaceChildren(el('p',data.note,'footnote'));
  target.append(el('p',`${data.documents} documentos confirmados · ${data.movements} movimientos`,'subtitle'));
  renderEvolution(evolution,target);
  if(!data.accounts.length)target.append(el('div','Todavía no hay períodos confirmados. Abre un documento y prepara su importación.','empty'));
  else {const summary=el('details',undefined,'data-section');summary.append(el('summary','Resumen acumulado por cuenta'));target.append(summary);renderArray(data.accounts.map(account=>({
    account_name:accountTitle(account), unit:account.unit,
    through:account.through, closing:account.closing, first_period:account.first_period,
    interest:account.interest, withholding:account.withholding,interest_net_of_withholding:account.interest_net_of_withholding,
    ...(!account.withholding_complete && account.withholding_documented!==null?{withholding_documented:account.withholding_documented}:{}),
    ...(account.institution==='cetesdirecto'?{interest_reported:account.interest_reported,security_proceeds:account.security_proceeds}:{}),
    ...(account.custodian==='alpaca'?{dividends:account.dividends,foreign_withholding:account.foreign_withholding,income_net_foreign_withholding:account.income_net_foreign_withholding}:{}),
    ...(['doopla','yotepresto'].includes(account.institution)?{vat_received:account.vat_received,vat_paid:account.vat_paid,rewards:account.rewards}:{}),
    charges_fees_and_vat:account.charges_fees_and_vat,
    periods:account.periods,pending_origins:account.pending_origins,gaps:account.gaps
  })),summary);}
}
$('book-nav').onclick=()=>run(openBook);
$('book-refresh').onclick=()=>run(openBook);
run(async()=>{await refresh();showList();});
window.addEventListener('focus',()=>{if(!busy)fetch('/api/state').then(r=>connection(r.ok)).catch(()=>connection(false));});
