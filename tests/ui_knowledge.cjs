/* 法考 3.4 藏经阁·典籍索引真实浏览器回归：看知识点（只读）→ 我的批注随时修改（保存即生效、刷新还在、历史回滚、冲突提示、新建改名删除）
   → 待审建议采纳/忽略 → 解惑预览（定位、没找到时的提示）；电脑/平板不整页滚动、不溢出。
   服务只用临时自编笔记与假HOME，不连接AI。 */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
let logs='',browser,active,service;
function start(){service=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','--knowledge-fixture'],{env:process.env});service.stderr.on('data',x=>logs+=x);
 return new Promise((resolve,reject)=>{let s='';const timer=setTimeout(()=>reject(Error(logs||'服务启动超时')),20000);service.stdout.on('data',x=>{s+=x;const m=s.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});service.on('exit',()=>{clearTimeout(timer);reject(Error(logs||'服务退出'));});});}
const out=path.resolve('ui-artifacts/knowledge');
async function fit(page,tag){assert.deepEqual(await page.evaluate(()=>{const e=[];if(document.documentElement.scrollHeight>innerHeight+2||document.documentElement.scrollWidth>innerWidth+2||scrollY)e.push('整页滚动或横向溢出');for(const s of ['.kn-side','.kn-main','.kn-panel']){const r=document.querySelector(s)?.getBoundingClientRect();if(!r||r.bottom>innerHeight+2||r.right>innerWidth+2)e.push(s+'伸出屏幕');}return e;}),[],tag);}
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
 const sizes=process.argv.find(a=>a.startsWith('--sizes='))?.split('=')[1]?.split(',');
 for(const [label,viewport] of [['desktop',{width:1280,height:860}],['tablet',{width:800,height:1280}]].filter(([l])=>!sizes||sizes.includes(l))){
  const base=await start();const page=await browser.newPage({viewport});active=page;const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept(d.type()==='prompt'?(d.message().includes('新的文件名')?'合同法.md':'合同.md'):undefined));
  await page.goto(base);await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await page.evaluate(()=>{try{localStorage.removeItem('knowledge-pos')}catch{};LIB.tab='knowledge';go('skeleton');});await page.waitForSelector('.kn-root.shelf .kn-tome');
  assert.match(await page.locator('[data-libtab="knowledge"]').textContent(),/典籍索引/);
  // 0 书架：一个科目一本会浮动的古籍，整块铺满内容区
  const nBoards=await page.evaluate(async()=>(await api('/api/knowledge')).boards.length);
  assert.equal(await page.locator('.kn-tome').count(),nBoards,'一个科目一本书');
  assert((await page.locator('.kn-tome').first().evaluate(e=>getComputedStyle(e).animationName)).includes('tome-float'),'有浮动动画');
  const wide=await page.evaluate(()=>{const r=document.querySelector('#view .scene-panel').getBoundingClientRect();return r.width/innerWidth;});
  assert(wide>0.9,'藏经阁铺满宽度 '+wide);
  await page.locator('.kn-tome').first().click({force:true});await page.waitForSelector('.kn-root.detail .kn-file');
  const first=await page.locator('.kn-who').textContent();assert.match(first,/民法/);assert.match(first,/📝1/);
  // 1 知识点：只读浏览
  await page.locator('.kn-file',{hasText:'物权变动.md'}).locator('summary').click();await page.locator('.kn-sec',{hasText:'善意取得'}).first().click();
  await page.locator('.kn-read').filter({hasText:'善意取得所有权'}).waitFor();assert.match(await page.locator('.kn-view').textContent(),/只读/);
  await page.fill('#knFilter','违约');assert.equal(await page.locator('.kn-sec').count(),1);await page.fill('#knFilter','');
  await fit(page,label+' 知识点');
  // 2 我的批注：待审建议 → 勾选采纳（只采纳第一条），采纳前没有批注
  await page.locator('[data-kn-tab="ann"]').click();await page.waitForSelector('.kn-prop');
  assert.equal(await page.locator('.kn-chip').count(),0);
  await page.locator('.kn-prop .kn-edit').nth(1).locator('input').uncheck();
  await page.locator('[data-kn="accept"]').click();await page.locator('.kn-note').filter({hasText:'已采纳：物权.md'}).waitFor();
  assert.match(await page.locator('.kn-read').textContent(),/善意取得别漏了善意要件/);
  assert.equal(await page.locator('.kn-prop .kn-edit.done').count(),1);
  await page.locator('[data-kn="dismiss"]').click();await page.locator('.kn-note').filter({hasText:'已忽略'}).waitFor();assert.equal(await page.locator('.kn-prop').count(),0);
  await fit(page,label+' 批注');
  // 3 随时修改：保存即生效、刷新还在
  await page.locator('[data-kn="edit"]').click();await page.waitForSelector('#knText');
  await page.fill('#knText','# 物权批注\n我自己的理解：登记不是善意取得的唯一要件');await page.keyboard.press('Control+s');
  await page.locator('.kn-note').filter({hasText:'已保存'}).waitFor();
  assert.match(await page.locator('.kn-read').textContent(),/我自己的理解/);
  await page.reload();await page.waitForFunction(()=>typeof go==='function'&&typeof DASH!=='undefined'&&!!DASH);
  await page.evaluate(()=>{LIB.tab='knowledge';go('skeleton');});await page.waitForSelector('.kn-root.shelf .kn-tome');
  await page.locator('.kn-tome').first().click({force:true});await page.waitForSelector('.kn-read');
  assert.match(await page.locator('.kn-read').textContent(),/我自己的理解/);
  // 4 历史与回滚
  await page.locator('[data-kn="history"]').click();await page.waitForSelector('.kn-ver');assert.equal(await page.locator('.kn-ver').count(),1);
  await page.locator('[data-kn="peek"]').click();assert.match(await page.locator('.kn-diff').textContent(),/善意取得别漏了善意要件/);
  await page.locator('[data-kn="restore"]').click();await page.locator('.kn-note').filter({hasText:'已回滚'}).waitFor();assert.match(await page.locator('.kn-read').textContent(),/善意取得别漏了善意要件/);
  // 5 版本冲突：别处先改，这里再保存被拒绝且草稿保留
  await page.locator('[data-kn="edit"]').click();await page.waitForSelector('#knText');await page.fill('#knText','我的草稿不能丢');
  await page.evaluate(async()=>{const f=await api('/api/annotations/file',{board:'民法',path:'物权.md'});await api('/api/annotations/save',{board:'民法',path:'物权.md',text:'别处改的',base:f.rev});});
  await page.locator('[data-kn="save"]').click();await page.locator('.kn-note').filter({hasText:'别处被改过'}).waitFor();assert.equal(await page.inputValue('#knText'),'我的草稿不能丢');
  await page.locator('[data-kn="cancel"]').click();await page.locator('.kn-read').filter({hasText:'别处改的'}).waitFor();
  // 6 新建、改名、删除；分析套路
  await page.locator('[data-kn="newfile"]').click();await page.waitForSelector('#knText');await page.fill('#knText','# 合同\n自编合同批注');await page.locator('[data-kn="save"]').click();
  await page.locator('.kn-chip',{hasText:'合同.md'}).waitFor();
  await page.locator('[data-kn="rename"]').click();await page.locator('.kn-note').filter({hasText:'已改名'}).waitFor();await page.locator('.kn-chip',{hasText:'合同法.md'}).waitFor();
  await page.locator('[data-kn="delete"]').click();await page.locator('.kn-note').filter({hasText:'已删除'}).waitFor();assert.equal(await page.locator('.kn-chip',{hasText:'合同法.md'}).count(),0);
  await page.locator('[data-kn="analysis"]').click();await page.waitForSelector('#knText');await page.locator('[data-kn="cancel"]').click().catch(()=>{});
  assert.equal(await page.locator('[data-kn="analysis"]').count(),0,'有了分析套路就不再显示新建按钮');
  // 7 解惑预览：定位到、没找到
  await page.locator('[data-kn-tab="preview"]').click();await page.waitForSelector('#knQ');
  await page.fill('#knQ','无处分权人转让不动产，受让人善意取得所有权须满足什么条件？依据第三百一十一条。');await page.locator('[data-kn="locate"]').click();
  await page.locator('.kn-hit').first().waitFor();assert.match(await page.locator('.kn-res').textContent(),/善意取得/);assert.match(await page.locator('.kn-res').textContent(),/\/ 30,000 字/);
  assert.equal(await page.locator('[data-kn="aiLocate"]').isDisabled(),true,'没填 AI key 不能点');
  await page.fill('#knQ','完全无关的内容zzz');await page.locator('[data-kn="locate"]').click();await page.locator('.kn-warn').filter({hasText:'没有在你的笔记里找到对应知识点'}).waitFor();
  await fit(page,label+' 预览');
  await page.locator('[data-kn="shelf"]').click();await page.waitForSelector('.kn-root.shelf .kn-tome');
  const t0=Date.now();await page.evaluate(()=>{go('home')});await page.evaluate(()=>{LIB.tab='knowledge';go('skeleton');});await page.waitForSelector('.kn-tome');
  assert(Date.now()-t0<2500,'再次进入立即出书架');
  assert.deepEqual(errors,[]);await page.close();service.kill();console.log('法考 '+label+'：知识点只读/批注随时修改/采纳忽略/历史冲突/预览定位通过');
 }
}catch(e){if(active&&!active.isClosed()){fs.mkdirSync(out,{recursive:true});await active.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}throw e;}finally{await browser?.close();service?.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
