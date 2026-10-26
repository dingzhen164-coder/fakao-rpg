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
  function images(){
    const {season,phase}=state();
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
