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
  // Check both scenes and all variants. Await the actual recording response.
  for(const scene of ['serve','pickup']) {
   await page.locator('#demo-scene').selectOption(scene);
   for(const variant of ['Original','Shift left','Shift right','Move forward','Move higher']) {
    const response = page.waitForResponse(r=>r.url().includes('.viser') && r.request().method()==='GET' && r.status()===200);
    await page.getByRole('button',{name:variant,exact:true}).click();
    await response;
    await page.frameLocator('#viser-frame').locator('canvas:visible').first().waitFor();
   }
  }
  for(const width of [768,390,320]) {
   await page.setViewportSize({width,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Overflow at ${width}px`);
  }
  // Missing-recording recovery should provide retry UI, not a broken iframe.
  await page.route('**/assets/recordings/**',route=>route.fulfill({status:404,body:''}));
  await page.getByRole('button',{name:'Shift left',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#demo-status').textContent.includes('could not be loaded'));
  assert.equal(await page.locator('#load-demo').isVisible(),true);
  assert.equal(await page.locator('#viser-frame').isHidden(),true);
  assert.deepEqual(errors,[]);
  console.log('PASS: 10 slots, 6 carousel selections, keyboard controls, 10 Viser recordings, /VICAR/ paths, 3 responsive widths, and missing-scene recovery.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
