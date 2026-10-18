/* 藏经阁·典籍索引（数据来自 /api/knowledge 和 /api/annotations，见 rpg/knowledge.py、rpg/annotations.py）。
   三个页签：① 知识点——你库里笔记的小节目录（只读）；② 我的批注——每个科目可随时修改，保存即生效，解惑时和笔记一起被定位；
   ③ 解惑预览——输入一道题，看学姐解惑时会读到哪些知识点（可请 AI 帮忙定位）。
   选中的科目/页签/文件记在 localStorage knowledge-pos，没保存的草稿留在模块内存里。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const POS = "knowledge-pos";
  const num = (n) => Number(n || 0).toLocaleString("en-US");
  let DATA = [], FLAGS = { ai: false, budget: 30000 }, BOARD = "", TAB = "browse";
  let TREE = [], SECTION = null, FILTER = "";
  let ANN = { files: [], proposals: [] }, FILE = "", CUR = null, MODE = "view", DRAFT = "", HIST = null, PREVIEW = null, NOTE = "", BUSY = false;
  let PV = { question: "", chapter: "", qid: "", result: null, msg: "" };
  const board = () => DATA.find((b) => b.board === BOARD) || null;
  const savePos = () => { try { localStorage.setItem(POS, JSON.stringify({ b: BOARD, t: TAB, f: FILE })); } catch {} };
  const loadPos = () => { try { return JSON.parse(localStorage.getItem(POS) || "{}"); } catch { return {}; } };

  function md(text) {
    return String(text).split("\n").map((l) => {
      const t = esc(l);
      if (/^#{1}\s/.test(l)) return `<h3>${t.replace(/^#\s*/, "")}</h3>`;
      if (/^#{2}\s/.test(l)) return `<h4>${t.replace(/^##\s*/, "")}</h4>`;
      if (/^#{3,}\s/.test(l)) return `<h5>${t.replace(/^#+\s*/, "")}</h5>`;
      if (/^\s*[-*]\s/.test(l)) return `<div class="kn-li">${t.replace(/^\s*[-*]\s/, "")}</div>`;
      return l.trim() ? `<p>${t}</p>` : "";
    }).join("");
  }

  async function reload() {
    const v = await api("/api/knowledge");
    DATA = v.boards; FLAGS = { ai: !!v.ai, budget: v.budget || 30000 };
    const p = loadPos();
    if (!board()) { BOARD = DATA.some((b) => b.board === p.b) ? p.b : (DATA[0]?.board || ""); TAB = ["browse", "ann", "preview"].includes(p.t) ? p.t : "browse"; FILE = p.f || ""; }
    await loadTab();
  }

  async function loadAnn(keep) {
    const b = board();
    if (!b) return;
    ANN = await api("/api/annotations", { board: b.board });
    const pick = keep && ANN.files.includes(keep) ? keep : (ANN.files.includes(FILE) ? FILE : ANN.files[0] || "");
    FILE = pick; savePos();
    CUR = null;
    if (pick) { try { CUR = await api("/api/annotations/file", { board: b.board, path: pick }); } catch (e) { NOTE = e.message; } }
  }

  async function loadTab() {
    const b = board();
    if (!b) return;
    NOTE = NOTE || "";
    if (TAB === "browse" && b.notes && !TREE.length) { try { TREE = (await api("/api/knowledge/tree", { board: b.board })).files; } catch (e) { NOTE = e.message; TREE = []; } }
    if (TAB === "ann") await loadAnn(FILE);
  }

  function badge(b) {
    return `${b.notes ? "" : '<span class="tag draft" title="这个科目没有笔记文件夹">无笔记</span>'}${b.annotations ? `<span class="tag">批注 ${b.annotations}</span>` : ""}${b.pending ? `<span class="tag kn-pend">📝${b.pending}</span>` : ""}`;
  }

  // ---- ① 知识点
  function browse(b) {
    if (!b.notes) return `<p class="muted">规则里这个科目的资料「${esc(b.source || "未配置")}」没有找到笔记文件夹（应是库里的 10-科目/${esc(b.board)} 之类）。</p>`;
    const q = FILTER.trim();
    const rows = TREE.map((f) => {
      const secs = f.sections.filter((s) => !q || s.title.includes(q) || f.display.includes(q));
      if (!secs.length) return "";
      return `<details class="kn-file" ${q ? "open" : ""}><summary>${f.annotation ? "📝 " : ""}${esc(f.display)} <small>${num(f.chars)} 字 · ${f.sections.length} 节</small></summary>
        ${secs.map((s) => `<button class="kn-sec" data-kn-sec="${esc(f.key)}" data-title="${esc(s.title)}">${esc(s.title)}<small>${num(s.chars)}字${s.articles.length ? " · 第" + s.articles.join("、") + "条" : ""}</small></button>`).join("")}</details>`;
    }).join("");
    return `<div class="kn-browse"><div class="kn-tree"><input type="search" id="knFilter" placeholder="搜标题或文件名" value="${esc(FILTER)}" aria-label="搜索知识点">${rows || '<p class="muted small">没有匹配的小节。</p>'}</div>
      <div class="kn-view">${SECTION ? `<div class="small muted">${esc(SECTION.display)} › ${esc(SECTION.title)}（只读，来自你的笔记）</div><div class="kn-read">${md(SECTION.text)}</div>` : '<p class="muted">点左边的小节，在这里看原文。笔记本身不会被改动；想补充自己的理解，去「我的批注」。</p>'}</div></div>`;
  }

  // ---- ② 我的批注
  function proposals() {
    if (!ANN.proposals.length) return "";
    return `<div class="kn-props">${ANN.proposals.map((p) => `<div class="kn-prop"><div class="kn-prop-h"><b>📝 ${esc(p.summary)}</b><span class="small faint">${esc(p.created)}${p.source?.label ? " · " + esc(p.source.label) : ""}</span></div>
      ${p.edits.map((e, i) => `<label class="kn-edit ${e.done ? "done" : ""}"><input type="checkbox" data-kn-pick="${esc(p.id)}" value="${i}" ${e.done ? "disabled" : "checked"}>
        <span><b>${esc(e.path)}</b> <small>${e.action === "new" ? "新建（已有同名不覆盖）" : "追加到末尾"}${e.done ? " · 已采纳" : ""}</small>
        ${e.reason ? `<span class="small muted">${esc(e.reason)}</span>` : ""}<details><summary class="small">看内容</summary><div class="kn-diff">${md(e.text)}</div></details></span></label>`).join("")}
      <div class="kn-acts"><button class="primary small" data-kn="accept" data-pid="${esc(p.id)}">采纳勾选的</button><button class="ghost small" data-kn="dismiss" data-pid="${esc(p.id)}">忽略这条</button>
        <span class="small faint">采纳前不会写任何批注；采纳后记进变更记录，随时可回滚</span></div></div>`).join("")}</div>`;
  }

  function ann(b) {
    const hasAna = ANN.files.includes("分析套路.md");
    const chips = ANN.files.map((f) => `<button class="kn-chip ${f === FILE ? "on" : ""}" role="tab" aria-selected="${f === FILE}" data-kn-file="${esc(f)}">${esc(f)}</button>`).join("");
    const tools = `<button class="ghost small" data-kn="newfile">＋ 新建批注</button>${hasAna ? "" : '<button class="ghost small" data-kn="analysis" title="每科可选一份：遇到这科的题先按什么顺序分析">＋ 分析套路</button>'}`;
    let main = "";
    if (MODE === "edit" && CUR) {
      main = `<div class="kn-editor"><div class="small muted">正在修改 <b>${esc(FILE)}</b> · 保存后<b>下一次解惑</b>就会参考 · Ctrl+S 保存</div><textarea id="knText" spellcheck="false" aria-label="修改 ${esc(FILE)}">${esc(DRAFT)}</textarea>
        <div class="kn-acts"><button class="primary" data-kn="save" ${BUSY ? "disabled" : ""}>保存</button><button class="ghost" data-kn="cancel">取消</button><span class="small faint">${num(DRAFT.length)} 字</span></div></div>`;
    } else if (MODE === "hist" && CUR) {
      main = `<div class="kn-hist"><div class="small muted">「${esc(FILE)}」的历史版本（每次保存、改名、删除前都会留一份）</div>
        ${(HIST || []).map((v) => `<div class="kn-ver"><span>${esc(v.at)} · ${num(v.chars)} 字</span><span><button class="ghost small" data-kn="peek" data-id="${esc(v.id)}">查看</button><button class="small" data-kn="restore" data-id="${esc(v.id)}">回滚到这版</button></span></div>`).join("") || '<p class="muted small">还没有历史。</p>'}
        ${PREVIEW != null ? `<div class="kn-diff">${md(PREVIEW)}</div>` : ""}<div class="kn-acts"><button class="ghost" data-kn="back">返回</button></div></div>`;
    } else {
      main = CUR ? `<div class="kn-actbar"><button class="primary small" data-kn="edit">✎ 修改</button><button class="ghost small" data-kn="history">🕘 历史</button>
        <button class="ghost small" data-kn="rename">改名</button><button class="ghost small" data-kn="delete">🗑 删除</button></div><div class="kn-read">${md(CUR.text) || '<p class="muted">（空文件）</p>'}</div>`
        : '<p class="muted">还没有批注。点「＋ 新建批注」写下你自己的补充：易错点、对比表、口诀、案例。解惑时会和你的笔记一起被定位，并标明来源。</p>';
    }
    return `${proposals()}<div class="kn-actbar">${MODE === "view" ? tools : ""}</div>${ANN.files.length && MODE === "view" ? `<div class="kn-files" role="tablist">${chips}</div>` : ""}<div class="kn-body">${main}</div>`;
  }

  // ---- ③ 解惑预览
  function preview(b) {
    if (!b.notes) return '<p class="muted">这个科目没有笔记文件夹，没有可定位的内容。</p>';
    const chapters = [...new Set(TREE.filter((f) => !f.annotation).map((f) => f.display.split("/").slice(0, -1).join("/")).filter(Boolean))];
    const r = PV.result;
    const res = !r ? "" : `<div class="kn-res"><div class="small"><b>学姐解惑时会读：</b>${r.sections.length} 个小节 · <b>${num(r.total)} / ${num(r.budget)}</b> 字（笔记共 ${num(r.sections_total)} 小节）</div>
      ${r.found ? "" : '<div class="kn-warn small">⚠ 没有在你的笔记里找到对应知识点。解惑时学姐会明说，并按通用法理讲、提示以现行法条和教材为准。</div>'}
      ${r.sections.map((s) => `<div class="kn-hit"><b>${esc(s.display)} › ${esc(s.title)}</b><small>${num(s.chars)}字${s.truncated ? " · 过长只读入前部分" : ""}</small><div class="small muted">依据：${s.why.map(esc).join("；")}</div><div class="small faint">${esc(s.excerpt || "")}</div></div>`).join("")}
      ${r.skipped.length ? `<div class="kn-warn small">超出字数预算没有读入：${r.skipped.map((s) => esc(s.display + " › " + s.title)).join("；")}</div>` : ""}</div>`;
    return `<div class="kn-pv"><label class="small muted">粘贴一道题（题干和选项）<textarea id="knQ" rows="5" placeholder="例如：甲将房屋出卖给乙，未办理登记……">${esc(PV.question)}</textarea></label>
      <div class="kn-row"><label class="small muted">章节归属（可选）<select id="knChapter"><option value="">不指定</option>${chapters.map((c) => `<option value="${esc(c)}" ${PV.chapter === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>
      <label class="small muted">题目编号（可选，AI 定位会固定在这道题上）<input id="knQid" value="${esc(PV.qid)}" placeholder="如 2019-1-023"></label></div>
      <div class="kn-acts"><button class="primary" data-kn="locate">定位</button><button class="ghost" data-kn="aiLocate" ${FLAGS.ai ? "" : "disabled"} title="${FLAGS.ai ? "只把小节目录（路径和标题）交给 AI，不含笔记正文；调用一次 AI" : "需要先在设置里填 AI 的 API key"}">✨ 让 AI 帮忙定位</button></div>
      ${PV.msg ? `<div class="kn-note" role="status">${esc(PV.msg)}</div>` : ""}${res}</div>`;
  }

  function html() {
    if (!DATA.length) return '<div class="card"><p class="muted">还没有连接资料库。</p></div>';
    const b = board();
    const tabs = [["browse", "知识点"], ["ann", "我的批注"], ["preview", "解惑预览"]];
    return `<aside class="kn-side card" aria-label="科目">${DATA.map((x) => `<button class="kn-board ${x.board === BOARD ? "on" : ""}" data-kn-board="${esc(x.board)}"><span>${esc(x.board)}</span>${badge(x)}</button>`).join("")}</aside>
      <section class="kn-main card"><div class="kn-head"><h3>${esc(b.board)} · 典籍索引</h3><div class="kn-tabs" role="tablist">${tabs.map(([k, t]) => `<button role="tab" class="${TAB === k ? "on" : ""}" aria-selected="${TAB === k}" data-kn-tab="${k}">${t}</button>`).join("")}</div></div>
        ${NOTE ? `<div class="kn-note" role="status">${esc(NOTE)}</div>` : ""}<div class="kn-panel">${TAB === "browse" ? browse(b) : TAB === "ann" ? ann(b) : preview(b)}</div></section>`;
  }

  function paint() {
    const root = document.getElementById("knRoot");
    if (root) root.innerHTML = html();
    const t = document.getElementById("knText");
    if (t) t.oninput = () => { DRAFT = t.value; };
    const f = document.getElementById("knFilter");
    if (f) f.oninput = () => { FILTER = f.value; const pos = f.selectionStart; paint(); const g = document.getElementById("knFilter"); if (g) { g.focus(); g.setSelectionRange(pos, pos); } };
  }

  function readPv() {
    PV.question = document.getElementById("knQ")?.value ?? PV.question;
    PV.chapter = document.getElementById("knChapter")?.value ?? PV.chapter;
    PV.qid = document.getElementById("knQid")?.value ?? PV.qid;
  }

  async function act(kind, el) {
    const b = board();
    NOTE = "";
    try {
      if (kind === "locate" || kind === "aiLocate") {
        readPv();
        if (!PV.question.trim()) { PV.msg = "先粘贴一道题。"; paint(); return; }
        if (kind === "aiLocate" && !confirm("让 AI 从小节目录里挑相关的小节（只传路径和标题，不含笔记正文，调用一次 AI）。继续吗？")) return;
        PV.msg = kind === "aiLocate" ? "AI 正在挑选，请稍等……" : ""; paint();
        const r = await api(kind === "aiLocate" ? "/api/knowledge/ai_locate" : "/api/knowledge/preview", { board: b.board, question: PV.question, chapter: PV.chapter, qid: PV.qid });
        PV.result = r; PV.msg = r.message || "";
      } else if (kind === "edit") { MODE = "edit"; DRAFT = CUR.text; }
      else if (kind === "cancel") {
        if (DRAFT !== CUR.text && !confirm("有没保存的修改，确定放弃吗？")) return;
        MODE = "view"; await loadAnn(FILE);
      } else if (kind === "save") {
        BUSY = true; paint();
        try {
          const r = await api("/api/annotations/save", { board: b.board, path: FILE, text: DRAFT, base: CUR.rev });
          NOTE = r.changed ? "已保存，下一次解惑就会参考这条批注。" : "内容没有变化。"; MODE = "view"; await loadAnn(FILE); await refreshBadges();
        } finally { BUSY = false; }
      } else if (kind === "newfile") {
        const n = (prompt("批注文件名（.md，建议以章节命名，如 物权.md）", "新批注.md") || "").trim();
        if (!n) return;
        await api("/api/annotations/save", { board: b.board, path: n, text: "# " + n.replace(/\.md$/i, "").split("/").pop() + "\n\n", base: "" });
        await loadAnn(n); MODE = "edit"; DRAFT = CUR.text; await refreshBadges();
      } else if (kind === "analysis") {
        await api("/api/annotations/analysis", { board: b.board }); await loadAnn("分析套路.md"); MODE = "edit"; DRAFT = CUR.text; await refreshBadges();
      } else if (kind === "history") { HIST = (await api("/api/annotations/history", { board: b.board, path: FILE })).versions; PREVIEW = null; MODE = "hist"; }
      else if (kind === "back") { MODE = "view"; }
      else if (kind === "peek") { PREVIEW = (await api("/api/annotations/history", { board: b.board, path: FILE, id: el.dataset.id })).text; }
      else if (kind === "restore") {
        if (!confirm("回滚到这一版？现在的内容会先存进历史，可以再回来。")) return;
        await api("/api/annotations/restore", { board: b.board, path: FILE, id: el.dataset.id, base: CUR.rev }); MODE = "view"; await loadAnn(FILE); NOTE = "已回滚。";
      } else if (kind === "rename") {
        const n = (prompt("新的文件名", FILE) || "").trim();
        if (!n || n === FILE) return;
        const r = await api("/api/annotations/rename", { board: b.board, path: FILE, new_path: n, base: CUR.rev }); await loadAnn(r.path); NOTE = "已改名，原内容留在历史里。";
      } else if (kind === "delete") {
        if (!confirm(`删除「${FILE}」？内容会先存进历史，可以找回。`)) return;
        await api("/api/annotations/delete", { board: b.board, path: FILE, base: CUR.rev }); FILE = ""; await loadAnn(""); await refreshBadges(); NOTE = "已删除，内容留在历史里。";
      } else if (kind === "accept") {
        const pid = el.dataset.pid, picks = [...document.querySelectorAll(`[data-kn-pick="${pid}"]:checked`)].map((x) => Number(x.value));
        const r = await api("/api/annotations/accept", { board: b.board, id: pid, picks });
        await loadAnn(r.applied[0] || FILE); await refreshBadges();
        NOTE = (r.applied.length ? `已采纳：${r.applied.join("、")}，下一次解惑就会参考。` : "没有写入任何批注。") + (r.skipped.length ? " 跳过：" + r.skipped.join("；") : "");
      } else if (kind === "dismiss") {
        if (!confirm("忽略这条建议？")) return;
        await api("/api/annotations/dismiss", { board: b.board, id: el.dataset.pid }); await loadAnn(FILE); await refreshBadges(); NOTE = "已忽略。";
      }
    } catch (e) { NOTE = e.message || String(e); if (kind === "locate" || kind === "aiLocate") { PV.msg = NOTE; NOTE = ""; } }
    savePos(); paint();
  }

  async function refreshBadges() { try { DATA = (await api("/api/knowledge")).boards; } catch {} }

  window.KNOWLEDGE = {
    async render() {
      try { await reload(); } catch (e) { return `<div class="card"><p class="muted">读取失败：${esc(e.message)}</p></div>`; }
      return `<div class="kn-root" id="knRoot">${html()}</div>`;
    },
    bind(view) {
      const root = view?.querySelector("#knRoot");
      if (!root) return;
      paint();
      root.onclick = async (e) => {
        const bt = e.target.closest("[data-kn-board]");
        if (bt) {
          if (MODE === "edit" && DRAFT !== CUR?.text && !confirm("有没保存的修改，确定放弃吗？")) return;
          BOARD = bt.dataset.knBoard; MODE = "view"; NOTE = ""; TREE = []; SECTION = null; FILE = ""; PV.result = null; PV.msg = "";
          await loadTab(); savePos(); paint(); return;
        }
        const tb = e.target.closest("[data-kn-tab]");
        if (tb) {
          if (MODE === "edit" && DRAFT !== CUR?.text && !confirm("有没保存的修改，确定放弃吗？")) return;
          readPv(); TAB = tb.dataset.knTab; MODE = "view"; NOTE = ""; await loadTab(); savePos(); paint(); return;
        }
        const sec = e.target.closest("[data-kn-sec]");
        if (sec) { try { SECTION = await api("/api/knowledge/section", { board: BOARD, key: sec.dataset.knSec, title: sec.dataset.title }); } catch (err) { NOTE = err.message; } paint(); return; }
        const f = e.target.closest("[data-kn-file]");
        if (f) { MODE = "view"; NOTE = ""; await loadAnn(f.dataset.knFile); paint(); return; }
        const a = e.target.closest("[data-kn]");
        if (a && !a.disabled) act(a.dataset.kn, a);
      };
      root.onkeydown = (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && MODE === "edit") { e.preventDefault(); act("save"); } };
    },
  };
})();
