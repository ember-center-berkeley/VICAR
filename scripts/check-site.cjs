/* Browser integration checks. Run npm install, npx playwright install chromium,
 * then npm test. PLAYWRIGHT_MODULE and CHROME_CHANNEL are optional local overrides. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const types = {'.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.svg':'image/svg+xml', '.png':'image/png', '.viser':'application/octet-stream'};
const server = http.createServer((req, res) => {
 const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
 const relative = pathname.replace(/^\/VICAR\//, '/');
 let file = path.resolve(root, '.' + relative);
 if (!file.startsWith(root + path.sep) && file !== root) {res.writeHead(403).end();return;}
 if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file,'index.html');
 if (!fs.existsSync(file)) {res.writeHead(404).end();return;}
 res.setHeader('Content-Type',types[path.extname(file)] || 'application/octet-stream');
 if (req.method === 'HEAD') res.end(); else fs.createReadStream(file).pipe(res);
});
(async () => {
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin = `http://127.0.0.1:${server.address().port}`;
 const browser = await chromium.launch({headless:true,channel:process.env.CHROME_CHANNEL || undefined,args:['--no-proxy-server']});
 try {
  const page = await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const errors=[]; const requests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',request=>requests.push(request.url()));
  await page.goto(origin+'/VICAR/',{waitUntil:'networkidle'});
  assert.equal(await page.locator('#serve-track article').count(),6);
  assert.equal(await page.locator('#other-skills article').count(),4);
  assert.equal(await page.locator('video').count(),0,'Empty slots must not request nonexistent clips');
  assert.equal(requests.some(url=>url.includes('.viser')),false,'Viewer must load on demand');
  assert.equal(await page.locator('[data-resource=arxiv]').getAttribute('href'),'./');
  for (let i=0;i<6;i++) {
   await page.locator('#serve-dots button').nth(i).click();
   await page.waitForFunction(index=>document.querySelectorAll('#serve-dots button')[index].getAttribute('aria-current')==='true',i);
  }
  assert.equal(await page.locator('#serve-next').isDisabled(),true);
  await page.locator('#serve-track').focus();
  await page.keyboard.press('ArrowLeft');
  await page.waitForFunction(()=>document.querySelectorAll('#serve-dots button')[4].getAttribute('aria-current')==='true');
  await page.getByRole('button',{name:'Load 3D demo'}).click();
  await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor({timeout:20000});
  assert.match(await page.locator('#viser-frame').getAttribute('src'),/\/VICAR\/viser-client\//);
  await page.waitForFunction(()=>document.querySelector('#augmentation-controls').dataset.selectedIndex==='364');
  const forehandFrame=page.frames().find(frame=>frame.url().includes('viser-client'));
  await forehandFrame.getByRole('button',{name:'Pause motion',exact:true}).click();
  const timeInput=forehandFrame.getByRole('textbox',{name:'Playback time',exact:true});
  await timeInput.fill('4.5');
  await timeInput.press('Tab');
  const iframeSource=await page.locator('#viser-frame').getAttribute('src');
  await page.locator('#shift-x').fill('-0.16');
  await page.waitForFunction(()=>document.querySelector('#augmentation-controls').dataset.selectedIndex==='400');
  assert.equal(await page.locator('#viser-frame').getAttribute('src'),iframeSource,'Sliders must not reload the viewer');
  assert.equal(await timeInput.inputValue(),'4.5','Sliders must preserve paused playback time');
  await page.locator('#reset-shift').click();
  await page.waitForFunction(()=>document.querySelector('#augmentation-controls').dataset.selectedIndex==='364');
  // Exercise all ten tasks, both tabletop hands, each actual sampled axis,
  // fixed dimensions, independent scene layers, and standalone playback.
  const scenes = await page.evaluate(() => window.VICAR.viewer.scenes);
  assert.equal(scenes.length,10);
  let recordings = 0;
  for(const scene of scenes) {
   assert.ok(scene.variants.length,`${scene.id} must have a populated viewer`);
   const firstResponse=page.waitForResponse(r=>r.url().includes(scene.variants[0].recording) && r.request().method()==='GET' && r.status()===200);
   await page.locator('#demo-scene').selectOption(scene.id);
   await firstResponse;
   assert.equal(await page.locator('#demo-variants').isVisible(),scene.variants.length>1);
   for(const [i,variant] of scene.variants.entries()) {
    if(i>0) {
     const response=page.waitForResponse(r=>r.url().includes(variant.recording) && r.request().method()==='GET' && r.status()===200);
     await page.getByRole('button',{name:variant.label,exact:true}).click();
     await response;
     assert.equal(await page.getByRole('button',{name:variant.label,exact:true}).getAttribute('aria-pressed'),'true');
    }
    await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor();
    const frame=page.frames().find(f=>f.url().includes('viser-client'));
    const grid=JSON.parse(fs.readFileSync(path.join(root,variant.augmentationPath),'utf8'));
    await page.waitForFunction(index=>document.querySelector('#augmentation-controls').dataset.selectedIndex===String(index),grid.defaultIndex,{timeout:60000});
    assert.equal(variant.sampleCount,grid.shifts.length);
    assert.match(await page.locator('#motion-meta').textContent(),/frames.*fps/);
    await frame.getByRole('button',{name:'Pause motion',exact:true}).click();
    const time=frame.getByRole('textbox',{name:'Playback time',exact:true});
    const displayTime=Number(((grid.hitFrame || 200)/grid.fps).toFixed(1));
    await time.fill(String(displayTime));await time.press('Tab');
    const src=await page.locator('#viser-frame').getAttribute('src');
    const shift=['x','y','z'].map(axis=>grid.axes[axis].default);
    const indexFor=values=>grid.shifts.findIndex(s=>s.every((v,i)=>Math.abs(v-values[i])<1e-6));
    for(const [axisIndex,axis] of ['x','y','z'].entries()) {
     const input=page.locator('#shift-'+axis);
     const settings=grid.axes[axis];
     if(grid.shifts.length===1) {assert.equal(await input.isHidden(),true);continue;}
     const values=settings.values || Array.from({length:9},(_,j)=>Number((settings.min+j*settings.step).toFixed(6)));
     assert.equal(Number(await input.getAttribute('min')),settings.values?0:settings.min);
     assert.equal(Number(await input.getAttribute('max')),settings.values?values.length-1:settings.max);
     assert.equal(Number(await input.getAttribute('step')),settings.values?1:settings.step);
     assert.equal(await input.isDisabled(),values.length===1);
     if(values.length===1)continue;
     for(const [j,value] of values.entries()) {
      shift[axisIndex]=value;
      await input.fill(String(settings.values?j:value));
      const index=indexFor(shift);
      assert.notEqual(index,-1,'Every displayed slider position must have a solved motion');
      await page.waitForFunction(index=>document.querySelector('#augmentation-controls').dataset.selectedIndex===String(index),index);
      assert.match(await input.getAttribute('aria-valuetext'),/metres/);
     }
    }
    assert.equal(await page.locator('#viser-frame').getAttribute('src'),src,'Shifts must preserve the camera by retaining the iframe');
    assert.equal(Number(await time.inputValue()),displayTime,'Shifts must preserve paused time');
    await page.locator('#show-hit-box').uncheck();
    await frame.waitForFunction(()=>document.documentElement.dataset.hitBoxVisible==='false');
    // Replaying/seeking must not restore baseline visibility over our controls.
    await time.fill('1.0');await time.press('Tab');
    await frame.waitForFunction(()=>document.documentElement.dataset.hitBoxVisible==='false');
    await page.locator('#show-hit-box').check();
    if(grid.layers?.length && !await page.locator('#scene-options').evaluate(el=>el.open)) await page.locator('#scene-options summary').click();
    for(const layer of grid.layers || []) {
     const checkbox=page.locator(`#scene-layers input[data-layer="${layer.id}"]`);
     assert.equal(await checkbox.isChecked(),layer.default);
     await checkbox.setChecked(!layer.default);
     await frame.waitForFunction(({id,value})=>JSON.parse(document.documentElement.dataset.sceneLayers)[id]===value,{id:layer.id,value:!layer.default});
     await checkbox.setChecked(layer.default);
    }
    if(grid.shifts.length>1) {
     await page.locator('#reset-shift').click();
     await page.waitForFunction(index=>document.querySelector('#augmentation-controls').dataset.selectedIndex===String(index),grid.defaultIndex);
    } else assert.equal(await page.locator('#reset-shift').isHidden(),true);
    if(grid.shifts.length>1 && await page.locator('#scene-options').evaluate(el=>el.open)) await page.locator('#scene-options summary').click();
    if(process.env.SCREENSHOT_DIR) {
     fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});
     await time.fill(String(displayTime));await time.press('Tab');
     await page.waitForTimeout(400);
     await page.evaluate(()=>document.activeElement?.blur());
     await page.locator('#interactive').screenshot({path:path.join(process.env.SCREENSHOT_DIR,`${scene.id}-${variant.id}.png`)});
    }
    const standalone=await browser.newPage();
    standalone.on('pageerror',e=>errors.push(e.message));
    await standalone.goto(await page.locator('#open-viewer').getAttribute('href'));
    const box=standalone.getByRole('checkbox',{name:grid.boxLabel || 'Show hit box',exact:true});
    await box.waitFor({timeout:60000});
    if(grid.shifts.length>1) {
     const input=standalone.getByRole('slider',{name:'X contact shift',exact:true});
     assert.equal(Number(await input.getAttribute('step')),grid.axes.x.values?1:grid.axes.x.step);
     await input.fill(String(grid.axes.x.values?0:grid.axes.x.min));
     const expected=indexFor([grid.axes.x.min,grid.axes.y.default,grid.axes.z.default]);
     await standalone.waitForFunction(index=>document.documentElement.dataset.augmentationIndex===String(index),expected);
    } else assert.equal(await standalone.getByRole('slider',{name:'X contact shift',exact:true}).count(),0);
    await box.uncheck();
    await standalone.waitForFunction(()=>document.documentElement.dataset.hitBoxVisible==='false');
    for(const layer of grid.layers || [])assert.equal(await standalone.getByRole('checkbox',{name:layer.label,exact:true}).isChecked(),layer.default);
    await standalone.close();
    recordings++;
   }
  }
  assert.equal(recordings,11);
  const resetResponse=page.waitForResponse(r=>r.url().includes('.viser') && r.request().method()==='GET' && r.status()===200);
  await page.getByRole('button',{name:'Reset view',exact:true}).click();
  await resetResponse;
  await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor();
  if(process.env.SCREENSHOT_DIR) {
   fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});
   await page.waitForTimeout(1500); // Allow mesh buffers to upload before visual QA.
   await page.locator('#interactive').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'motion-explorer.png')});
  }
  for(const width of [768,390,320]) {
   await page.setViewportSize({width,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Overflow at ${width}px`);
  }
  // Missing-recording recovery should provide retry UI, not a broken iframe.
  await page.route('**/assets/augmentation/tasks/*.viser',route=>route.fulfill({status:404,body:''}));
  await page.getByRole('button',{name:'Reset view',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#demo-status').textContent.includes('could not be loaded'));
  assert.equal(await page.locator('#load-demo').isVisible(),true);
  assert.equal(await page.locator('#viser-frame').isHidden(),true);
  // A scene switch while the initial HEAD request is pending must cancel it.
  await page.unroute('**/assets/augmentation/tasks/*.viser');
  await page.reload({waitUntil:'networkidle'});
  let releaseHead;
  const heldHead = new Promise(resolve=>{releaseHead=resolve;});
  await page.route('**/assets/augmentation/serves/*.viser',async route=>{
   if(route.request().method()==='HEAD') await heldHead;
   await route.continue();
  });
  const headStarted=page.waitForRequest(r=>r.url().includes('.viser') && r.method()==='HEAD');
  await page.getByRole('button',{name:'Load 3D demo'}).click();
  await headStarted;
  await page.locator('#demo-scene').selectOption('backhand');
  const headFinished=page.waitForResponse(r=>r.url().includes('.viser') && r.request().method()==='HEAD');
  releaseHead();
  await headFinished;
  await page.waitForFunction(()=>document.querySelector('#viser-frame').src.includes('backhand-base.viser'));
  await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor();
  assert.equal(await page.locator('#viser-frame').isVisible(),true);
  await page.unroute('**/assets/augmentation/serves/*.viser');
  await page.locator('#demo-scene').selectOption('ladder-climbing');
  await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS: all 10 tasks / 11 viewers, every sampled XYZ position, fixed axes, both tabletop hands, scene layers, preserved playback, standalone controls, 10 video slots, responsive widths, missing-scene recovery, and scene-switch race.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
