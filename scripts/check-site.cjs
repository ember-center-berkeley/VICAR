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
  const grid=JSON.parse(fs.readFileSync(path.join(root,'assets/augmentation/forehand.json'),'utf8'));
  let shift=[-.08,0,0];
  for(const [axisIndex,axis] of ['x','y','z'].entries()) {
   for(let step=0;step<9;step++) {
    shift[axisIndex]=Number((grid.axes[axis].min+step*.01).toFixed(2));
    await page.locator('#shift-'+axis).fill(String(shift[axisIndex]));
    const index=grid.shifts.findIndex(s=>s.every((value,i)=>Math.abs(value-shift[i])<1e-6));
    await page.waitForFunction(index=>document.querySelector('#augmentation-controls').dataset.selectedIndex===String(index),index);
   }
  }
  assert.equal(await page.locator('#viser-frame').getAttribute('src'),iframeSource,'Sliders must not reload the viewer');
  assert.equal(await timeInput.inputValue(),'4.5','Sliders must preserve paused playback time');
  await page.locator('#reset-shift').click();
  await page.waitForFunction(()=>document.querySelector('#augmentation-controls').dataset.selectedIndex==='364');
  // Standalone Open viewer has the same sliders within the Viser window.
  const standalone=await browser.newPage();
  await standalone.goto(await page.locator('#open-viewer').getAttribute('href'));
  await standalone.getByRole('slider',{name:'X contact shift'}).waitFor();
  await standalone.getByRole('slider',{name:'X contact shift'}).fill('-0.12');
  await standalone.waitForFunction(()=>document.documentElement.dataset.augmentationIndex==='400');
  await standalone.close();
  // Exercise every task, including six deliberate missing-data states.
  const scenes = await page.evaluate(() => window.VICAR.viewer.scenes);
  assert.equal(scenes.length,10);
  let recordings = 0;
  for(const scene of scenes) {
   const firstResponse = scene.variants.length ? page.waitForResponse(r=>r.url().includes(scene.variants[0].recording) && r.request().method()==='GET' && r.status()===200) : null;
   await page.locator('#demo-scene').selectOption(scene.id);
   if(!scene.variants.length) {
    assert.equal(await page.locator('#viser-frame').isHidden(),true);
    assert.equal(await page.locator('#load-demo').isHidden(),true);
    assert.equal(await page.locator('#open-viewer').isHidden(),true);
    assert.match(await page.locator('#motion-meta').textContent(),/coming soon/);
    continue;
   }
   await firstResponse;
   for(const [i,variant] of scene.variants.entries()) {
    if (i > 0) {
     const response = page.waitForResponse(r=>r.url().includes(variant.recording) && r.request().method()==='GET' && r.status()===200);
     await page.getByRole('button',{name:variant.label,exact:true}).click();
     await response;
    }
    await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor();
    // Wait for playback to advance, so checks don't stop at an empty canvas
    // mounted before the recording messages have been applied.
    const frame = page.frames().find(f=>f.url().includes('viser-client'));
    await frame.waitForFunction(()=>Array.from(document.querySelectorAll('input')).some(input=>Number(input.value)>0.1),null,{timeout:15000});
    assert.match(await page.locator('#motion-meta').textContent(),/frames.*fps/);
    recordings++;
   }
  }
  assert.equal(recordings,9);
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
  await page.route('**/assets/recordings/**',route=>route.fulfill({status:404,body:''}));
  await page.getByRole('button',{name:'Saved motion',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#demo-status').textContent.includes('could not be loaded'));
  assert.equal(await page.locator('#load-demo').isVisible(),true);
  assert.equal(await page.locator('#viser-frame').isHidden(),true);
  // A scene switch while the initial HEAD request is pending must cancel it.
  await page.unroute('**/assets/recordings/**');
  await page.reload({waitUntil:'networkidle'});
  let releaseHead;
  const heldHead = new Promise(resolve=>{releaseHead=resolve;});
  await page.route('**/assets/augmentation/*.viser',async route=>{
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
  await page.waitForTimeout(100);
  assert.equal(await page.locator('#viser-frame').getAttribute('src'),null);
  assert.equal(await page.locator('#viser-frame').isHidden(),true);
  await page.unroute('**/assets/augmentation/*.viser');
  await page.locator('#demo-scene').selectOption('ladder-climbing');
  await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS: X/Y/Z sliders at all 9 positions, preserved playback time, standalone controls, 10 video slots, all 9 recordings, 6 pending tasks, responsive widths, missing-scene recovery, and scene-switch race.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
