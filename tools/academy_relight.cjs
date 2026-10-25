/* 在原生4K细绘母版上合成时段光照。参考图只参与模糊后的大尺度色温；
 * 建筑、树叶、笔触等高频像素来自母版，绝不把低分辨率构图稿放大当成成品。
 * node tools/academy_relight.cjs <母版.webp> <时段参考.png> <成品.webp> [细节权重 0..1] */
const fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path');
const {execFileSync}=require('node:child_process');
const [base,reference,dest,weight]=process.argv.slice(2);
if(!base||!reference||!dest)throw Error('需要母版、时段参考、输出路径');
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const magick=args=>execFileSync('magick',['-limit','thread','2',...args],{encoding:'utf8',maxBuffer:1024*1024});
const dimensions=file=>execFileSync('magick',['identify','-limit','thread','2','-format','%w %h',file],{encoding:'utf8'}).trim().split(' ').map(Number);
const [width,height]=dimensions(base);
if(![[3840,2880],[2880,3840]].some(s=>s[0]===width&&s[1]===height))throw Error('母版必须是学院原生4K尺寸');
fs.mkdirSync(path.dirname(dest),{recursive:true});
// 用模糊图之差改变环境光；高频纹理仍取自母版。参考构图仅作照明指导。
const defaultDetail=/(?:^|[-/])night(?:[-.])/.test(dest)?0.72:0.88;
const detail=weight===undefined?defaultDetail:Number(weight);
if(!Number.isFinite(detail)||detail<=0||detail>1)throw Error('细节权重须大于0且不超过1');
magick([base,reference,'-resize',`${width}x${height}!`,
  '(','-clone','0','-blur','0x32',')',
  '(','-clone','1','-blur','0x32',')',
  '-delete','1','-fx',`u[2]+${detail}*(u[0]-u[1])`,
  '-alpha','off','-define','webp:method=6','-quality','90',dest]);
const size=dimensions(dest),bytes=fs.statSync(dest).size;
if(size[0]!==width||size[1]!==height||bytes>12*1024*1024)throw Error(`光照成品异常：${size} ${bytes}`);
const record={method:'native-4k-base-with-low-frequency-generated-light-guide',nativeDetailWeight:detail,base:{file:base,sha256:sha(base),size:[width,height]},reference:{file:reference,sha256:sha(reference),size:dimensions(reference),role:'low-frequency-light-and-color-only'},output:{file:dest,sha256:sha(dest),size,bytes}};
fs.writeFileSync(dest+'.provenance.json',JSON.stringify(record,null,2)+'\n');
console.log(`${dest}: ${size.join('×')} ${bytes} bytes`);
