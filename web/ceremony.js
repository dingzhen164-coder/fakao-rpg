/* 大典画面：晋升、晋升试炼成功、竞技场出成绩时弹出的一整屏（法师成长记：星夜、金月与旋转法阵、城堡剪影、流星；原版是仿“觅长生”的墨色夜空、青玉山峦与云雾、
   灵鱼在空中游、落叶飘、月前一个大字，下面一条青色横幅写一段话，再是 ——◇ 小标题 ◇—— 和几行属性，最后一个橙色「确 定」）。
   全部用 SVG / CSS 画，不用图片。用法：
     CEREMONY.show({ title: "化神", subtitle: "化神初期", text: "…", stats: [["道行", "70 分"], …], tone: "jade" }) → Promise（点确定后 resolve）
     CEREMONY.realm(event)   境界提升事件 → 自动配文案
     CEREMONY.contest(info)  宗门大比出成绩 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const queue = [];
  let busy = false;

  // 每个大位阶一段话（原创，按法考修行的意思写）
  const REALM_TEXT = {
    "魔法学徒": "指尖第一次亮起微弱的魔力光芒。那些拗口的法条、绕人的构成要件，原来都是咒文的音节——你终于摸到了魔法的门槛。从今往后，每一道真题都是一次施法练习，每一次复盘都是一次冥想。",
    "初级法师": "法袍上绣上了第一枚青铜法徽。你发现自己能一口气念出民法总则的骨架、刑法的犯罪构成，案情里的关键事实会自己跳出来。客观题的及格线，你已经站上去了——根基既成，往后的魔力都将立于其上。",
    "中级法师": "魔力在体内流转得愈发圆融，几个科目的咒文开始彼此呼应：实体法的规则一动，程序法的期限与管辖便跟着浮现。题干里的陷阱、选项间的毫厘之差，你已能一眼看穿。",
    "高级法师": "你的法阵第一次能同时驱动八种元素。民刑行三大实体、三大诉讼、商经知与三国法，在你眼前铺成一张脉络分明的网。学院的长老们开始在走廊里叫出你的名字。",
    "大魔导师": "高塔顶层的门为你打开。你能凭一段案情推演出全部法律关系与可能的结局，也开始懂得那些例外与但书背后的分寸——那是法律的温度，也是你仍需敬畏的东西。",
    "法圣": "万法归一，心如止水。曾经令你夜不能寐的物权变动、共同犯罪、上诉不加刑，如今不过是掌中纹路。你站在塔顶回望来路，每一级台阶都刻着你熬过的晨昏。离封神，只差最后一步。",
    "法神·上岸者": "晋升试炼的光柱散尽，神域之门洞开。那一纸法律职业资格证书，便是你的神格。回首这一路，所有的苦修都有了意义。",
  };
  const MINOR = [
    "体内的魔力又凝实了一分，咒文咏唱得愈发流畅。小位阶的门槛悄然跨过，你知道，这是日复一日的功课换来的。",
    "一夜苦读，魔法书上又亮起一行金字。那些曾经模糊的考点，此刻变得清晰可触。经验精进，再上一星。",
    "法阵多转了一圈，便多一分沉稳。你没有停下，只是把这一层的感悟默默写进了魔法手记。",
  ];

  function stageOf(name) {
    name = String(name || "");
    const k = Object.keys(REALM_TEXT).find((x) => name.startsWith(x));
    return k || name.replace(/\s*·.*$/, "");
  }

  // 一道流星般的魔法光（原来是灵鱼，类名沿用 cer-fish）：发光的光点拖一条渐隐的尾巴
  const FISH = `<svg viewBox="0 0 220 110" class="cer-fish-svg"><defs>
      <linearGradient id="cerTail" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffd98a" stop-opacity="0"/><stop offset=".7" stop-color="#ffe9b3" stop-opacity=".55"/><stop offset="1" stop-color="#fff8e6"/></linearGradient>
      <radialGradient id="cerOrb"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="#ffe9b3"/><stop offset="1" stop-color="#b48cff" stop-opacity="0"/></radialGradient></defs>
    <path d="M182 49 Q110 50 8 78 Q110 62 182 61 Z" fill="url(#cerTail)"/>
    <circle cx="184" cy="55" r="22" fill="url(#cerOrb)"/><circle cx="184" cy="55" r="5" fill="#fff"/>
    <path d="M184 38 L186 53 L201 55 L186 57 L184 72 L182 57 L167 55 L182 53Z" fill="#fff8e6" opacity=".9"/></svg>`;

  // 一侧的城堡剪影：尖顶塔楼 + 带垛口的城墙，窗里亮着灯（原来是青玉山，类名沿用 cer-mount）
  const MOUNT = (flip) => `<svg viewBox="0 0 520 260" class="cer-mount ${flip ? "r" : "l"}" preserveAspectRatio="none"><defs>
      <linearGradient id="cerM1${flip ? "r" : "l"}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b4a8c"/><stop offset=".45" stop-color="#2a1f4a"/><stop offset="1" stop-color="#0b0818"/></linearGradient>
      <linearGradient id="cerM2${flip ? "r" : "l"}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a2d63"/><stop offset="1" stop-color="#07050f"/></linearGradient></defs>
    <path d="M0 260 L0 150 L70 120 L140 140 L220 90 L300 130 L380 110 L460 170 L520 200 L520 260 Z" fill="url(#cerM2${flip ? "r" : "l"})" opacity=".8"/>
    <path d="M0 260 L0 200 L40 190 L60 186 L60 140 L56 140 L80 88 L104 140 L100 140 L100 172 L108 172 L108 166 L116 166 L116 172 L124 172 L124 166 L132 166 L132 172 L145 172 L145 82 L140 82 L175 8 L210 82 L205 82 L205 176 L214 176 L214 170 L222 170 L222 176 L230 176 L230 170 L238 170 L238 176 L246 176 L246 170 L254 170 L254 176 L262 176 L262 170 L270 170 L270 176 L300 176 L300 122 L296 122 L320 58 L344 122 L340 122 L340 186 L400 200 L460 222 L520 240 L520 260 Z" fill="url(#cerM1${flip ? "r" : "l"})"/>
    <path d="M140 82 L175 8 L210 82 M56 140 L80 88 L104 140 M296 122 L320 58 L344 122" stroke="#e0b354" stroke-width="1.6" opacity=".55" fill="none"/>
    <g fill="#ffd98a" opacity=".9"><rect x="171" y="104" width="7" height="12" rx="3"/><rect x="171" y="136" width="7" height="12" rx="3"/>
      <rect x="77" y="156" width="6" height="10" rx="3"/><rect x="317" y="138" width="6" height="11" rx="3"/><rect x="230" y="190" width="5" height="8" rx="2"/></g></svg>`;

  function sparks(n) {
    return Array.from({ length: n }, () => {
      const a = Math.random() * Math.PI * 2, r = 46 + Math.random() * 10;
      return `<i style="left:${50 + r * Math.cos(a)}%;top:${50 + r * Math.sin(a)}%;animation-delay:${(Math.random() * 3).toFixed(2)}s"></i>`;
    }).join("");
  }
  function leaves(n) {
    return Array.from({ length: n }, () => `<b style="left:${(Math.random() * 100).toFixed(1)}%;top:${(Math.random() * 70).toFixed(1)}%;
      animation-delay:${(Math.random() * 8).toFixed(2)}s;animation-duration:${(9 + Math.random() * 8).toFixed(1)}s;--rot:${Math.round(Math.random() * 360)}deg;
      --s:${(0.6 + Math.random() * 0.8).toFixed(2)}"></b>`).join("");
  }

  function build(o) {
    const el = document.createElement("div");
    el.className = "ceremony tone-" + (o.tone || "jade");
    const title = esc(o.title || "");
    el.innerHTML = `
      <div class="cer-sky">${leaves(14)}</div>
      <div class="cer-stage">
        <div class="cer-moon"><div class="cer-circle"><img src="art/circle-dark.svg" alt=""></div><div class="cer-ring">${sparks(26)}</div></div>
        ${MOUNT(false)}${MOUNT(true)}
        <svg class="cer-ridge" viewBox="0 0 1000 120" preserveAspectRatio="none"><defs>
          <linearGradient id="cerRidge" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a76c4" stop-opacity=".5"/><stop offset=".35" stop-color="#2a1f4a" stop-opacity=".95"/><stop offset="1" stop-color="#06040d"/></linearGradient></defs>
          <path d="M0 120 L0 70 C80 40 140 64 210 52 C290 38 340 70 420 58 C470 50 520 40 560 52 C640 74 700 44 780 54 C860 64 920 46 1000 60 L1000 120 Z" fill="url(#cerRidge)"/></svg>
        <div class="cer-mist m1"></div><div class="cer-mist m2"></div><div class="cer-mist m3"></div>
        <div class="cer-fish f1">${FISH}</div><div class="cer-fish f2">${FISH}</div><div class="cer-fish f3">${FISH}</div>
        <div class="cer-title ${title.length > 2 ? "long" : ""}">${[...(o.title || "")].map((c, i) => `<span style="animation-delay:${0.25 + i * 0.22}s">${esc(c)}</span>`).join("")}</div>
      </div>
      <div class="cer-band">
        <p class="cer-text">${esc(o.text || "")}</p>
        ${o.subtitle ? `<div class="cer-sub"><i></i><span>${esc(o.subtitle)}</span><i></i></div>` : ""}
        ${(o.stats || []).length ? `<div class="cer-stats">${o.stats.map((row) => `<div>${row.map(([k, v]) => `<span><em>${esc(k)}：</em>${esc(v)}</span>`).join("")}</div>`).join("")}</div>` : ""}
      </div>
      <button class="cer-ok">${esc(o.button || "确 定")}</button>`;
    return el;
  }

  function show(o) {
    return new Promise((resolve) => { queue.push([o, resolve]); next(); });
  }
  function next() {
    if (busy || !queue.length) return;
    busy = true;
    const [o, resolve] = queue.shift();
    const el = build(o);
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add("in"));
    let done = false;
    const close = () => {
      if (done) return;
      done = true;
      document.removeEventListener("keydown", key);
      el.classList.add("out");
      setTimeout(() => { el.remove(); busy = false; resolve(); next(); }, 600);
    };
    const key = (e) => { if (e.key === "Enter" || e.key === "Escape") close(); };
    setTimeout(() => document.addEventListener("keydown", key), 800);     // 刚弹出时别被正在按的回车直接关掉
    el.querySelector(".cer-ok").onclick = close;
  }

  // 境界提升：大境界（含渡劫）配大段文案；小境界一句
  function realm(e) {
    const big = stageOf(e.big_name || e.name);
    const major = !!e.major;
    const text = e.tribulation
      ? `试炼之门一道接着一道。你稳住意志，以平日讨伐过的魔物、咏唱熟的咒文为盾，硬生生闯过了全部关卡。光芒散去，${REALM_TEXT[big] || "位阶豁然开朗。"}`
      : major ? (REALM_TEXT[big] || "瓶颈松动，魔力如潮水般涌入法阵，你踏入了新的大位阶。")
        : MINOR[Math.floor(Math.random() * MINOR.length)];
    const stats = [[["魔力", `${e.score} 分`], ["目标", `${e.target || "—"} 分`]]];
    if (e.next) stats.push([["下一阶", e.next], ...(e.from ? [["来自", e.from]] : [])]);
    return show({ title: major ? big : e.name, subtitle: e.name, text, stats, tone: e.tribulation ? "gold" : "jade" });
  }

  // 宗门大比出成绩
  function contest(s, prev) {
    const diff = s.avg != null ? s.score - s.avg : null;
    let text;
    if (diff == null) text = `第 ${s.season} 季宗门大比落幕。你交出了 ${s.score} 分的答卷——成绩已录入宗门名册，且看下回如何。`;
    else if (diff >= 10) text = `第 ${s.season} 季宗门大比，你出手便压住了全场，比同门平均高出 ${diff.toFixed(1)} 分。长老们交头接耳：此子道基扎实，假以时日，必成大器。只是山外有山，榜首仍在前方。`;
    else if (diff >= 0) text = `第 ${s.season} 季宗门大比，你稳稳胜过同门平均 ${diff.toFixed(1)} 分。不算惊艳，却也守住了自己的位置。差距藏在几个薄弱板块里——回去把心魔一只只斩了，下一季再争。`;
    else text = `第 ${s.season} 季宗门大比，你比同门平均低了 ${(-diff).toFixed(1)} 分。败一场不丢人，丢人的是不知道败在哪。去心魔录里看看这一季的错题，它们就是你下一次突破的台阶。`;
    if (prev && prev.score != null) {
      const d = s.score - prev.score;
      text += d > 0 ? `比上一季精进 ${d.toFixed(1)} 分。` : d < 0 ? `比上一季回落 ${(-d).toFixed(1)} 分，稳住心神。` : "与上一季持平。";
    }
    const mods = (s.modules || []).filter((m) => m.total);
    const best = mods.slice().sort((a, b) => b.acc - a.acc)[0], worst = mods.slice().sort((a, b) => a.acc - b.acc)[0];
    const stats = [[["得分", `${s.score}`], ["大比平均", s.avg ?? "—"], ["最高分", s.top ?? "—"]],
                   [["已击败", s.beat != null ? s.beat + "%" : "—"], ["排名", s.rank ? `${s.rank} / ${s.people || "?"}` : "—"]]];
    if (best && worst && best !== worst) stats.push([["最强", `${best.name} ${Math.round(best.acc * 100)}%`], ["最弱", `${worst.name} ${Math.round(worst.acc * 100)}%`]]);
    const tone = diff == null || diff >= 0 ? "gold" : "crimson";
    return show({ title: "大比", subtitle: `第 ${s.season} 季 · 宗门大比`, text, stats, tone });
  }

  window.CEREMONY = { show, realm, contest };
})();
