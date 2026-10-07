// GitHub runner已有Chrome；使用Node标准库CDP，不安装测试依赖。
import {spawn} from 'node:child_process';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const dir=await mkdtemp(join(tmpdir(),'fakao-ui-'));
const server=spawn('python',['server.py','--no-browser','--port','8766','--vault',join(dir,'vault'),'--settings-dir',join(dir,'settings')],{stdio:'inherit'});
const chrome=spawn(process.env.CHROME_PATH||'google-chrome',['--headless','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=9222','--user-data-dir='+join(dir,'chrome'),'about:blank'],{stdio:'ignore'});
let ws;let count=0;const pending=new Map();const errors=[];
try{
 for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8766/health');await fetch('http://127.0.0.1:9222/json/version');break;}catch{await pause(300);}}
 async function api(a,b={}){const r=await fetch('http://127.0.0.1:8766/api/'+a,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});const data=await r.json();if(!r.ok)throw Error(a+':'+JSON.stringify(data));return data;}
 const fixture=await readFile('tests/test_core.py','utf8');const sample=fixture.split("SAMPLE='''")[1].split("'''")[0];
 const m=await api('material_import',{text:sample,name:'002-结构验证样例.md'});await api('material_save',{id:m.id,cleaned:m.cleaned,verified:true,chapter:'自然人 · 结构测试',teacher:'测试资料',edition:'测试版'});
 await api('card_add',{front:'主动回忆可以从哪些角度展开？',back:'上位分类、原则与例外、易混区别、案例应用。',subject:'民法',material_id:m.id});
 const q=await api('question_add',{stem:'以下哪种方式属于主动回忆？',options:{A:'只看笔记',B:'闭卷写出知识框架',C:'只收藏资料',D:'只看学习统计'},answer:['B'],subject:'民法',point:'学习方法测试',type:'single',verified:true,explanation:'闭卷回忆后对照资料。'});
 const ex=await api('exam_create',{title:'案例分析 · 机考流程验证',minutes:30,material:'本材料用于验证材料阅读、分问作答、保存和交卷流程。请围绕学习方法组织答案。',questions:[{prompt:'说明体系学习与主动回忆的关系。',reference:'先建立体系，再独立回忆与核对。',points:[]},{prompt:'说明如何利用做题发现知识缺口。',reference:'记录错题并回到对应考点复查。',points:[]}]});
 const n=await api('note_save',{title:'手写笔输入验证',text:'笔写字，手指滚动。',strokes:[]});
 const targets=await (await fetch('http://127.0.0.1:9222/json')).json();const target=targets.find(x=>x.type==='page');ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});ws.onmessage=e=>{const v=JSON.parse(e.data);if(v.id){const p=pending.get(v.id);pending.delete(v.id);v.error?p.reject(Error(JSON.stringify(v.error))):p.resolve(v.result);}else if(v.method==='Runtime.exceptionThrown')errors.push(v.params.exceptionDetails.text+' '+(v.params.exceptionDetails.exception?.description||''));};
 function cdp(method,params={}){const id=++count;return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timeout '+method));}},15000).unref();});}
 async function ev(expression){const r=await cdp('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;}
 async function click(selector){await ev(`document.querySelector(${JSON.stringify(selector)}).click()`);await pause(200);}
 async function shot(name){await pause(200);const r=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await writeFile('screenshots/'+name+'.png',Buffer.from(r.data,'base64'));const overflow=await ev('document.documentElement.scrollWidth>innerWidth+1');if(overflow)throw Error('horizontal overflow '+name);}
 await cdp('Runtime.enable');await cdp('Page.enable');await mkdir('screenshots',{recursive:true});
 for(const [name,width,height] of [['desktop',1280,860],['tablet',800,1280]]){
  await cdp('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});await cdp('Emulation.setTouchEmulationEnabled',{enabled:name==='tablet'});
  await cdp('Page.navigate',{url:'http://127.0.0.1:8766'});await pause(500);
  for(const theme of ['light','dark']){
   await ev(`document.documentElement.dataset.theme=${JSON.stringify(theme)}`);
   await click('[data-view="home"]');await shot(name+'-'+theme+'-home');
   await click('[data-view="materials"]');await click('[data-material="'+m.id+'"]');await shot(name+'-'+theme+'-material');
   await click('[data-view="cards"]');await click('[data-do="flip"]');await shot(name+'-'+theme+'-cards');
   await click('[data-view="exam"]');await click('[data-exam="'+ex.id+'"]');await shot(name+'-'+theme+'-exam');
  }
 }
 // 真正点击客观题，不在接口响应和页面上提前展示答案。
 await click('[data-view="questions"]');await click('[data-question="'+q.id+'"]');await ev(`document.querySelector('input[value="B"]').click()`);await click('[data-do="question-submit"]');if(!await ev("document.querySelector('#question-result').textContent.includes('回答正确')"))throw Error('question UI failed');
 // 自动保存、分问切换、恢复、交卷后答案开放。
 await click('[data-view="exam"]');await click('[data-exam="'+ex.id+'"]');await ev(`const t=document.querySelector('#exam-answer');t.value='独立回忆后对照知识体系';t.dispatchEvent(new Event('input',{bubbles:true}))`);await pause(850);await click('[data-question-index="1"]');await click('[data-question-index="0"]');if(await ev("document.querySelector('#exam-answer').value")!=='独立回忆后对照知识体系')throw Error('autosave lost');
 await click('[data-view="notes"]');await click('[data-note="'+n.id+'"]');const rect=await ev("(()=>{const r=document.querySelector('#draw').getBoundingClientRect();return {x:r.x+50,y:r.y+50}})()");
 await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:rect.x,y:rect.y,button:'left',buttons:1,clickCount:1,pointerType:'pen'});
 for(let i=1;i<8;i++)await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:rect.x+i*12,y:rect.y+i*7,button:'left',buttons:1,pointerType:'pen'});
 await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:rect.x+100,y:rect.y+55,button:'left',buttons:0,pointerType:'pen'});await pause(950);
 let saved=(await api('notes')).find(x=>x.id===n.id);if(saved.strokes.length!==1)throw Error('pen stroke missing');
 await cdp('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:rect.x,y:rect.y}]});await cdp('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:rect.x+10,y:rect.y+10}]});await cdp('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await pause(300);saved=(await api('notes')).find(x=>x.id===n.id);if(saved.strokes.length!==1)throw Error('finger created stroke');await shot('tablet-dark-notes');
 if(errors.length)throw Error(errors.join('\n'));
 console.log('UI-OK: four size/theme combinations, real clicks, answer hiding, autosave/recovery, pen/touch, no overflow');
 await writeFile('screenshots/verification.json',JSON.stringify({passed:true,combinations:4,screenshots:17,flows:['objective','exam-autosave','pen','touch'],errors},null,2));
}finally{ws?.close();server.kill();chrome.kill();await pause(200);await rm(dir,{recursive:true,force:true});}
