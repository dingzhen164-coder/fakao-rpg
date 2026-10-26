/* 汇总四季原生细绘母版与4K时段合成证据，供随包美术测试核验。
 * 读取 ACADEMY_ART_SOURCE（默认工作区生成目录）及随图光照记录，写入 academy/provenance.json。 */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const repo=path.resolve(__dirname,'..'),source=process.env.ACADEMY_ART_SOURCE||'/workspace/generated_images/fakao-4k-source';
const target=path.join(repo,'web/assets/academy/provenance.json');
const data=JSON.parse(fs.readFileSync(target,'utf8'));
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const roomKeys=['minfa','xingfa','minsu','xingsu','xingzheng','shangjing','sanguo','lilun'];
const seasons=['spring','summer','autumn','winter'],phases=['day','dusk','night'];
const scene=(season,phase,portrait)=>`web/assets/academy/scene/${season==='spring'&&phase==='day'?portrait?'academy-portrait-4k.webp':'academy-day-4k.webp':`academy-${season}-${phase}${portrait?'-portrait':''}-4k.webp`}`;
for(const season of seasons.slice(1))for(const suffix of ['', '-portrait']){
  const key=`academy-${season}${suffix}`;
  const record=JSON.parse(fs.readFileSync(path.join(source,key,'provenance.json'),'utf8'));
  if(sha(path.join(repo,record.output))!==record.sha256)throw Error(`${key} 哈希不匹配`);
  data.records[key]=record;
}
const matrix={},lighting={};
for(const season of seasons)for(const phase of phases)for(const portrait of [false,true]){
  const rel=scene(season,phase,portrait),file=path.join(repo,rel),size=fs.statSync(file).size;
  matrix[`${season}-${phase}-${portrait?'portrait':'landscape'}`]={file:rel,size:portrait?[2880,3840]:[3840,2880],bytes:size,sha256:sha(file)};
  if(phase==='day')continue;
  const side=file+'.provenance.json',record=JSON.parse(fs.readFileSync(side,'utf8'));
  if(record.output.sha256!==matrix[`${season}-${phase}-${portrait?'portrait':'landscape'}`].sha256)throw Error(`${rel} 光照记录不符`);
  lighting[rel]=record;
  fs.unlinkSync(side);
}
for(const key of roomKeys){
  const rel=`web/assets/beauty/page/train-${key}-night.webp`,file=path.join(repo,rel),side=file+'.provenance.json';
  const record=JSON.parse(fs.readFileSync(side,'utf8'));
  if(record.output.sha256!==sha(file))throw Error(`${rel} 光照记录不符`);
  lighting[rel]=record;fs.unlinkSync(side);
}
if(new Set(Object.values(matrix).map(x=>x.sha256)).size!==24)throw Error('24张学院状态图中有重复文件');
data.method='native-tiled-day-masters-with-native-4k-time-light-composites';
data.sceneMatrix=matrix;data.lighting=lighting;
fs.writeFileSync(target,JSON.stringify(data,null,2)+'\n');
console.log(`已登记 ${Object.keys(data.records).length} 张原生母版、24 张主界面状态图及 ${Object.keys(lighting).length} 张4K光照合成图`);
