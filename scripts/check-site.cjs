/* Browser integration checks. Run npm install, npx playwright install chromium,
 * then npm test. PLAYWRIGHT_MODULE and CHROME_CHANNEL are optional local overrides. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const types = {'.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.svg':'image/svg+xml', '.png':'image/png', '.jpg':'image/jpeg', '.mp4':'video/mp4', '.viser':'application/octet-stream'};
const server = http.createServer((req, res) => {
 const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
 const relative = pathname.replace(/^\/VICAR\//, '/');
 let file = path.resolve(root, '.' + relative);
 if (!file.startsWith(root + path.sep) && file !== root) {res.writeHead(403).end();return;}
 if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file,'index.html');
 if (!fs.existsSync(file)) {res.writeHead(404).end();return;}
 res.setHeader('Content-Type',types[path.extname(file)] || 'application/octet-stream');
 const size=fs.statSync(file).size;
 res.setHeader('Accept-Ranges','bytes');
 const range=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
 if(range) {
  const start=Number(range[1]), end=range[2]?Math.min(Number(range[2]),size-1):size-1;
  if(start>=size || end<start) {res.writeHead(416,{'Content-Range':`bytes */${size}`}).end();return;}
  res.writeHead(206,{'Content-Range':`bytes ${start}-${end}/${size}`,'Content-Length':end-start+1});
  if(req.method==='HEAD')res.end();else fs.createReadStream(file,{start,end}).pipe(res);
  return;
 }
 res.setHeader('Content-Length',size);
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
  assert.equal(await page.locator('.media-slot video').count(),10,'All ten task videos must be present');
  assert.equal(await page.locator('.media-placeholder').count(),0,'All video slots are now populated');
  assert.equal(requests.some(url=>url.includes('/assets/videos/')),false,'Clips must not download before play');
  assert.equal(await page.locator('.media-slot video[preload="none"]').count(),10);
  assert.equal(await page.locator('.hero-actions [data-resource="video"]').getAttribute('href'),'#skills');
  // Hero: two actions, paper links in the nav, and a still poster under reduced motion.
  assert.equal(await page.locator('.hero-actions a').count(),2);
  assert.deepEqual(await page.locator('.nav-cta').allTextContents(),['arXiv','Paper','Code']);
  assert.match(await page.locator('#hero-video').getAttribute('poster'),/hero-box-pickup-poster/);
  assert.equal(await page.locator('#hero-video').getAttribute('src'),null,'Reduced motion must not play the hero loop');
  assert.equal(await page.locator('#hero-toggle').isHidden(),true);
  await page.waitForFunction(()=>document.querySelector('#hero-source img').naturalWidth>0);
  assert.equal(await page.locator('#hero-source').isVisible(),true,'The human demonstration card must show');
  assert.equal(await page.locator('.hero').getAttribute('class'),'hero');
  // Abstract: gap, idea and result cards, with the full text collapsed until asked for.
  assert.deepEqual(await page.locator('.idea-label').allTextContents(),['The gap','The idea','The result']);
  assert.equal(await page.locator('#abstract-text').isVisible(),false);
  await page.locator('.abstract-details summary').click();
  assert.ok((await page.locator('#abstract-text').textContent()).split(/\s+/).length>200,'The full abstract must be available');
  assert.equal(requests.some(url=>url.includes('.viser')),false,'Viewer must wait until its section is near');
  assert.equal(await page.locator('[data-resource=arxiv]').getAttribute('href'),'./');
  for (let i=0;i<6;i++) {
   await page.locator('#serve-dots button').nth(i).click();
   await page.waitForFunction(index=>document.querySelectorAll('#serve-dots button')[index].getAttribute('aria-current')==='true',i);
  }
  assert.equal(await page.locator('#serve-next').isDisabled(),true);
  await page.locator('#serve-track').focus();
  await page.keyboard.press('ArrowLeft');
  await page.waitForFunction(()=>document.querySelectorAll('#serve-dots button')[4].getAttribute('aria-current')==='true');
  // Reaching the section loads the viewer without a click.
  await page.locator('#demo-stage').scrollIntoViewIfNeeded();
  await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor({timeout:20000});
  assert.match(await page.locator('#viser-frame').getAttribute('src'),/\/VICAR\/viser-client\//);
  await page.waitForFunction(()=>document.querySelector('#augmentation-controls').dataset.selectedIndex==='364');
  // The wheel scrolls the page past the viewer until the scene is clicked, then zooms.
  const stageBox=await page.locator('#demo-stage').boundingBox();
  await page.mouse.move(stageBox.x+stageBox.width/2,stageBox.y+stageBox.height/2);
  const beforeWheel=await page.evaluate(()=>scrollY);
  await page.mouse.wheel(0,200);
  await page.waitForFunction(y=>scrollY>y,beforeWheel);
  await page.mouse.down();
  await page.mouse.up();
  const clickedAt=await page.evaluate(()=>scrollY);
  await page.mouse.wheel(0,200);
  await page.waitForTimeout(300);
  assert.equal(await page.evaluate(()=>scrollY),clickedAt,'After a click the wheel must zoom, not scroll');
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
  // With data saver on, the viewer waits for the button.
  const saver=await browser.newPage({viewport:{width:1440,height:1000}});
  await saver.addInitScript(()=>Object.defineProperty(navigator,'connection',{value:{saveData:true}}));
  await saver.goto(origin+'/VICAR/',{waitUntil:'networkidle'});
  await saver.locator('#demo-stage').scrollIntoViewIfNeeded();
  await saver.waitForTimeout(500);
  assert.equal(await saver.locator('#viser-frame').getAttribute('src'),null,'Data saver must wait for the button');
  await saver.getByRole('button',{name:'Load 3D demo'}).click();
  await saver.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor({timeout:20000});
  await saver.close();
  // Without a loop or poster, the hero falls back to centred text.
  const broken=await browser.newPage({viewport:{width:1440,height:900}});
  await broken.route(/hero-box-pickup/,route=>route.fulfill({status:404,body:''}));
  await broken.goto(origin+'/VICAR/',{waitUntil:'networkidle'});
  await broken.waitForFunction(()=>document.querySelector('.hero').classList.contains('hero-centered'));
  assert.equal(await broken.locator('.hero-media').isHidden(),true);
  assert.equal(await broken.locator('#hero-toggle').isHidden(),true);
  await broken.close();
  // Touch screens get a tap-to-interact shield so swipes scroll the page.
  const phone=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const touch=await phone.newPage();
  await touch.goto(origin+'/VICAR/',{waitUntil:'networkidle'});
  // Without reduced motion the hero loop plays and its button pauses it.
  assert.match(await touch.locator('#hero-video').getAttribute('src'),/hero-box-pickup\.mp4/);
  if (await touch.evaluate(()=>document.createElement('video').canPlayType('video/mp4; codecs="avc1.640028"'))) {
   await touch.waitForFunction(()=>!document.querySelector('#hero-video').paused);
   await touch.locator('#hero-toggle').tap();
   assert.equal(await touch.evaluate(()=>document.querySelector('#hero-video').paused),true);
   assert.equal(await touch.locator('#hero-toggle').getAttribute('aria-label'),'Play background video');
  }
  await touch.locator('#demo-stage').scrollIntoViewIfNeeded();
  await touch.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor({timeout:20000});
  assert.equal(await touch.locator('#viewer-shield').isVisible(),true);
  await touch.locator('#viewer-shield').tap();
  assert.equal(await touch.locator('#viewer-shield').isVisible(),false);
  await phone.close();
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
    const grid=JSON.parse(fs.readFileSync(path.join(root,variant.augmentationPath.split('?')[0]),'utf8'));
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
  for(const width of [1440,768,390,320]) {
   await page.setViewportSize({width,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Overflow at ${width}px`);
   const layout=await page.locator('#serve-track').evaluate(track=>({track:track.clientWidth,cards:Array.from(track.children).map(card=>card.getBoundingClientRect().width)}));
   assert.ok(layout.cards.every(width=>Math.abs(width-layout.track)<2),'Show one full-width serve at every screen size');
   const climbingWidth=await page.locator('#ladder-climbing').evaluate(card=>card.getBoundingClientRect().width);
   const skillsWidth=await page.locator('#other-skills').evaluate(grid=>grid.getBoundingClientRect().width);
   const climbingScale=width>600 ? .5 : 1;
   assert.ok(Math.abs(climbingWidth-skillsWidth*climbingScale)<2,'Climbing comparison must use half width on larger screens and full width on mobile');
  }
  // Missing-recording recovery should provide retry UI, not a broken iframe.
  await page.route('**/assets/augmentation/tasks/*.viser*',route=>route.fulfill({status:404,body:''}));
  await page.getByRole('button',{name:'Reset view',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#demo-status').textContent.includes('could not be loaded'));
  assert.equal(await page.locator('#load-demo').isVisible(),true);
  assert.equal(await page.locator('#viser-frame').isHidden(),true);
  // A scene switch while the initial HEAD request is pending must cancel it.
  await page.unroute('**/assets/augmentation/tasks/*.viser*');
  let releaseHead;
  const heldHead = new Promise(resolve=>{releaseHead=resolve;});
  await page.route('**/assets/augmentation/serves/*.viser',async route=>{
   if(route.request().method()==='HEAD') await heldHead;
   await route.continue();
  });
  const headStarted=page.waitForRequest(r=>r.url().includes('.viser') && r.method()==='HEAD');
  await page.reload({waitUntil:'load'});
  await page.locator('#demo-stage').scrollIntoViewIfNeeded();
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
  // Decode, play and seek every supplied clip, with the actual Pages URL prefix.
  await page.setViewportSize({width:1440,height:1000});
  const clips=await page.evaluate(()=>[...window.VICAR.serves,...window.VICAR.skills].filter(item=>item.src));
  for(const [index,clip] of clips.entries()) {
   if(index<6) {
    await page.locator('#serve-dots button').nth(index).click();
    await page.waitForFunction(i=>document.querySelectorAll('#serve-dots button')[i].getAttribute('aria-current')==='true',index);
   }
   const video=page.locator(`#${clip.id} video`);
   await video.scrollIntoViewIfNeeded();
   assert.ok(fs.statSync(path.join(root,clip.src)).size<=20_000_000,`${clip.id} exceeds 20 MB`);
   await video.evaluate(async video=>{video.muted=true;await video.play();});
   await page.waitForFunction(id=>document.querySelector(`#${id} video`).currentTime>.1,clip.id);
   const metadata=await video.evaluate(video=>({width:video.videoWidth,height:video.videoHeight,duration:video.duration,poster:video.poster,error:video.error}));
   assert.equal(metadata.error,null);
   assert.equal(metadata.width,clip.width);
   assert.equal(metadata.height,clip.height);
   if(clip.duration)assert.ok(Math.abs(metadata.duration-clip.duration)<.1,'Preserve the climbing comparison duration');
   else assert.ok(metadata.duration>15 && metadata.duration<25);
   await video.evaluate(video=>{video.pause();video.currentTime=video.duration*.75;});
   await page.waitForFunction(id=>{const v=document.querySelector(`#${id} video`);return !v.seeking && v.readyState>=2 && v.currentTime>v.duration*.7;},clip.id);
  }
  if(process.env.SCREENSHOT_DIR) {
   await page.locator('#serve-dots button').first().click();
   await page.locator('#skills').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'serve-videos.png')});
   await page.locator('#under-table-pickup').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'pickup-comparison.png')});
   await page.locator('#ladder-climbing').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'climbing-comparison.png')});
   await page.setViewportSize({width:390,height:844});
   await page.locator('#skills').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'serve-mobile.png')});
   await page.locator('#ladder-climbing').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'climbing-mobile.png')});
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: all ten compressed videos play and seek, responsive aligned climbing comparison, native aspect ratios, no video preloading, full-width serve carousel, responsive widths, hero controls, all 10 tasks / 11 viewers, every sampled XYZ position, fixed axes, scene layers, preserved playback, standalone controls, missing-scene recovery, and scene-switch race.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
