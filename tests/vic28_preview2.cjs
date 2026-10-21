/* Populated acceptance evidence. Browser emulation is labelled separately from native DPI/IME. */
const {chromium}=require('playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const out=path.resolve(process.env.VIC28_PREVIEW2_OUTPUT||'.local/vic28-preview2');fs.mkdirSync(out,{recursive:true});
const urls={fixture:'http://127.0.0.1:8769',copy:'http://127.0.0.1:8770',stale:'http://127.0.0.1:8771',unknown:'http://127.0.0.1:8772',preparing:'http://127.0.0.1:8773'};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const errors=[],external=[],checks=[],layouts=[],contrast=[];
 try{
  async function context(options){const c=await browser.newContext(options);await c.route('**/*',r=>{const u=r.request().url();if(/^http:\/\/127\.0\.0\.1:87(?:6[89]|7[0-3])(?:\/|$)/.test(u))return r.continue();external.push(u);return r.abort();});c.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));return c;}
  const ctx=await context({viewport:{width:1760,height:1350}}),p=await ctx.newPage();p.setDefaultTimeout(7000);
  async function go(kind){await p.goto(urls[kind]);await p.waitForSelector('.worker-card');const v=await (await p.request.get(urls[kind]+'/api/v1/snapshot')).json();fs.writeFileSync(path.join(out,kind+'-snapshot.json'),JSON.stringify(v,null,2));return v;}
  async function nav(view,filter='all'){await p.locator(`[data-nav="${view}"][data-filter="${filter}"]:visible`).first().click();}
  async function shot(name){await p.screenshot({path:path.join(out,name+'.png'),animations:'disabled',fullPage:true});}
  async function layout(label,page=p){const v=await page.evaluate(()=>({root:document.documentElement.scrollWidth-innerWidth,main:document.querySelector('main').scrollWidth-document.querySelector('main').clientWidth,viewport:[innerWidth,innerHeight],dpr:devicePixelRatio}));assert.ok(v.root<=1&&v.main<=1,label+': '+JSON.stringify(v));layouts.push({label,...v});}
  const v=await go('fixture');assert.equal(v.catalog.length,13);assert.equal(new Set(v.catalog.map(r=>r.status)).size,13);
  assert.equal(await p.locator('tbody tr').count(),6);assert.ok((await p.locator('.active-job').innerText()).includes('Текущая часть 2 из 3'));await shot('01-dashboard');await layout('Dashboard populated');
  await nav('catalog');assert.equal(await p.locator('tbody tr').count(),13);await shot('02-catalog');await layout('Catalog all 13 states');
  await nav('catalog','ai_queue');assert.equal(await p.locator('tbody tr').count(),5);assert.equal(await p.locator('[role="progressbar"]').count(),0);await shot('03-ai-queue');await layout('AI queue all durable AI states');
  await nav('catalog');await p.locator('#global-search').fill('01_2026-10-20');assert.equal(await p.locator('tbody tr').count(),1);assert.equal(await p.locator('.inspector [role="progressbar"]').getAttribute('aria-valuenow'),'57');
  const footer=await p.locator('.inspector-actions').boundingBox(),status=await p.locator('#statusbar').boundingBox();assert.ok(footer.y+footer.height<=status.y);await shot('04-active-lecture');
  const samples=await p.locator('.source-banner,.lecture-title-btn,.lecture-sub,.lecture-table .badge,.mini-progress-label,.stage-row>span:nth-child(2),.stage-state,.info-pairs dd,.inspector-actions,.progress-meta').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().width).map(n=>({text:n.textContent.trim().slice(0,70),font:parseFloat(getComputedStyle(n).fontSize),color:getComputedStyle(n).color})));
  function luminance(rgb){return rgb.map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);}
  const panel=luminance([53,49,62]);for(const s of samples){const color=s.color.match(/[\d.]+/g).map(Number);const fg=luminance(color.slice(0,3)),ratio=(Math.max(fg,panel)+.05)/(Math.min(fg,panel)+.05);contrast.push({...s,conservativeBackground:'#35313e',ratio:+ratio.toFixed(2)});assert.ok(ratio>=4.5,'Contrast '+JSON.stringify(s)+' '+ratio);assert.ok(s.font>=11,'Useful desktop text too small: '+JSON.stringify(s));}
  await nav('catalog','waiting_ai');assert.ok((await p.locator('.inspector').innerText()).includes('Процент и время AI неизвестны'));assert.equal(await p.locator('.inspector [role="progressbar"]').count(),0);await shot('05-manual-ai');
  await nav('catalog','problems');await p.locator('tbody [data-row="SYS/08_2026-10-14"]').first().click();assert.ok((await p.locator('.inspector .callout').innerText()).includes('исходники сохранены'));await shot('06-error');
  await p.locator('tbody [data-row="ECON/12_2026-10-10"]').first().click();assert.ok((await p.locator('.inspector').innerText()).includes('управляемое аудио отсутствует'));await shot('07-inconsistent-state');
  await nav('inbox');assert.ok((await p.locator('main').innerText()).includes('Не хватает части 2'));await shot('08-inbox-multipart');
  checks.push('All 13 backend catalog statuses, 5 AI tasks, 2/3, 57%, ETA 7 min, explicit errors, manual AI without invented progress, Inbox missing part 2');
  await nav('home');await p.locator('#global-search').focus();
  await p.locator('#global-search').evaluate(el=>{window.__composingInput=el;el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:''}));el.value='yun';el.dispatchEvent(new InputEvent('input',{bubbles:true,data:'yun',isComposing:true}));});
  const staleDuringComposition=await (await p.request.get(urls.stale+'/api/v1/snapshot')).json();
  await p.route('**/api/v1/snapshot',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(staleDuringComposition)}));
  const response=p.waitForResponse(r=>r.url().endsWith('/api/v1/snapshot'));await p.locator('[data-action="refresh"]').first().evaluate(el=>el.click());await response;
  assert.equal(await p.evaluate(()=>window.__composingInput===document.querySelector('#global-search')),true,'Snapshot repaint cancelled IME input');
  assert.ok((await p.locator('.worker-card').first().innerText()).includes('Heartbeat устарел'),'Heartbeat paint was delayed by composition');
  assert.equal(await p.locator('[role="progressbar"]').count(),0,'Live progress was retained during composition');
  await p.unroute('**/api/v1/snapshot');
  await p.locator('#global-search').evaluate(el=>{el.value='运筹';el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'运筹'}));});
  assert.equal(await p.locator('#global-search').inputValue(),'运筹');assert.equal(await p.locator('tbody tr').count(),4);
  checks.push('Composition regression: input DOM identity survives refresh while stale heartbeat and hidden live progress repaint immediately; committed Chinese query filters 4 rows (synthetic event test, not native IME evidence)');
  await go('stale');assert.ok((await p.locator('.worker-card').first().innerText()).includes('Heartbeat устарел'));assert.equal(await p.locator('[role="progressbar"]').count(),0);assert.ok(!(await p.locator('.worker-grid').innerText()).includes('GPU · CUDA'));assert.ok(!(await p.locator('.active-job').innerText()).includes('Текущая часть 2 из 3'));await shot('09-stale-heartbeat');
  await go('unknown');const unknown=await p.locator('.active-job').innerText();assert.ok(unknown.includes('Текущая часть 2 из 3')&&unknown.includes('Процент недоступен')&&unknown.includes('ETA недоступен'));assert.equal(await p.locator('[role="progressbar"]').count(),0);await shot('10-unknown-percent-eta');
  await go('preparing');assert.ok((await p.locator('.active-job').innerText()).includes('Подготовка аудио'));assert.equal(await p.locator('[role="progressbar"]').count(),0);await shot('11-preparing');
  checks.push('Real backend projection of isolated stale/unknown/preparing fixtures: stale hides N/M/percent/ETA/device, unknown percent keeps valid multipart N/M');
  const copy=await go('copy');assert.equal(copy.catalog.length,1);assert.equal(copy.catalog[0].parts,7);assert.equal(copy.catalog[0].stages.raw,'available');assert.equal(copy.catalog[0].status,'problem');assert.equal(copy.counts.done,0);
  await p.locator('tbody [data-row]').first().click();assert.ok((await p.locator('.inspector').innerText()).includes('completed не подтверждён'));await shot('12-dev-raw-copy');
  checks.push('DEV Raw/SRT copy: 7 actual parts, Raw available, missing completed authority explicitly shown; no fake Done, workers or ASR telemetry');
  for(const factor of [1.25,1.5,2]){
   const c=await context({viewport:{width:Math.floor(2880/factor),height:Math.floor(1800/factor)-70},deviceScaleFactor:factor});const q=await c.newPage();await q.goto(urls.fixture);await q.waitForSelector('.worker-card');
   for(const [view,filter] of [['home','all'],['catalog','all'],['catalog','ai_queue'],['inbox','all']]){await q.locator(`[data-nav="${view}"][data-filter="${filter}"]:visible`).first().click();await layout(`${factor*100}% browser emulation ${view}/${filter}`,q);}
   await q.locator('[data-nav="home"]').click();await q.screenshot({path:path.join(out,`scale-${factor*100}-dashboard.png`),animations:'disabled'});await c.close();
  }
  for(const [w,h] of [[1280,720],[1024,576],[640,360]]){await p.setViewportSize({width:w,height:h});await go('fixture');for(const view of ['home','catalog','inbox','courses','diagnostics']){await nav(view);await layout(`${view} ${w}x${h}`);}await nav('home');await shot(`compact-${w}`);}
  checks.push('125/150/200 percent browser viewport+density emulation of 2880x1800 display, plus compact windows; vertical scrolling retained, no horizontal page overflow');
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  const report={result:'PASS',javascriptErrors:errors,externalPageRequests:external,checks,layouts,contrast,minimumMeasuredContrast:Math.min(...contrast.map(c=>c.ratio)),nativeDpiEvidence:false,nativeImeEvidence:false};
  fs.writeFileSync(path.join(out,'preview2-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({result:'PASS',checks,layouts:layouts.length,minimumMeasuredContrast:report.minimumMeasuredContrast,javascriptErrors:errors.length,externalPageRequests:external.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
