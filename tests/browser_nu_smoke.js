'use strict';
// Chrome/Node del ejecutor; CDP y WebSocket nativos, sin paquetes adicionales.
const {spawn,spawnSync}=require('node:child_process');
const fs=require('node:fs');const os=require('node:os');const path=require('node:path');
const assert=require('node:assert/strict');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const timeout=(promise,ms=20000)=>Promise.race([promise,new Promise((_,reject)=>setTimeout(()=>reject(Error('Tiempo de espera agotado')),ms).unref())]);
(async()=>{
  assert.equal(typeof WebSocket,'function','La prueba requiere Node con WebSocket nativo');
  const chrome=process.env.CHROME_BIN||['google-chrome','google-chrome-stable','chromium','chromium-browser'].find(bin=>spawnSync('which',[bin]).status===0);
  assert.ok(chrome,'Chrome no está instalado en este ejecutor');
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),'nu-browser-'));let app,browser,ws;
  try {
    app=spawn(process.env.FINANZAS_TEST_PYTHON||'python3',['-m','tests.browser_nu_fixture'],{stdio:['ignore','pipe','pipe']});
    const url=await timeout(new Promise((resolve,reject)=>{let text='';app.stdout.on('data',chunk=>{text+=chunk;const m=text.match(/NU_TEST_URL=(http:\/\/127\.0\.0\.1:\d+)/);if(m)resolve(m[1]);});app.on('error',reject);app.on('exit',()=>reject(Error('Servidor de prueba detenido')));}));
    browser=spawn(chrome,['--headless=new','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:['ignore','ignore','pipe']});
    const endpoint=await timeout(new Promise((resolve,reject)=>{let text='';browser.stderr.on('data',chunk=>{text+=chunk;const m=text.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(m)resolve(m[1]);});browser.on('error',reject);browser.on('exit',()=>reject(Error('Chrome de prueba detenido')));}));
    ws=new WebSocket(endpoint);await timeout(new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});}));
    let seq=0;const pending=new Map(),errors=[];
    ws.addEventListener('message',event=>{const msg=JSON.parse(event.data);if(msg.id){const task=pending.get(msg.id);pending.delete(msg.id);if(task)(msg.error?task.reject(Error(msg.error.message)):task.resolve(msg.result));}else if(msg.method==='Runtime.exceptionThrown')errors.push(msg.params.exceptionDetails.text);});
    const send=(method,params={},sessionId)=>timeout(new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));}));
    const {targetId}=await send('Target.createTarget',{url:'about:blank'}),{sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
    const cmd=(method,params={})=>send(method,params,sessionId);
    await cmd('Runtime.enable');await cmd('Page.enable');await cmd('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    const evaluate=async expression=>{const r=await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
    const until=async expression=>{for(let i=0;i<100;i++){if(await evaluate(expression))return;await delay(100);}throw Error('No se cumplió condición: '+expression);};
    await cmd('Page.navigate',{url});await until('document.querySelector("#documents .filename")!==null');
    await evaluate('document.querySelector("#documents .filename").click()');await until('typeof financialPlan!=="undefined" && financialPlan?.nu_buckets?.length===2');
    await evaluate(`(()=>{const label=[...document.querySelectorAll('label')].find(l=>l.textContent.includes('Acreditar cada Cajita por separado'));const input=label.querySelector('input');input.checked=true;input.dispatchEvent(new Event('change'));const form=label.parentElement;const first=form.querySelector('fieldset');for(const [key,val] of [['Saldo inicial acreditado','27'],['Interés bruto acreditado','0'],['ISR retenido acreditado','0']])first.querySelector('input[aria-label^="'+key+'"]').value=val;const set=(key,val,index=0)=>document.querySelectorAll('[aria-label="'+key+' individual"]')[index].value=val;set('Saldo inicial','53');set('Saldo final','105');set('Interés bruto','2.10');set('ISR retenido','0.10');[...document.querySelectorAll('button')].find(b=>b.textContent==='Añadir Cajita sin movimientos').click();set('Nombre de Cajita','Sin movimientos',1);set('Saldo inicial','20',1);set('Saldo final','20',1);set('Interés bruto','0',1);set('ISR retenido','0',1);[...form.querySelectorAll('label')].find(l=>l.textContent.includes('Verifiqué con mis fuentes las aperturas')).querySelector('input').checked=true;[...form.querySelectorAll('button')].find(b=>b.textContent==='Aplicar revisión Nu').click();})()`);
    await until('financialPlan?.can_confirm===true');assert.equal(await evaluate('financialPlan.nu_individual_mode'),true);
    await evaluate('document.querySelector("#confirm").click()');await until('financialPlan?.status==="imported"');
    await evaluate('document.querySelector("#book-nav").click()');await until('document.querySelectorAll(".evolution table").length===3');
    assert.equal(await evaluate('document.querySelector(".evolution").textContent.includes("sin movimientos")'),true);
    const accounts=await evaluate(`fetch('/api/book/evolution').then(r=>r.json()).then(d=>d.accounts)`);
    assert.equal(accounts.length,3);assert.equal(accounts.filter(a=>a.role==='cajita').length,2);
    assert.ok(accounts.every(a=>a.history.every(r=>r.reconciled)));
    assert.ok(!accounts.some(a=>a.role==='cajitas_aggregate'));
    fs.mkdirSync('artifacts',{recursive:true});
    fs.writeFileSync('artifacts/nu-desktop.png',Buffer.from((await cmd('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
    await cmd('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await delay(250);
    assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'La página móvil desborda el ancho; las tablas deben desplazar internamente');
    fs.writeFileSync('artifacts/nu-mobile.png',Buffer.from((await cmd('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
    assert.deepEqual(errors,[]);console.log('Nu navegador: revisión individual, confirmación, evolución, monedas y móvil aprobados.');
  } finally {if(ws)ws.close();if(browser){const closed=new Promise(r=>browser.once('exit',r));browser.kill();await Promise.race([closed,delay(2000)]);}if(app)app.kill();fs.rmSync(profile,{recursive:true,force:true});}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
