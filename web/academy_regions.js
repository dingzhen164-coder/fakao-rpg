/* 法考八座学科楼的名称、缩略画面与地图直达入口。
 * 数据仍使用 study_regions.js 的科目ID、卡片和导图；app.js 在地图地点被点击时调用 select(科目名)。
 * 只改法考显示层，旧资料、学习进度和奖励均不迁移。 */
(() => {
  'use strict';
  const rooms={
    '民法':{hall:'契约馆',key:'minfa',hint:'契约、平等与日常生活'},
    '刑法':{hall:'审判堡',key:'xingfa',hint:'责任、公平与保护'},
    '民诉':{hall:'衡序厅',key:'minsu',hint:'平等、调解与程序'},
    '刑诉':{hall:'真相塔',key:'xingsu',hint:'证据、调查与程序保障'},
    '行政法':{hall:'律令宫',key:'xingzheng',hint:'公共服务与权力约束'},
    '商经知':{hall:'创艺坊',key:'shangjing',hint:'商贸、市场与知识创造'},
    '三国法':{hall:'万国馆',key:'sanguo',hint:'国际条约与交流'},
    '理论法':{hall:'星穹馆',key:'lilun',hint:'法理、宪法与职业伦理'}
  };
  const base=window.STUDY_REGIONS;
  if(!base)return;
  const originalSelect=base.select,originalBind=base.bind;
  const boards=()=>{
    const tree=typeof DASH!=='undefined'&&DASH?DASH.tree:[];
    const names=[...new Set((tree||[]).map(b=>b.board))];
    return names.length?names:Object.keys(rooms);
  };
  base.select=(id)=>{
    const index=boards().indexOf(id);
    originalSelect(index<0?id:'board-'+index);
  };
  base.bind=(root)=>{
    originalBind(root);
    const heading=root.querySelector('.study-regions-heading');
    if(heading){
      const small=heading.querySelector('.small'),p=heading.querySelector('p');
      if(small)small.textContent='八座学科楼 · 自由研习';
      if(p)p.textContent='走进学科楼，阅读卷轴、复习卡片与法阵图。';
      root.querySelectorAll('[data-study-region]').forEach((button,index)=>{
        const name=boards()[index],room=rooms[name];if(!room)return;
        button.dataset.academySubject=room.key;
        const copy=button.querySelector('.study-region-copy');
        if(copy){const title=copy.querySelector('b'),subtitle=copy.querySelector('span'),hint=copy.querySelector('small');
          if(title)title.textContent=room.hall;if(subtitle)subtitle.textContent=name;if(hint)hint.textContent=room.hint;}
        // 训练/外观/五脉里用户放过的分区图优先于随包缩略图。
        const symbol=button.querySelector('.study-region-symbol');
        if(symbol){
          const img=document.createElement('img');
          img.className='study-region-image';img.src='assets/academy/rooms/thumb-'+room.key+'.webp';
          img.alt='';img.loading='lazy';img.dataset.regionImage=String(index);
          symbol.replaceWith(img);
        }
      });
    }
    const detail=root.querySelector('.study-region-heading');
    if(detail){
      const subject=base.title(),room=rooms[subject];
      if(room){
        detail.dataset.academySubject=room.key;
        const title=detail.querySelector('h2');
        if(title){
          const roomTitle=document.createElement('strong');roomTitle.className='academy-room-title';
          roomTitle.textContent=room.hall;title.before(roomTitle);
        }
        const sub=document.createElement('small');sub.textContent='法考研习';detail.append(sub);
        const back=document.createElement('button');back.className='ghost academy-room-back';
        back.textContent='← 学院总览';back.onclick=()=>{originalSelect('');go('home');};
        detail.prepend(back);
      }
    }
  };
  window.ACADEMY_ROOMS=rooms;
})();
