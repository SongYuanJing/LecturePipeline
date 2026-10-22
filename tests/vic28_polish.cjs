/* UI-only gate: real frontend + existing DTO fixtures, never a second catalog. */
const {chromium}=require('playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const out=path.resolve(process.env.VIC28_POLISH_OUTPUT||'.local/user-facing-polish/evidence/browser');
const urls={dev:process.env.VIC28_DEV_URL||'http://127.0.0.1:8898',fixture:process.env.VIC28_FIXTURE_URL||'http://127.0.0.1:8899',stale:process.env.VIC28_STALE_URL||'http://127.0.0.1:8901',unknown:process.env.VIC28_UNKNOWN_URL||'http://127.0.0.1:8902',preparing:process.env.VIC28_PREPARING_URL||'http://127.0.0.1:8903'};
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const failures=[],checks=[],errors=[],external=[],layouts=[],fonts=[];
 function check(name,pass,detail){checks.push({name,pass,detail});if(!pass)failures.push({name,detail});}
 try{
  const context=await browser.newContext({viewport:{width:1440,height:900}}),p=await context.newPage();
  p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(/^https?:/.test(r.url())&&!Object.values(urls).some(u=>r.url().startsWith(u+'/')))external.push(r.url());});
  const fixture=await (await p.request.get(urls.fixture+'/api/v1/snapshot')).json();
  async function go(url){await p.goto(url);await p.waitForSelector('.worker-card');}
  async function nav(view,filter='all'){await p.locator(`[data-nav="${view}"][data-filter="${filter}"]:visible`).first().click();}
  async function repaint(){await p.evaluate(()=>new Promise(resolve=>{const sidebar=document.querySelector('#sidebar'),observer=new MutationObserver(()=>{observer.disconnect();requestAnimationFrame(()=>resolve());});observer.observe(sidebar,{childList:true});document.querySelector('[data-action="refresh"]').click();}));}
  async function layout(label,page=p){const value=await page.evaluate(()=>({viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,root:document.documentElement.scrollWidth-innerWidth,main:document.querySelector('main').scrollWidth-document.querySelector('main').clientWidth,sidebar:document.querySelector('#sidebar').scrollWidth-document.querySelector('#sidebar').clientWidth}));layouts.push({label,...value});check('No horizontal clipping: '+label,value.root<=1&&value.main<=1&&value.sidebar<=1,value);}
  await go(urls.dev);
  const actual=await (await p.request.get(urls.dev+'/api/v1/snapshot')).json();
  check('DEV installation stays explicitly identified',/изолированн.*тестов|тестов.*установ/i.test(await p.locator('body').innerText()),actual.source.kind);
  check('Public shell has no Work S / ticket labels',!/(VIC-28|Work S|read-only projection)/i.test(await p.locator('body').innerText()));
  if(actual.workspace.name===actual.workspace.id)check('Technical workspace ID stays out of the public shell',!(await p.locator('#sidebar,#topbar').allTextContents()).join(' ').includes(actual.workspace.id),actual.workspace.id);
  await go(urls.fixture);await p.setViewportSize({width:1280,height:480});
  const before=await p.locator('#sidebar').evaluate(el=>{el.scrollTop=el.scrollHeight;return el.scrollTop;});
  await repaint();const after=await p.locator('#sidebar').evaluate(el=>el.scrollTop);
  check('Sidebar scroll survives an actual snapshot refresh',before>0&&Math.abs(before-after)<=1,{before,after});
  await p.screenshot({path:path.join(out,'sidebar-refresh.png'),animations:'disabled'});
  if(process.env.VIC28_POLISH_SCROLL_ONLY==='1'){
   fs.writeFileSync(path.join(out,'polish-verification.json'),JSON.stringify({checks,failures},null,2));
   assert.equal(failures.length,0,JSON.stringify(failures));return;
  }
  const long=structuredClone(fixture);
  for(const course of long.courses)course.name=Array(3).fill(course.name).join(' · ');
  for(const row of long.catalog)row.course_display_name=long.courses.find(c=>c.id===row.course_id).name;
  // Only repeat current fixture display names; identities, stages, counts and progress stay unchanged.
  await p.route('**/api/v1/snapshot',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(long)}));
  await go(urls.fixture);await p.setViewportSize({width:1440,height:900});await nav('catalog');
  const title=await p.locator('.lecture-title-btn').first().evaluate(el=>({text:el.textContent,whiteSpace:getComputedStyle(el).whiteSpace,scrollWidth:el.scrollWidth,width:el.clientWidth}));
  check('Long course names wrap instead of disappearing behind ellipsis',title.whiteSpace!=='nowrap'&&title.scrollWidth<=title.width+1,title);
  await layout('long Chinese and Cyrillic course names');
  await p.screenshot({path:path.join(out,'long-names-catalog.png'),animations:'disabled'});
  await nav('courses');await layout('long course cards');await p.screenshot({path:path.join(out,'long-names-courses.png'),animations:'disabled'});
  await nav('diagnostics');await layout('diagnostics paths');
  const audit=await p.locator('.diagnostics').innerText();check('Diagnostic evidence remains available',audit.includes(fixture.read_audit.files[0]));
  await p.unroute('**/api/v1/snapshot');
  for(const factor of [1.25,1.5,2])for(const display of [[1920,1080],[2880,1800]]){
   const c=await browser.newContext({viewport:{width:Math.floor(display[0]/factor),height:Math.floor(display[1]/factor)-64},deviceScaleFactor:factor}),q=await c.newPage();
   q.on('pageerror',e=>errors.push(e.message));await q.goto(urls.fixture);await q.waitForSelector('.worker-card');
   for(const [view,filter] of [['home','all'],['catalog','all'],['catalog','ai_queue'],['courses','all'],['inbox','all'],['diagnostics','all']]){
    await q.locator(`[data-nav="${view}"][data-filter="${filter}"]:visible`).first().click();
    const label=`${display.join('x')} / ${factor*100}% browser / ${view}-${filter}`;await layout(label,q);
    const sample=await q.locator('.lecture-sub,.worker-card small,.stage-state,.diagnostic-pairs,.source-banner,.nav-item .label,.course-card-stats,.course-card-stats span,.inbox-reason,.inbox-item .badge').evaluateAll(els=>els.filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).map(e=>({text:e.textContent.slice(0,60),font:parseFloat(getComputedStyle(e).fontSize)})));
    fonts.push({label,minimum:Math.min(...sample.map(s=>s.font))});check('Useful secondary text is at least 12 CSS px: '+label,sample.every(s=>s.font>=12),sample.filter(s=>s.font<12));
    check('DEV/demo source remains visible: '+label,await q.locator('.source-pill').evaluate(el=>el.getBoundingClientRect().width>30&&!!el.innerText.trim()));
    if(view==='catalog'&&filter==='all'){
     await q.locator('.inspector-content').evaluate(el=>el.scrollTop=el.scrollHeight);
     check('Last lecture detail remains reachable: '+label,await q.locator('.inspector-content').evaluate(el=>el.scrollHeight<=el.clientHeight+el.scrollTop+1));
    }
    if(display[0]===2880&&['home','catalog','courses','inbox','diagnostics'].includes(view)&&filter==='all')await q.screenshot({path:path.join(out,`${factor*100}-${view}.png`),animations:'disabled'});
   }
   await c.close();
  }
  for(const kind of ['stale','unknown','preparing']){
   await go(urls[kind]);const text=await p.locator('.active-job').innerText();
   check(kind+' does not invent percentages',await p.locator('[role="progressbar"]').count()===0);
   if(kind==='stale')check('Stale observations hide live multipart and device',!text.includes('Текущая часть 2 из 3')&&!(await p.locator('.worker-grid').innerText()).includes('GPU · CUDA'));
   if(kind==='unknown')check('Unknown percent keeps verified multipart',text.includes('Текущая часть 2 из 3'));
  }
  await go(urls.fixture);await nav('catalog','problems');
  for(const row of fixture.catalog.filter(r=>['problem','review','error'].includes(r.status))){await p.locator(`tbody [data-row="${row.id}"]`).first().click();for(const reason of row.reasons||[])check('Backend reason preserved: '+row.id,(await p.locator('.inspector').innerText()).includes(reason));}
  await nav('catalog','waiting_ai');check('Manual AI has no invented progress',await p.locator('.inspector [role="progressbar"]').count()===0);
  await go(urls.dev);await nav('diagnostics');check('Raw technical workspace ID is retained in diagnostics',(await p.locator('main').innerText()).includes(actual.workspace.id));
  check('No JavaScript errors',errors.length===0,errors);check('No external page requests',external.length===0,external);
  const report={result:failures.length?'FAIL':'PASS',checks,failures,layouts,fonts,javascriptErrors:errors,externalRequests:external,browserScaleFactors:[1.25,1.5,2],nativeDpiEvidence:false,longNameFixture:'Repeated existing DTO fixture course display names; no new identity, state or storage fields'};
  fs.writeFileSync(path.join(out,'polish-verification.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({result:report.result,checks:checks.length,failures,layouts:layouts.length,javascriptErrors:errors.length,externalRequests:external.length}));
  assert.equal(failures.length,0,JSON.stringify(failures));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
