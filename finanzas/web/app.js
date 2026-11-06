'use strict';
const $ = id => document.getElementById(id);
let state, current, financialPlan, selected = null, lane = 'debit', busy = false;
const labels = {
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
  operation_date:'Fecha de operación', posting_date:'Fecha de cargo', effective_date:'Fecha efectiva',
  date:'Fecha', description:'Descripción', amount:'Importe', deposit:'Abono', withdrawal:'Cargo',
  balance:'Saldo', category:'Tipo de movimiento', currency:'Moneda', exchange_rate:'Tipo de cambio',
  reference:'Referencia', period_start:'Inicio del período', period_end:'Fin del período',
  page:'Página', line:'Línea', outside_period:'Fuera del período', contracts:'Contratos',
  positions:'Posiciones', portfolio:'Cartera', loans:'Préstamos', fields:'Campos extraídos',
  transfer_candidates:'Transferencias candidatas', aggregate:'Resumen global del documento',
  aggregate_isr_basis:'Base observada del ISR global', annex_pages:'Páginas de anexo excluidas',
  issues:'Alertas', detail_issues:'Alertas de detalle', cash_issues:'Alertas de efectivo',
  contract_issues:'Alertas de contratos', document_preview:'Lectura documental', evidence:'Evidencia OCR',
  confidence:'Confianza OCR', text:'Texto', unit:'Unidad', value:'Valor', raw_value:'Valor original',
  status:'Estado', periods:'Períodos detectados', account_fingerprint:'Huella de cuenta',
  document_id:'Huella documental', relationship_fingerprint:'Huella de relación', id:'Identificador',
  evidence_id:'Identificador de evidencia', name:'Campo', operation_kind:'Tipo de operación',
  timezone:'Zona horaria', account:'Cuenta', source_lines:'Líneas de origen',
  principal:'Capital', principal_paid:'Capital pagado', interest_paid:'Interés pagado',
  maturity:'Vencimiento', rate:'Tasa', start:'Inicio', end:'Fin', quantity:'Cantidad',
  debit:'Cuenta operativa', investments:'Inversiones', reconciled:'Conciliación',
  candidate_requires_review:'Candidato pendiente de revisión', interest_received:'Interés cobrado',
  first_period:'Primer período importado', through:'Cierre al', closing:'Saldo de cierre documental',
  pending_origins:'Orígenes pendientes', gaps:'Huecos entre períodos importados',
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
const hiddenKeys = new Set(['document_id','account_fingerprint','recipient_fingerprint','relationship_fingerprint','evidence_id','lane','institution','ready_to_import','account','transfer_id','id']);
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
  financialPlan=null;$('financial-plan').hidden=true;$('confirm').hidden=true;
  $('crumb').textContent=name(result.institution);$('detail-institution').textContent=name(result.institution);
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
  if(result.institution==='openbank' && result.format==='pdf')showPlan(await api('/api/documents/'+id+'/plan'));
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
  renderObject({periods:plan.periods.map(p=>({product:label(p.lane),...p})),
    movements:plan.movements.map(m=>({product:label(m.lane),...m}))},panel);
  $('confirm').hidden=!plan.can_confirm;$('confirm').disabled=!plan.can_confirm;
}
$('prepare').onclick=()=>run(async()=>showPlan(await api('/api/documents/'+current.id+'/plan')));
$('confirm').onclick=()=>run(async()=>{
  if(!financialPlan?.can_confirm)return;
  const plan=await api('/api/documents/'+current.id+'/confirm',{revision:financialPlan.revision,plan_hash:financialPlan.plan_hash});
  showPlan(plan);message(plan.duplicate?'El documento ya estaba importado; no se duplicó.':'Importación confirmada. Los movimientos están guardados en el libro financiero.');
});
async function openBook() {
  const data=await api('/api/book');
  selected=null;renderNavigation();
  $('overview').hidden=true;$('detail').hidden=true;$('book').hidden=false;
  $('crumb').textContent='Libro financiero';$('all').classList.remove('selected');$('book-nav').classList.add('selected');
  const target=$('book-content');target.replaceChildren(el('p',data.note,'footnote'));
  target.append(el('p',`${data.documents} documentos confirmados · ${data.movements} movimientos`,'subtitle'));
  if(!data.accounts.length)target.append(el('div','Todavía no hay períodos confirmados. Abre un documento y prepara su importación.','empty'));
  else renderArray(data.accounts.map(account=>({
    account_name:'Openbank · '+label(account.lane), unit:account.unit,
    through:account.through, closing:account.closing, first_period:account.first_period,
    interest:account.interest, withholding:account.withholding,
    periods:account.periods,pending_origins:account.pending_origins,gaps:account.gaps
  })),target);
}
$('book-nav').onclick=()=>run(openBook);
$('book-refresh').onclick=()=>run(openBook);
run(async()=>{await refresh();showList();});
window.addEventListener('focus',()=>{if(!busy)fetch('/api/state').then(r=>connection(r.ok)).catch(()=>connection(false));});
