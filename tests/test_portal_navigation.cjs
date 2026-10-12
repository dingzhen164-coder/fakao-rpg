/* 场景切页必须等待手记保存，保存失败时不能离页；直接运行app.js真实导航函数。 */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const text=fs.readFileSync('web/app.js','utf8');
const start=text.indexOf('async function go(view) {'),end=text.indexOf('\ndocument.querySelectorAll("#nav a")',start);
assert.ok(start>=0&&end>start);
let release,renders=0,closed=0;
const context={VIEW:'notes',window:{NARRATIVE:{close(){closed++;}},NOTES:{flush:()=>new Promise(r=>release=r)}},
 document:{querySelectorAll:()=>[]},render:()=>renders++,setTimeout:fn=>fn()};
context.NOTES=context.window.NOTES;
vm.createContext(context);vm.runInContext(text.slice(start,end),context);
(async()=>{
 const failed=context.go('home');assert.equal(context.VIEW,'notes');assert.equal(renders,0);release(false);await failed;
 assert.equal(context.VIEW,'notes');assert.equal(renders,0);
 const success=context.go('home');assert.equal(context.VIEW,'notes');release(true);await success;
 assert.equal(context.VIEW,'home');assert.equal(renders,1);assert.equal(closed,2);
 console.log('场景切页保存保护检查通过');
})().catch(e=>{console.error(e);process.exitCode=1;});
