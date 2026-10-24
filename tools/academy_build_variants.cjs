/* 从四季原生4K白天母版合成黄昏、夜晚；须先完成各季分块细绘。
 * node tools/academy_build_variants.cjs landscape|portrait
 * 光照参考保存在 /workspace/generated_images/fakao-4k-source/lighting。 */
const path=require('node:path'),fs=require('node:fs'),{execFileSync}=require('node:child_process');
const orientation=process.argv[2];
if(!['landscape','portrait'].includes(orientation))throw Error('需要 landscape 或 portrait');
const repo=path.resolve(__dirname,'..'),source=process.env.ACADEMY_ART_SOURCE||'/workspace/generated_images/fakao-4k-source';
const suffix=orientation==='portrait'?'-portrait':'';
for(const season of ['summer','autumn','winter'])for(const phase of ['dusk','night']){
  const base=path.join(repo,`web/assets/academy/scene/academy-${season}-day${suffix}-4k.webp`);
  const guide=path.join(source,`lighting/${season}-${phase}-${orientation}.png`);
  const target=path.join(repo,`web/assets/academy/scene/academy-${season}-${phase}${suffix}-4k.webp`);
  if(!fs.existsSync(base)||!fs.existsSync(guide))throw Error(`缺少原生母版或光照参考：${base} ${guide}`);
  execFileSync(process.execPath,[path.join(__dirname,'academy_relight.cjs'),base,guide,target],{stdio:'inherit'});
}
