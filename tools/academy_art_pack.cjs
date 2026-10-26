/* 法考学院原生4K分块合成：开发工具，网页运行无需Node或ImageMagick。
 * 参考构图仅用于低频色调；成品每个像素都来自原生1024×1536重绘块。
 * 用法：node tools/academy_art_pack.cjs <academy|academy-portrait|academy-季节[-portrait]|八科英文key>。
 * 原始块与 references.json 默认放在 /workspace/generated_images/fakao-4k-source。 */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const root=path.resolve(process.env.ACADEMY_ART_SOURCE||'/workspace/generated_images/fakao-4k-source');
const repo=path.resolve(__dirname,'..'),key=process.argv[2];
const keys=['academy','academy-portrait','minfa','xingfa','minsu','xingsu','xingzheng','shangjing','sanguo','lilun'];
const seasonal=/^academy-(summer|autumn|winter)(-portrait)?$/.exec(key||'');
if(!keys.includes(key)&&!seasonal)throw Error('需要指定 academy、academy-portrait、academy-季节[-portrait] 或八科英文key');
const folder=path.join(root,key),work=path.join(folder,'pack');fs.mkdirSync(work,{recursive:true});
const refs=JSON.parse(fs.readFileSync(path.join(root,'references.json'),'utf8'));
const base=path.join(root,'..',refs[key]);
const portrait=key==='academy-portrait'||!!seasonal?.[2],W=portrait?2880:3840,H=portrait?3840:2880,PAD=16;
const cols=portrait?3:4,rows=portrait?3:2,cellW=W/cols,cellH=H/rows;
function magick(args){const argv=args[0]==='identify'?['identify','-limit','thread','2',...args.slice(1)]:['-limit','thread','2',...args];return execFileSync('magick',argv,{encoding:'utf8',maxBuffer:1024*1024});}
function size(file){return magick(['identify','-format','%w %h',file]).trim().split(' ').map(Number);}
function digest(file){return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');}
const refFull=path.join(work,'reference-full.png');
if(!fs.existsSync(refFull))magick([base,'-resize',`${W}x${H}!`,refFull]);
const canvas=path.join(work,'canvas.png');
magick(['-size',`${W}x${H}`,'xc:black','-colorspace','sRGB','-type','TrueColor','-define','png:color-type=2',canvas]);
const tiles=[];
for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){
  const source=path.join(folder,`tile-c${col}r${row}.png`);
  const x=Math.max(0,col*cellW-PAD),y=Math.max(0,row*cellH-PAD);
  const w=Math.min(W,(col+1)*cellW+PAD)-x,h=Math.min(H,(row+1)*cellH+PAD)-y;
  const native=size(source);
  if(native[0]<w||native[1]<h)throw Error(`${source} 原生尺寸不足：${native} < ${w}×${h}`);
  const index=row*cols+col,ref=path.join(work,`ref-${index}.png`),fit=path.join(work,`fit-${index}.png`),tone=path.join(work,`tone-${index}.png`),weight=path.join(work,`weight-${index}.png`),blend=path.join(work,`blend-${index}.png`);
  magick([refFull,'-crop',`${w}x${h}+${x}+${y}`,'+repage',ref]);
  magick([source,'-alpha','off','-resize',`${w}x${h}!`,fit]);
  // 大尺度色差校正只影响低频；参考图的细节不会进入成品。
  magick([fit,ref,'(','-clone','0','-blur','0x24',')','(','-clone','1','-blur','0x24',')','-delete','1','-fx','u[0]+u[2]-u[1]',tone]);
  const f=[];if(x>0)f.push('min(1,i/31)');if(x+w<W)f.push('min(1,(w-1-i)/31)');
  if(y>0)f.push('min(1,j/31)');if(y+h<H)f.push('min(1,(h-1-j)/31)');
  // -fx 的 u 是强度标量，直接乘彩色图会退成灰阶；先画权重图再逐通道相乘。
  magick(['-size',`${w}x${h}`,'xc:white','-fx',f.join('*')||'1',weight]);
  magick([tone,weight,'-compose','Multiply','-composite',blend]);
  magick([canvas,blend,'-geometry',`+${x}+${y}`,'-compose','Plus','-composite','-define','png:color-type=2',canvas]);
  tiles.push({row,col,x,y,w,h,native,sha256:digest(source)});
}
const dest=seasonal?path.join(repo,`web/assets/academy/scene/academy-${seasonal[1]}-day${portrait?'-portrait':''}-4k.webp`):key==='academy'?path.join(repo,'web/assets/academy/scene/academy-day-4k.webp'):portrait?path.join(repo,'web/assets/academy/scene/academy-portrait-4k.webp'):path.join(repo,`web/assets/beauty/page/train-${key}.webp`);
fs.mkdirSync(path.dirname(dest),{recursive:true});
magick([canvas,'-alpha','off','-define','webp:method=6','-quality','92',dest]);
const actual=size(dest),bytes=fs.statSync(dest).size;
if(actual[0]!==W||actual[1]!==H||bytes>12*1024*1024)throw Error(`成品尺寸或大小异常：${actual} ${bytes}`);
if(key!=='academy'&&!portrait&&!seasonal){
  const thumb=path.join(repo,`web/assets/academy/rooms/thumb-${key}.webp`);
  fs.mkdirSync(path.dirname(thumb),{recursive:true});
  magick([dest,'-resize','640x480^','-gravity','center','-extent','640x480','-quality','86',thumb]);
}
const record={key,target:[W,H],grid:[cols,rows],overlap:PAD,reference:{file:refs[key],sha256:digest(base),size:size(base),role:'composition-and-low-frequency-tone-only'},tiles,output:path.relative(repo,dest),bytes,sha256:digest(dest)};
fs.writeFileSync(path.join(folder,'provenance.json'),JSON.stringify(record,null,2)+'\n');
console.log(`${key}: ${actual.join('×')} ${bytes} bytes ${record.sha256}`);
