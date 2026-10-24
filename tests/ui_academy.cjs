/* 学院正式美术验收：三种视口真实点击八科楼与公共入口，核对背景、阅读区及高密度图像。 */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const subjects = {
  minfa:['民法','契约馆'], xingfa:['刑法','审判堡'], minsu:['民诉','衡序厅'],
  xingsu:['刑诉','真相塔'], xingzheng:['行政法','律令宫'],
  shangjing:['商经知','创艺坊'], sanguo:['三国法','万国馆'], lilun:['理论法','星穹馆']
};
const only=process.argv.find(a=>a.startsWith('--only='))?.slice(7);
const sizes = [{name:'desktop',width:1280,height:860,dpr:1},
  {name:'portrait',width:800,height:1280,dpr:1},
  {name:'landscape',width:1280,height:800,dpr:2}];
const baseDir = path.resolve(__dirname,'..');
for (const key of Object.keys(subjects).filter(k=>!only||k===only)) {
  const file=path.join(baseDir,`web/assets/beauty/page/train-${key}.webp`);
  assert.ok(fs.existsSync(file),`缺少${key}正式楼内图`);
}
for (const file of only?['academy-day-4k.webp']:['academy-day-4k.webp','academy-portrait-4k.webp'])
  assert.ok(fs.existsSync(path.join(baseDir,'web/assets/academy/scene',file)),`缺少${file}`);

const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','--reader-fixture'],{cwd:baseDir,env:process.env});
let logs='';srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{
  let out='';const timer=setTimeout(()=>reject(Error('测试服务未启动 '+logs)),20000);
  srv.stdout.on('data',b=>{out+=b;const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
  srv.on('exit',c=>{clearTimeout(timer);reject(Error('测试服务退出 '+c+' '+logs));});
});
const artDir=path.join(baseDir,'ui-artifacts/academy');
async function home(page){
  if(await page.evaluate(()=>VIEW)!=='home')await page.evaluate(()=>go('home'));
  await page.locator('.portal-world').waitFor();
}
async function shape(page,where){
  const info=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,
    stage:document.querySelector('.portal-stage')?.getBoundingClientRect().toJSON(),
    background:getComputedStyle(document.body).getPropertyValue('--ds-page-art'),
    badControls:[...document.querySelectorAll('#view button')].filter(b=>b.getClientRects().length&&(
      b.getBoundingClientRect().right>innerWidth+2||b.getBoundingClientRect().left< -2)).slice(0,3).map(b=>b.textContent.trim().slice(0,15))}));
  assert.ok(info.scroll<=info.width+2,`${where} 整页横向溢出 ${JSON.stringify(info)}`);
  assert.deepEqual(info.badControls,[],`${where} 控件越过屏幕边缘`);
  return info;
}
(async()=>{
  let browser;
  try{
    const base=await ready;
    browser=await chromium.launch(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});
    for(const size of sizes){
      const context=await browser.newContext({viewport:{width:size.width,height:size.height},deviceScaleFactor:size.dpr});
      const page=await context.newPage(),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(()=>localStorage.setItem('xrpg-theme','light'));
      await page.goto(base);
      await page.locator('.portal-world').waitFor();
      await page.evaluate(()=>document.querySelectorAll('.cer-ok').forEach(b=>b.click()));
      assert.equal(await page.locator('.portal-landscape.portal-day').evaluate(img=>img.naturalWidth),3840);
      const nativeWidth=size.name==='portrait'?2880:3840;
      assert.ok(nativeWidth>=size.width*size.dpr,`${size.name}地图图像不足以覆盖设备像素`);
      assert.equal(await page.locator('[data-portal-go]').count(),17);
      await shape(page,size.name+'总览');
      const portrait=await page.evaluate(()=>matchMedia('(orientation:portrait)').matches);
      assert.equal(portrait,size.name==='portrait');
      if(portrait){
        assert.equal(await page.locator('.portal-landscape.portal-day').evaluate(el=>getComputedStyle(el).display),'none');
        if(!only)assert.match(await page.locator('.portal-stage').evaluate(el=>getComputedStyle(el,'::before').backgroundImage),/academy-portrait-4k/);
      }
      if(process.argv.includes('--shots')){fs.mkdirSync(artDir,{recursive:true});await page.screenshot({path:path.join(artDir,size.name+'-home.png')});}
      for(const [key,[subject,hall]] of Object.entries(subjects).filter(([k])=>!only||k===only)){
        await home(page);
        await page.locator(`[data-portal-go="subject-${key}"]`).click();
        await page.waitForFunction(name=>VIEW==='train'&&STUDY_REGIONS.title()===name,subject);
        await page.locator('.academy-room-title').filter({hasText:hall}).waitFor();
        assert.equal(await page.locator('.academy-room-title').textContent(),hall);
        assert.equal(await page.locator('.study-region-heading h2').textContent(),subject);
        assert.match((await shape(page,size.name+' '+hall)).background,new RegExp(`train-${key}\\.webp`));
        if(size.name==='desktop'){
          const realSize=await page.evaluate(key=>new Promise((resolve,reject)=>{
            const image=new Image();image.onload=()=>resolve([image.naturalWidth,image.naturalHeight]);
            image.onerror=reject;image.src=`assets/beauty/page/train-${key}.webp`;
          }),key);
          assert.deepEqual(realSize,[3840,2880],hall+'网页仍读到旧楼内图');
        }
        await page.locator('.fx-region-work').waitFor();
        if(key==='minfa'&&process.argv.includes('--shots'))await page.screenshot({path:path.join(artDir,size.name+'-minfa.png')});
        assert.ok(await page.locator('.academy-room-back').isVisible(),hall+'返回入口不可见');
        await page.locator('.academy-room-back').click();
        await page.locator('.portal-world').waitFor();
      }
      for(const [id,view] of Object.entries({dwelling:'dwelling',train:'train',skeleton:'skeleton',bank:'bank',notes:'notes',contest:'contest',log:'log',tianji:'tianji'})){
        await home(page);
        await page.locator(`[data-portal-go="${id}"]`).click();
        await page.waitForFunction(target=>VIEW===target,view);
        assert.ok((await page.locator('#view').innerText()).trim().length>8,id+'页面空白');
        await shape(page,size.name+' '+id);
      }
      await home(page);
      await page.evaluate(()=>{localStorage.setItem('xrpg-theme','dark');document.documentElement.dataset.theme='dark';});
      await page.locator('[data-portal-go="subject-minfa"]').click();
      await page.waitForFunction(()=>STUDY_REGIONS.title()==='民法');
      await page.locator('.academy-room-title').filter({hasText:'契约馆'}).waitFor();
      assert.match((await shape(page,size.name+'暗色民法')).background,/train-minfa\.webp/);
      if(process.argv.includes('--shots'))await page.screenshot({path:path.join(artDir,size.name+'-minfa-dark.png')});
      assert.deepEqual(errors,[],`${size.name}脚本错误`);
      await context.close();
    }
    console.log('学院4K与八科/公共入口真实点击通过：1280×860、800×1280、1280×800（DPR2），明暗主题');
  }finally{if(browser)await browser.close();srv.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
