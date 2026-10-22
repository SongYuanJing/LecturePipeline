/* Run against the two local launchers. Playwright is QA-only, not a runtime dependency. */
const {chromium}=require('playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const out=path.resolve(process.env.VIC28_QA_OUTPUT||'.local/vic28-qa');fs.mkdirSync(out,{recursive:true});
const dev=process.env.VIC28_DEV_URL||'http://127.0.0.1:8768',fixture=process.env.VIC28_FIXTURE_URL||'http://127.0.0.1:8769';
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const errors=[],requests=[],checks=[],layouts=[];
  try{
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    const page=await context.newPage();page.setDefaultTimeout(6000);
    page.on('pageerror',e=>errors.push(e.message));page.on('request',req=>{if(/^https?:/.test(req.url())&&!req.url().startsWith(dev)&&!req.url().startsWith(fixture))requests.push(req.url());});
    async function goto(url){await page.goto(url);await page.waitForSelector('.worker-card');}
    async function nav(view,filter='all'){await page.locator(`[data-nav="${view}"][data-filter="${filter}"]:visible`).first().click();}
    async function action(name){await page.locator(`[data-action="${name}"]:visible`).first().click();}
    async function layout(label){const result=await page.evaluate(()=>({root:document.documentElement.scrollWidth-innerWidth,main:document.querySelector('main').scrollWidth-document.querySelector('main').clientWidth}));assert.ok(result.root<=1&&result.main<=1,label+' '+JSON.stringify(result));layouts.push(label);}
    async function partialSnapshot(){
      const original=await (await page.request.get(dev+'/api/v1/snapshot')).json();
      const partial={...original,counts:null,catalog:[],errors:['Проверка UI: файл состояния не читается']};
      await page.route('**/api/v1/snapshot',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(partial)}));
      await goto(dev);assert.ok((await page.locator('.read-warning').innerText()).includes('Данные каталога неполны'));
      assert.ok(!(await page.locator('main').innerText()).includes('Лекций пока нет'));
      assert.ok(!(await page.locator('main').innerText()).includes('В DEV ещё нет лекций'));
      assert.equal(await page.locator('.metric-number').first().innerText(),'—');
      await layout('partial snapshot 1440x1000');
      await page.screenshot({path:path.join(out,'partial-snapshot.png'),animations:'disabled'});
      await page.unroute('**/api/v1/snapshot');
      const result={result:'PASS',case:'Partial authority read is not an empty catalog',javascriptErrors:errors,externalRequests:requests.length,realDevFilesChanged:false};
      fs.writeFileSync(path.join(out,'partial-verification.json'),JSON.stringify(result,null,2));
    }
    if(process.env.VIC28_FOCUS_PARTIAL==='1'){await partialSnapshot();assert.deepEqual(errors,[]);console.log(fs.readFileSync(path.join(out,'partial-verification.json'),'utf8'));return;}
    await goto(dev);const actual=await (await page.request.get(dev+'/api/v1/snapshot')).json();
    assert.equal(actual.source.kind,'dev');assert.equal(actual.capabilities.read_only,true);
    assert.ok((await page.locator('.source-banner').innerText()).includes('Изолированная тестовая установка'));
    if(actual.counts.total===0){assert.ok((await page.locator('main').innerText()).includes('Лекций пока нет'));assert.equal(await page.locator('[role="progressbar"]').count(),0);}
    await page.screenshot({path:path.join(out,'dashboard-real-dev.png'),animations:'disabled'});
    fs.writeFileSync(path.join(out,'real-dev-snapshot.json'),JSON.stringify(actual,null,2));
    checks.push('Real DEV source, actual counts, missing data represented explicitly');
    await partialSnapshot();
    await goto(fixture);const sample=await (await page.request.get(fixture+'/api/v1/snapshot')).json();
    assert.equal(sample.source.kind,'fixture');assert.equal(sample.source.frozen,true);
    assert.equal(await page.locator('.active-job [role="progressbar"]').getAttribute('aria-valuenow'),'57');
    assert.ok((await page.locator('.active-job').innerText()).includes('Текущая часть 2 из 3'));
    await page.screenshot({path:path.join(out,'dashboard-synthetic.png'),animations:'disabled'});
    await nav('catalog');assert.equal(await page.locator('tbody tr').count(),13);
    const footer=await page.locator('.inspector-actions').boundingBox(),bar=await page.locator('#statusbar').boundingBox();assert.ok(footer.y+footer.height<=bar.y,'Inspector footer clipped');
    await page.keyboard.press('Control+k');await page.locator('#global-search').fill('系统');assert.equal(await page.locator('tbody tr').count(),4);
    await page.locator('#global-search').fill('');await nav('catalog','waiting_ai');assert.equal(await page.locator('tbody tr').count(),1);
    assert.equal(await page.locator('.inspector [role="progressbar"]').count(),0,'AI percent invented');
    assert.ok((await page.locator('.inspector').innerText()).includes('Ожидается ручной AI'));
    await nav('catalog','all');await page.locator('#course-filter').selectOption('ECON');assert.equal(await page.locator('tbody tr').count(),5);
    await nav('inbox');assert.ok((await page.locator('main').innerText()).includes('Не хватает части 2'));
    await nav('courses');assert.equal(await page.locator('.course-card').count(),3);
    await nav('diagnostics');assert.ok((await page.locator('main').innerText()).includes('Не запускался этим UI'));
    checks.push('Unicode, Chinese search, course/state filters, manual AI has no percent, pending group, diagnostics');
    await nav('home');await action('glass');assert.ok((await page.locator('body').getAttribute('class')).includes('no-glass'));await action('glass');
    await action('fallback');for(let n=0;n<6;n++)await page.keyboard.press('Tab');assert.equal(await page.locator('dialog').evaluate(el=>el.contains(document.activeElement)),true);await page.keyboard.press('Escape');assert.equal(await page.locator('dialog[open]').count(),0);
    await page.route('**/api/v1/snapshot',route=>route.abort());await action('refresh');await page.waitForSelector('.stale-source');
    assert.equal(await page.locator('[role="progressbar"]').count(),0);assert.ok(!(await page.locator('.active-job').innerText()).includes('57%'));assert.ok(!(await page.locator('.worker-grid').innerText()).includes('GPU · CUDA'));
    await page.screenshot({path:path.join(out,'connection-lost.png'),animations:'disabled'});await page.unroute('**/api/v1/snapshot');await action('refresh');await page.waitForSelector('[role="progressbar"]');
    checks.push('Reduced transparency, keyboard modal focus/Escape, connection loss hides N/M/percent/ETA/observed device');
    for(const [w,h] of [[1280,720],[2560,1440],[1024,576],[640,360]]){
      await page.setViewportSize({width:w,height:h});
      for(const view of ['home','catalog','inbox','courses','diagnostics']){await nav(view);await layout(`${view} ${w}x${h}`);}
      await nav('home');await page.screenshot({path:path.join(out,`viewport-${w}.png`),animations:'disabled'});
    }
    checks.push('Five views at four desktop/scaled viewport sizes, no horizontal overflow');
    for(const factor of [1.25,1.5,2]){
      const scaled=await browser.newContext({viewport:{width:1280,height:720},deviceScaleFactor:factor});const p=await scaled.newPage();
      await p.goto(fixture);await p.waitForSelector('.worker-card');assert.equal(await p.evaluate(()=>devicePixelRatio),factor);
      assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await p.screenshot({path:path.join(out,`browser-scale-${factor}.png`),animations:'disabled'});await scaled.close();
    }
    checks.push('Browser device scale 125/150/200 percent (not native Windows DPI acceptance)');
    await page.setViewportSize({width:1440,height:1000});await goto(dev);await nav('catalog');await page.locator('#global-search').fill('保留 · русский');await page.waitForTimeout(3400);assert.equal(await page.locator('#global-search').inputValue(),'保留 · русский');
    checks.push('Real automatic polling preserves search input');
    assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
    const result={result:'PASS',javascriptErrors:errors,externalRequests:requests.length,checks,layouts,deviceScaleFactors:[1.25,1.5,2],nativeDpiAcceptance:false};
    fs.writeFileSync(path.join(out,'browser-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
