/* 法考随包的八科楼内背景登记给共用美术加载器。
 * 服务端注入的用户覆盖路径优先，ART_CUSTOM 不加入随包文件。 */
(() => {
  'use strict';
  const files=Array.isArray(window.ART_FILES)?window.ART_FILES:[];
  window.ART_FILES=files;
  for(const key of ['minfa','xingfa','minsu','xingsu','xingzheng','shangjing','sanguo','lilun']){
    const path=`beauty/page/train-${key}.webp`;
    if(!files.some(item=>item[0]===path))files.push([path,'academy4k']);
  }
})();
