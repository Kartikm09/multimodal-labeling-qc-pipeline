const {test,expect}=require('@playwright/test');
test('real playback, frame stepping, revision preservation, validation and ranking',async({page})=>{
  await page.goto('/');await expect(page.getByRole('status',{name:'Review status'})).toContainText('Ready.');
  await expect(page.locator('#clip')).toHaveJSProperty('readyState',4);
  await page.locator('#clip').evaluate(video=>video.play());
  await expect.poll(()=>page.locator('#clip').evaluate(video=>video.currentTime)).toBeGreaterThan(0.08);
  await page.locator('#clip').evaluate(video=>{video.pause();video.currentTime=0;});
  await expect(page.locator('#time')).toContainText('0.000 s');
  await page.getByRole('button',{name:'Next frame'}).click();await expect(page.locator('#time')).toContainText('Frame 1');
  await page.getByRole('button',{name:'Next frame'}).click();await expect(page.locator('#time')).toContainText('0.200 s');
  await page.getByRole('button',{name:'Previous frame'}).click();await expect(page.locator('#time')).toContainText('0.080 s');
  await page.locator('#event').selectOption('1');await page.locator('#end').fill('0');await page.locator('#reason').fill('Invalid reverse interval must be rejected.');
  await page.getByRole('button',{name:'Save new revision'}).click();await expect(page.getByRole('status',{name:'Review status'})).toContainText('reversed or out-of-range');
  await expect(page.locator('#history li')).toHaveCount(1);
  await page.locator('#end').fill(await page.locator('#start').inputValue());
  await page.locator('#event').selectOption('2');await page.locator('#event').selectOption('1');
  await page.locator('#outcome').selectOption('attempted');await page.locator('#reason').fill('Simulated reviewer: separate contact attempt from visible lift outcome.');
  await page.getByRole('button',{name:'Save new revision'}).click();await expect(page.getByRole('status',{name:'Review status'})).toContainText('Saved a new revision');
  await expect(page.locator('#history li')).toHaveCount(2);await expect(page.locator('#event')).toBeFocused();
  const history=await(await page.request.get('/api/cases/known-boundaries')).json();expect(history.history[0].document.events[1].outcome).toBe('successful');expect(history.history[1].document.events[1].outcome).toBe('attempted');
  await page.locator('#ranking_evidence').fill('Revision 1 preserves the uncertainty between contact and successful manipulation.');
  await page.getByRole('button',{name:'Save pairwise ranking'}).click();await expect(page.getByRole('status',{name:'Review status'})).toContainText('ranking saved');
  await expect(page.locator('#rankings li')).toHaveCount(1);
});
test('ambiguous simulation remains explicitly uncertain; real screenshots at three viewports',async({page})=>{
  await page.clock.setFixedTime(new Date('2026-09-18T12:00:00Z'));await page.goto('/');
  await page.locator('#case').selectOption('ambiguous-contact');await expect(page.getByRole('status',{name:'Review status'})).toContainText('Ready.');
  await page.locator('#event').selectOption('1');await expect(page.locator('#outcome')).toHaveValue('unknown');await expect(page.locator('#occluded')).toBeChecked();
  await expect(page.locator('#clip')).toHaveJSProperty('readyState',4);
  await page.locator('#clip').evaluate(video=>video.play());
  await expect.poll(()=>page.locator('#clip').evaluate(video=>video.currentTime)).toBeGreaterThan(0.08);
  await page.locator('#clip').evaluate(video=>new Promise(resolve=>{video.pause();video.addEventListener('seeked',()=>requestAnimationFrame(()=>requestAnimationFrame(resolve)),{once:true});video.currentTime=1.6;}));
  await expect(page.locator('#clip')).toHaveJSProperty('seeking',false);
  await expect(page.locator('#time')).toContainText('1.600 s');
  for(const [width,height] of [[1920,1080],[1440,900],[390,844]]){await page.setViewportSize({width,height});await page.screenshot({path:`reports/ui-chromium-${process.platform}-${width}x${height}.png`,fullPage:true});}
});

test('empty and newly added API event revisions render safely', async({page})=>{
  const endpoint='/api/cases/ambiguous-contact';
  const before=await(await page.request.get(endpoint)).json();
  const latest=before.history.at(-1);const empty=structuredClone(latest.document);empty.events=[];
  const response=await page.request.post(endpoint+'/revisions',{data:{document:empty,reviewer:'simulated-api-reviewer',reason:'No defensible action boundary in this review.',expected_revision:latest.revision}});
  expect(response.status()).toBe(201);await page.goto('/');await page.locator('#case').selectOption('ambiguous-contact');
  await expect(page.getByRole('status',{name:'Review status'})).toContainText('Ready.');await expect(page.locator('#comparison')).toContainText('No events');
  await expect(page.getByRole('button',{name:'Save new revision'})).toBeDisabled();
  const added=structuredClone(latest.document);added.events=[{...latest.document.events[0],id:'new-review-event'}];
  expect((await page.request.post(endpoint+'/revisions',{data:{document:added,reviewer:'simulated-api-reviewer',reason:'Add separately identified reviewed interval.',expected_revision:latest.revision+1}})).status()).toBe(201);
  await page.reload();await page.locator('#case').selectOption('ambiguous-contact');await expect(page.getByRole('status',{name:'Review status'})).toContainText('Ready.');
  await expect(page.locator('#comparison')).toContainText('Added in review');await expect(page.getByRole('button',{name:'Save new revision'})).toBeEnabled();
});
