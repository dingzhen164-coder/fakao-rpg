/* 法考学院四季×白天/黄昏/黑夜素材选择。场景时钟与季节设置只改变背景；
 * app.js 传入同一个地图配置，地点 ID、保存坐标和学习数据均不受影响。 */
(() => {
  'use strict';
  const root=document.documentElement;
  const seasons=['spring','summer','autumn','winter'];
  let config;
  const file=(season,phase,portrait=false)=>season==='spring'&&phase==='day'?
    `assets/academy/scene/academy-${portrait?'portrait':'day'}-4k.webp`:
    `assets/academy/scene/academy-${season}-${phase}${portrait?'-portrait':''}-4k.webp`;
  function state(){
    const chosen=root.dataset.sceneSeason;
    const season=seasons.includes(chosen)?chosen:window.SCENE_FX?.season()||'spring';
    const current=root.dataset.scenePhase||window.SCENE_CLOCK?.resolve().ph||'day';
    return {season,phase:current==='night'?'night':current==='dusk'?'dusk':'day'};
  }
  // 横屏地图换了新布局（12 处极简版）后，名牌坐标是一套；只有已经做好新布局的季节才用对应季节图，其余季节先沿用春季图，
  // 等夏、秋、冬的新图做好后把季节加进这个名单即可（竖屏图仍按季节，用旧布局的竖屏坐标）。
  const NEW_LAYOUT=['spring'];
  function images(){
    const {season:real,phase}=state(),season=NEW_LAYOUT.includes(real)?real:NEW_LAYOUT[0];
    return {day:file(season,phase==='night'?'day':phase),night:file(season,'night')};
  }
  function apply(){
    const {season,phase}=state();
    root.style.setProperty('--academy-portrait-art',`url("${file(season,phase,true)}")`);
    if(config){config.images=images();window.SCENE_PORTAL?.refreshArt();}
  }
  function bind(c){config=c;apply();}
  new MutationObserver(apply).observe(root,{attributes:true,attributeFilter:['data-scene-season','data-scene-phase','data-scene-time']});
  window.ACADEMY_SCENE={images,bind,apply,file};apply();
})();
