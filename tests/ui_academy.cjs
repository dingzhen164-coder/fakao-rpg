/* 学院正式美术验收：三种视口真实点击八科楼与公共入口，核对背景、阅读区及高密度图像。 */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const subjects = {
  minfa:['民法','契约馆'], xingfa:['刑法','审判堡'], minsu:['民诉','衡序厅'],
  xingsu:['刑诉','真相塔'], xingzheng:['行政法','律令宫'],
  shangjing:['商经知','创艺坊'], sanguo:['三国法','万国馆'], lilun:['理论法','星穹馆']
};
const glyphs={minfa:'民',xingfa:'刑',minsu:'民訴',xingsu:'刑訴',xingzheng:'行',shangjing:'商',sanguo:'國',lilun:'理'};
const only=process.argv.find(a=>a.startsWith('--only='))?.slice(7);
const sizes = [{name:'desktop',width:1280,height:860,dpr:1},
  {name:'portrait',width:800,height:1280,dpr:1},
  {name:'landscape',width:1280,height:800,dpr:2}];
const baseDir = path.resolve(__dirname,'..');
const sceneFile=(season,phase,portrait=false)=>season==='spring'&&phase==='day'?
  portrait?'academy-portrait-4k.webp':'academy-day-4k.webp':
  `academy-${season}-${phase}${portrait?'-portrait':''}-4k.webp`;
for (const key of Object.keys(subjects).filter(k=>!only||k===only)) {
  const file=path.join(baseDir,`web/assets/beauty/page/train-${key}.webp`);
  assert.ok(fs.existsSync(file),`缺少${key}正式楼内图`);
}
const scenes=[];
for(const season of ['spring','summer','autumn','winter'])for(const phase of ['day','dusk','night'])for(const portrait of [false,true]){
  const file=sceneFile(season,phase,portrait),p=path.join(baseDir,'web/assets/academy/scene',file);
  assert.ok(fs.existsSync(p),`缺少${file}`);scenes.push(crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'));
}
assert.equal(new Set(scenes).size,24,'四季和时段主界面素材有重复文件');
for(const key of Object.keys(subjects))assert.ok(fs.existsSync(path.join(baseDir,`web/assets/beauty/page/train-${key}-night.webp`)),`缺少${key}夜景`);

const srv=spawn(process.env.PYTHON||'python3',['tests/ui_layout_server.py','--reader-fixture'],{cwd:baseDir,env:process.env});
let logs='',fixture;srv.stderr.on('data',b=>logs+=b);
const ready=new Promise((resolve,reject)=>{
  let out='';const timer=setTimeout(()=>reject(Error('测试服务未启动 '+logs)),20000);
  srv.stdout.on('data',b=>{out+=b;const f=out.match(/UI-READER (.+)\n/);if(f)fixture=JSON.parse(f[1]);const m=out.match(/UI-READY (http:\/\/\S+)/);if(m){clearTimeout(timer);resolve(m[1]);}});
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
    // 复现用户已有“冒险大厅”整页背景：它不能再顶替八座楼的专属场景。
    assert.ok(fixture?.vault,'隔离法考库未就绪');
    const generic=path.join(fixture.vault,'训练/外观/美术/子地图背景/冒险大厅.png');
    fs.mkdirSync(path.dirname(generic),{recursive:true});
    fs.writeFileSync(generic,Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5V8AAAAASUVORK5CYII=','base64'));
    browser=await chromium.launch(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{});
    for(const size of sizes){
      const context=await browser.newContext({viewport:{width:size.width,height:size.height},deviceScaleFactor:size.dpr});
      const page=await context.newPage(),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(()=>{localStorage.setItem('xrpg-theme','light');localStorage.setItem('scene-season','spring');localStorage.setItem('scene-time','day');});
      await page.goto(base);
      await page.locator('.portal-world').waitFor();
      await page.evaluate(()=>document.querySelectorAll('.cer-ok').forEach(b=>b.click()));
      assert.equal(await page.locator('.portal-landscape.portal-day').evaluate(img=>img.naturalWidth),3840);
      const nativeWidth=size.name==='portrait'?2880:3840;
      assert.ok(nativeWidth>=size.width*size.dpr,`${size.name}地图图像不足以覆盖设备像素`);
      assert.equal(await page.locator('[data-portal-go]').count(),12);
      for(const [key,glyph] of Object.entries(glyphs))assert.equal(await page.locator(`[data-portal-go="subject-${key}"] .portal-calligraphy`).textContent(),glyph);
      await shape(page,size.name+'总览');
      const portrait=await page.evaluate(()=>matchMedia('(orientation:portrait)').matches);
      assert.equal(portrait,size.name==='portrait');
      if(portrait){
        assert.equal(await page.locator('.portal-landscape.portal-day').evaluate(el=>getComputedStyle(el).display),'none');
        if(!only)assert.match(await page.locator('.portal-stage').evaluate(el=>getComputedStyle(el,'::before').backgroundImage),/academy-portrait-4k/);
      }
      else{
        // 12 处极简新地图：图片按 4:3 原比例居中（contain），名牌放进同比例 .portal-frame，名牌按图片坐标定位。
        assert.equal(await page.locator('.portal-landscape.portal-day').evaluate(el=>getComputedStyle(el).objectFit),'contain','横屏地图按原比例完整显示');
        const box=await page.locator('.portal-frame').evaluate(el=>{const r=el.getBoundingClientRect();return [r.width,r.height];});
        assert.ok(Math.abs(box[0]/box[1]-4/3)<0.02,'地图框保持4:3');
      }
      if(size.name!=='landscape')for(const season of ['spring','summer','autumn','winter'])for(const phase of ['day','dusk','night']){
        await page.evaluate(([s,p])=>{localStorage.setItem('scene-season',s);localStorage.setItem('scene-time',p);SCENE_FX.apply();},[season,phase]);
        const file=sceneFile(portrait?season:'spring',phase,portrait);      // 横屏：新布局只有春季，其余季节先沿用春季图（academy_scene.js NEW_LAYOUT）
        if(portrait){
          await page.waitForFunction(name=>getComputedStyle(document.querySelector('.portal-stage'),'::before').backgroundImage.includes(name),file);
          const img=await page.evaluate(name=>new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve([i.naturalWidth,i.naturalHeight]);i.onerror=reject;i.src='assets/academy/scene/'+name;}),file);
          assert.deepEqual(img,[2880,3840],file);
        }else{
          await page.waitForFunction(name=>document.querySelector(`.portal-${document.documentElement.dataset.sceneTime}`).getAttribute('src').includes(name),file);
          const img=page.locator(`.portal-${phase==='night'?'night':'day'}`);
          await img.evaluate(el=>el.decode());assert.equal(await img.evaluate(el=>el.naturalWidth),3840,file);
        }
        if(process.argv.includes('--shots')&&season==='autumn'&&(phase==='day'||size.name==='desktop')){
          fs.mkdirSync(artDir,{recursive:true});
          await page.screenshot({path:path.join(artDir,`autumn-${phase}-${size.name}.png`)});
        }
      }
      await page.evaluate(()=>{localStorage.setItem('scene-season','spring');localStorage.setItem('scene-time','day');SCENE_FX.apply();});
      await page.evaluate(()=>go('train'));
      await page.locator('.study-region-grid').waitFor();
      assert.ok(await page.evaluate(()=>BeautyArt.files().includes('beauty/page/train.webp')),'测试库的通用冒险大厅覆盖未载入');
      for(const [key,glyph] of Object.entries(glyphs))assert.equal(await page.locator(`[data-academy-subject="${key}"] .academy-subject-mark`).textContent(),glyph);
      if(process.argv.includes('--shots')){fs.mkdirSync(artDir,{recursive:true});await page.screenshot({path:path.join(artDir,size.name+'-subjects.png')});}
      await home(page);
      if(process.argv.includes('--shots')){fs.mkdirSync(artDir,{recursive:true});await page.screenshot({path:path.join(artDir,size.name+'-home.png')});}
      for(const [key,[subject,hall]] of Object.entries(subjects).filter(([k])=>!only||k===only)){
        await home(page);
        await page.locator(`[data-portal-go="subject-${key}"]`).click();
        await page.waitForFunction(name=>VIEW==='train'&&STUDY_REGIONS.title()===name,subject);
        await page.locator('.academy-room-title').filter({hasText:hall}).waitFor();
        assert.equal(await page.locator('.academy-room-title').textContent(),hall);
        assert.equal(await page.locator('.study-region-heading h2').textContent(),subject);
        assert.match((await shape(page,size.name+' '+hall)).background,new RegExp(`train-${key}\\.webp`));
        if(key==='minfa'){
          await page.evaluate(()=>{document.body.classList.add('has-bg');BeautyArt.mount('train');});
          assert.match((await shape(page,size.name+'全局背景下的'+hall)).background,/train-minfa\.webp/);
          await page.evaluate(()=>document.body.classList.remove('has-bg'));
        }
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
      for(const [id,view] of Object.entries({dwelling:'dwelling',skeleton:'skeleton',bank:'bank',notes:'notes',contest:'contest',log:'log'})){
        await home(page);
        if(['contest','log'].includes(id))await page.evaluate(v=>go(v),id);          // 竞技场/成长档案不再占地图：从试炼塔、营地进，这里只查页面本身
        else await page.locator(`[data-portal-go="${id}"]`).click();
        await page.waitForFunction(target=>VIEW===target,view);
        assert.ok((await page.locator('#view').innerText()).trim().length>8,id+'页面空白');
        await shape(page,size.name+' '+id);
      }
      if(size.name==='desktop'){
        await page.evaluate(()=>go('settings'));
        await page.locator('details[data-fx-group="navigation"] > summary').click();
        await page.locator('select[data-scene-season]').selectOption('winter');
        await page.locator('select[data-scene-time]').selectOption('dusk');
        await home(page);
        await page.waitForFunction(()=>document.querySelector('.portal-day')?.getAttribute('src')?.includes('academy-spring-dusk-4k.webp'));   // 冬季新布局还没做：横屏地图先沿用春季图
        assert.deepEqual(await page.evaluate(()=>[localStorage.getItem('scene-season'),localStorage.getItem('scene-time')]),['winter','dusk']);
        await page.evaluate(()=>{localStorage.setItem('scene-season','spring');localStorage.setItem('scene-time','day');SCENE_FX.apply();});
      }
      await home(page);
      await page.evaluate(()=>{localStorage.setItem('xrpg-theme','dark');localStorage.setItem('scene-time','night');document.documentElement.dataset.theme='dark';SCENE_FX.apply();});
      await page.locator('[data-portal-go="subject-minfa"]').click();
      await page.waitForFunction(()=>STUDY_REGIONS.title()==='民法');
      await page.locator('.academy-room-title').filter({hasText:'契约馆'}).waitFor();
      assert.match((await shape(page,size.name+'暗色民法')).background,/train-minfa-night\.webp/);
      if(process.argv.includes('--shots'))await page.screenshot({path:path.join(artDir,size.name+'-minfa-dark.png')});
      if(size.name==='desktop')for(const key of Object.keys(subjects).filter(k=>k!=='minfa')){
        await home(page);await page.locator(`[data-portal-go="subject-${key}"]`).click();
        await page.waitForFunction(name=>STUDY_REGIONS.title()===name,subjects[key][0]);
        await page.locator('.academy-room-title').filter({hasText:subjects[key][1]}).waitFor();
        await page.waitForFunction(k=>getComputedStyle(document.body).getPropertyValue('--ds-page-art').includes(`train-${k}-night.webp`),key);
        assert.match((await shape(page,'夜景 '+key)).background,new RegExp(`train-${key}-night\\.webp`));
      }
      assert.deepEqual(errors,[],`${size.name}脚本错误`);
      await context.close();
    }
    // 同科目专用用户图仍优先于随包图；通用大厅图不得抢占八科楼。
    const own=path.join(fixture.vault,'训练/外观/美术/子地图背景/民法.png');
    fs.writeFileSync(own,fs.readFileSync(generic));
    const custom=await browser.newPage({viewport:{width:1280,height:860}});
    await custom.addInitScript(()=>{localStorage.setItem('scene-season','spring');localStorage.setItem('scene-time','day');});
    await custom.goto(base);
    await custom.locator('[data-portal-go="subject-minfa"]').click();
    await custom.waitForFunction(()=>STUDY_REGIONS.title()==='民法');
    await custom.waitForFunction(()=>getComputedStyle(document.body).getPropertyValue('--ds-page-art').includes('train-minfa.webp'));
    assert.ok(await custom.evaluate(()=>BeautyArt.files().includes('beauty/page/train-minfa.webp')),'用户的民法专用覆盖未载入');
    assert.equal(await custom.evaluate(()=>new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img.naturalWidth);img.onerror=reject;img.src=BeautyArt.url('beauty/page/train-minfa.webp');})),1,'用户的民法覆盖未优先于随包图');
    await custom.close();
    console.log('学院24种4K取景与八科昼夜/公共入口真实点击通过：1280×860、800×1280、1280×800（DPR2），明暗主题');
  }finally{if(browser)await browser.close();srv.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
