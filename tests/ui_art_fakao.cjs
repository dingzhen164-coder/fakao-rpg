// 法考场景图接入检查：试炼塔整图 + 选择大厅 + 营地/书馆/手记背景，昼夜与黄昏回退
const { chromium } = require('playwright'); const { spawn } = require('node:child_process');
(async()=>{
  const srv=spawn('python3',['tests/ui_layout_server.py'],{env:{...process.env,PYTHONIOENCODING:'utf-8'}});
  const base=await new Promise(r=>{let t='';srv.stdout.on('data',b=>{t+=b;const m=t.match(/UI-READY (\S+)/);if(m)r(m[1]);});});
  const b=await chromium.launch(); const bad=[];
  const cases=[['bank','day','synthetic','bank-day'],['bank','night','native','bank-night'],['bank','dusk','synthetic','bank-day'],['skeleton','night','native','skeleton-night'],['notes','day','synthetic','notes-day']];
  for(const [pg,ph,relight,art] of cases){
    const p=await b.newPage({viewport:{width:1280,height:860}}); const errs=[]; p.on('pageerror',e=>errs.push(e.message));
    await p.addInitScript(t=>{try{localStorage.setItem('scene-time',t);localStorage.setItem('xrpg-theme',t==='night'?'dark':'light');}catch(e){}},ph);
    await p.goto(base); await p.waitForTimeout(1500); await p.evaluate(()=>document.querySelectorAll('.cer-ok').forEach(x=>x.click()));
    await p.evaluate(v=>go(v),pg); await p.waitForTimeout(2200);
    const i=await p.evaluate(()=>({art:getComputedStyle(document.body).getPropertyValue('--ds-page-art'),relight:document.body.dataset.sceneRelight,gates:document.querySelectorAll('.th-painted-gate').length,contest:!!document.querySelector('[data-th-contest]')}));
    if(!i.art.includes(art+'.webp'))bad.push(`${pg}/${ph} 背景应为 ${art}: ${i.art}`);
    if(i.relight!==relight)bad.push(`${pg}/${ph} relight 应为 ${relight}: ${i.relight}`);
    if(pg==='bank'&&(i.gates!==2||!i.contest))bad.push(`${pg}/${ph} 试炼塔应有 2 个山门与模考入口: ${JSON.stringify(i)}`);
    if(errs.length)bad.push(`${pg}/${ph} 脚本报错 ${errs[0]}`);
    await p.close();
  }
  await b.close(); srv.kill();
  if(bad.length){console.error(bad.join('\n'));process.exit(1);}
  console.log('法考场景图接入通过：试炼塔整图+双山门+模考入口，营地/书馆/手记昼夜与黄昏回退');
})();
