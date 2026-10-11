/* 历年真题卷轴：导入本地Markdown、筛章节、参考练习、核验答案。
 * 调用 /api/exams/*；无答案的练习不计游戏分，AI建议必须用户确认。
 */
(() => {
  let dialog, content, data, question, timer, busy = false, epoch = 0;
  let offlinePackage = null, offlinePreview = null, batchLimit = 20, sequence = null, browseMode = false;
  let filters = { board: '', chapter: '', year: '', paper: '', classification: '', q: '', page: 0 };
  const labels = { pending: '待分类', legacy: '旧分科 · 待核对', confirmed: '章节已确认', review: '已归章 · 待复核', suggested: '有待确认建议' };
  const option = (value, text, selected) => `<option value="${esc(value)}" ${String(value) === String(selected) ? 'selected' : ''}>${esc(text)}</option>`;
  const message = text => { const el = content.querySelector('[data-message]'); if (el) el.textContent = text; };
  async function run(action) {
    if (busy) return;
    busy = true;
    content.setAttribute('aria-busy', 'true');
    content.querySelectorAll('button').forEach(b => b.disabled = true);
    try { await action(); } catch (e) { message(e.message); }
    finally { busy = false; content.removeAttribute('aria-busy'); content.querySelectorAll('button').forEach(b => b.disabled = false); if (question && sequence) { const i = sequence.ids.indexOf(question.id); content.querySelector('[data-q-prev]').disabled = i <= 0; content.querySelector('[data-q-next]').disabled = i + 1 >= sequence.total; } }
  }
  async function refresh() {
    sequence = null;
    const token = ++epoch;
    const result = await api('/api/exams/search', filters);
    if (!dialog?.open || token !== epoch) return;
    data = result;
    renderList();
  }
  function jobText() {
    const j = data.job || {};
    return j.running ? `分类中 ${j.done}/${j.total}，可继续学习` : j.error ? `本批停止：${j.error}；已完成 ${j.done}/${j.total}` : j.total ? `本批完成 ${j.done}/${j.total}` : '';
  }
  function renderList() {
    question = null;
    const s = data.stats;
    const chapters = data.chapters.filter(c => !filters.board || c.board === filters.board);
    content.innerHTML = `<div class="ex-heading"><div><div class="rune">王立法学魔法学院 · 历年卷轴</div><h2>历年真题 · 科目与章节</h2></div><button data-close aria-label="关闭历年真题">关闭</button></div>
      <p class="muted small">原卷只读。分类与练习保存在训练目录。参考解析未经核验；答案和章节均确认后，才进入正式试炼。</p>
      <div class="ex-stats">${[['原始题目', s.total], ['章节已确认', s.classified], ['答案已核验', s.verified], ['有参考解析', s.references]].map(([name, n]) => `<div><b>${n}</b><span>${name}</span></div>`).join('')}</div>
      <details class="card ex-import" ${!s.total ? 'open' : ''}><summary>📥 导入与参考解析</summary><div class="ex-tools">
        <label>原卷文件夹（相对法考库）<input id="exFolder" value="60-真题库"></label><div class="row"><button data-scan>预览导入</button><button data-import>导入 / 更新原卷</button></div>
        <p class="small muted">识别“年份-试卷一/二/三.md”；按年份、卷次、题号去重，旧分科只作为待核对记录。章节来自 10-科目 的文件夹。</p>
        <label>离线分类结果（无需 API）<input type="file" id="exOfflineFile" accept=".json,application/json"></label><div class="row"><button data-offline-adopt>预览后采用离线分类</button><button data-suggestions>查看待确认建议</button></div><p class="small muted">先选分类包中的 JSON 预览，再点击采用。保留已确认归属；多专题或证据不足的题按章显示并标记待复核。答案、解析和练习记录保持原样。</p>
        <div class="row"><button data-reference>下载并匹配 Lawyer LLaMA</button><label class="small">或上传 JSON <input type="file" id="exReferenceFile" accept=".json,application/json"></label></div>
        <p class="small muted">只作个人学习参考，遵循上游数据使用说明。首次下载需联网，之后本地可用。仅精确匹配题干及选项，保留原选项映射，不自动提取标准答案。</p>
      </div></details>
      <div class="ex-filters"><label>科目<select id="exBoard">${option('', '全部科目', filters.board)}${data.boards.map(b => option(b, b, filters.board)).join('')}</select></label>
      <label>章节<select id="exChapter">${option('', '全部章节', filters.chapter)}${chapters.map(c => option(c.id, c.subject + ' · ' + c.name, filters.chapter)).join('')}</select></label>
      <label>年份<select id="exYear">${option('', '全部年份', filters.year)}${data.years.map(y => option(y, y, filters.year)).join('')}</select></label>
      <label>卷次<select id="exPaper">${option('', '全部卷次', filters.paper)}${['试卷一', '试卷二', '试卷三'].map(p => option(p, p, filters.paper)).join('')}</select></label>
      <label>分类状态<select id="exClass">${option('', '全部状态', filters.classification)}${Object.entries(labels).map(([k, v]) => option(k, v, filters.classification)).join('')}</select></label>
      <label class="ex-keyword">关键词<input id="exQuery" value="${esc(filters.q)}" placeholder="题干、选项、题号或知识点"></label><button data-search>搜索</button></div>
      <div class="row ex-ai"><label class="small">本批 <select id="exLimit">${[20, 50, 100].map(n => option(n, n, batchLimit)).join('')}</select> 题</label><button data-classify>AI 建议章节</button><span class="muted small">只处理当前科目中尚无建议的题；已保存建议不重复请求。</span></div>
      <p data-job class="small muted ex-ai" role="status">${esc(jobText())}</p>
      <p data-message class="ex-message" role="status" aria-live="polite"></p>
      <div class="card ex-bulk"><div class="row"><button class="primary" data-confirm-all>一次采用全部章节建议（${data.confirmable.all} 题）</button><button data-confirm-filtered>采用当前筛选的章节建议（${data.confirmable.filtered} 题）</button></div><p class="small muted">批量采用跨全部分页，无需逐题勾选；保留已确认归属。仅采用现有有效章节建议，不核验答案，不调用 AI。当前筛选按上方已应用的科目、章节、年份、状态和关键词。</p></div>
      <div class="row"><b>共 ${data.total} 题</b><button data-start-sequence>开始 / 继续刷题</button><span class="spacer"></span><button data-select-page>全选本页建议</button><button data-confirm>采用勾选的章节建议</button></div>
      <div class="ex-list">${data.rows.map(q => { const c = data.chapters.find(c => c.id === q.suggestion?.chapter); return `<article class="ex-row">
        <div>${c ? `<input type="checkbox" data-confirm-id="${esc(q.id)}" aria-label="选择${esc(q.id)}的章节建议">` : ''}<button class="ex-question" data-question="${esc(q.id)}"><b>${esc(q.id)}</b><span>${esc(q.text)}</span></button></div>
        <p class="small muted">${esc(q.subject || '未分科')} · ${esc(labels[q.classification])}${q.chapter ? ' · ' + esc(data.chapters.find(c => c.id === q.chapter)?.name || q.chapter) : ''} · ${q.answer_status === 'verified' ? '答案已核验' : '答案待核验'}${q.references ? ` · 参考解析 ${q.references}` : ''}${q.warnings ? ' · 原文需核对' : ''}</p>
        ${q.suggestion ? `<div class="ex-suggestion small">建议：${esc(c ? c.subject + ' · ' + c.name : '无法确定章节')} · ${esc(q.suggestion.topic)}<br>${esc(q.suggestion.reason)}</div>` : ''}</article>`; }).join('') || '<p class="muted">没有符合筛选条件的题目。</p>'}</div>
      <div class="row ex-pagination"><button data-prev ${!data.page ? 'disabled' : ''}>上一页</button><span>${data.pages ? data.page + 1 : 0} / ${data.pages}</span><button data-next ${data.page + 1 >= data.pages ? 'disabled' : ''}>下一页</button></div>`;
    bindList();
  }
  function bindList() {
    const el = s => content.querySelector(s);
    el('[data-close]').onclick = () => dialog.close();
    el('[data-search]').onclick = () => run(async () => { filters.q = el('#exQuery').value.trim(); filters.page = 0; await refresh(); });
    el('#exQuery').onkeydown = e => { if (e.key === 'Enter') el('[data-search]').click(); };
    [['#exBoard', 'board'], ['#exChapter', 'chapter'], ['#exYear', 'year'], ['#exPaper', 'paper'], ['#exClass', 'classification']].forEach(([id, key]) => el(id).onchange = () => run(async () => { filters[key] = el(id).value; if (key === 'board') filters.chapter = ''; filters.page = 0; await refresh(); }));
    el('[data-prev]').onclick = () => run(async () => { filters.page = Math.max(0, filters.page - 1); await refresh(); });
    el('[data-next]').onclick = () => run(async () => { if (filters.page + 1 < data.pages) filters.page++; await refresh(); });
    const scan = commit => run(async () => { message('正在读取本地原卷…'); const r = await api('/api/exams/scan', { folder: el('#exFolder').value.trim(), commit }); if (commit) { await refresh(); message(`已导入 ${r.total} 题，新增 ${r.added}，原文更新 ${r.changed}。`); } else message(`预览：${r.papers} 张原卷、${r.total} 题、${r.chapters} 个章节；${r.legacy} 题有旧分科，${r.warning_questions} 题需核对原文。预览尚未写入。`); });
    el('[data-scan]').onclick = () => scan(false); el('[data-import]').onclick = () => scan(true);
    const refs = body => run(async () => { message('正在匹配参考数据，首次下载可能需要片刻…'); const r = await api('/api/exams/references', body); await refresh(); message(`读取 ${r.records} 条数据；${r.matched}/${r.total} 道题匹配参考，其中 ${r.full} 道题干与选项完整匹配。标准答案未改变。`); });
    el('[data-reference]').onclick = () => refs({ download: true });
    const offlineMessage = r => `可采用 ${r.adopted} 题；另 ${r.review} 题归章并标记待复核。保留已确认 ${r.preserved}；未找到 ${r.missing}；原文变化 ${r.changed}；未知章节 ${r.unknown_chapter}。`;
    el('#exOfflineFile').onchange = e => run(async () => {
      offlinePackage = null; offlinePreview = null;
      const f = e.target.files[0]; if (!f) return;
      if (f.size > 12 * 1024 * 1024) throw Error('分类JSON不能超过12MB');
      const pkg = JSON.parse(await f.text());
      const r = await api('/api/exams/import-classification', { package: pkg, commit: false });
      offlinePackage = pkg; offlinePreview = r; message('预览：' + offlineMessage(r) + ' 点击采用后写入训练目录。');
    });
    el('[data-offline-adopt]').onclick = () => run(async () => {
      if (!offlinePackage || !offlinePreview) throw Error('请先选择离线分类JSON，查看预览结果');
      const r = await api('/api/exams/import-classification', { package: offlinePackage, commit: true, revision: offlinePreview.revision });
      offlinePackage = null; offlinePreview = null; await refresh(); message('已导入：' + offlineMessage(r));
    });
    el('[data-suggestions]').onclick = () => run(async () => { filters.classification = 'suggested'; filters.year = ''; filters.page = 0; await refresh(); });
    el('#exLimit').onchange = () => { batchLimit = Number(el('#exLimit').value); };

    el('#exReferenceFile').onchange = async e => { const f = e.target.files[0]; if (!f) return; try { if (f.size > 12 * 1024 * 1024) throw Error('JSON文件不能超过12MB'); const rows = JSON.parse(await f.text()); if (!Array.isArray(rows)) throw Error('请选择JSON数组文件'); await refs({ name: f.name, rows }); } catch (err) { message(err.message); } };
    el('[data-classify]').onclick = () => run(async () => { const r = await api('/api/exams/classify', { board: filters.board, limit: Number(el('#exLimit').value) }); data.job = r; el('[data-job]').textContent = jobText(); });
    el('[data-select-page]').onclick = () => { const boxes = [...content.querySelectorAll('[data-confirm-id]')]; const check = boxes.some(x => !x.checked); boxes.forEach(x => x.checked = check); el('[data-select-page]').textContent = check ? '取消本页全选' : '全选本页建议'; };
    const adopt = scope => run(async () => {
      const count = data.confirmable[scope === 'all' ? 'all' : 'filtered'];
      if (!count) throw Error('该范围没有可采用的章节建议；已确认的题无需再次确认');
      const r = await api('/api/exams/confirm', { scope, filters: { ...filters }, revision: data.revision });
      filters.page = 0; await refresh(); message(`已一次采用 ${r.confirmed} 题的章节建议；答案核验状态未改变。`);
    });
    el('[data-start-sequence]').onclick = () => run(startSequence);
    el('[data-confirm-all]').onclick = () => adopt('all');
    el('[data-confirm-filtered]').onclick = () => adopt('filtered');
    el('[data-confirm]').onclick = () => run(async () => { const selected = [...content.querySelectorAll('[data-confirm-id]:checked')].map(x => data.rows.find(q => q.id === x.dataset.confirmId)); if (!selected.length) throw Error('请先勾选要确认的建议'); const r = await api('/api/exams/confirm', { items: selected.map(q => ({ id: q.id, revision: q.revision })) }); await refresh(); message(`已确认 ${r.confirmed} 道题的章节。`); });
    content.querySelectorAll('[data-question]').forEach(b => b.onclick = () => run(() => openQuestion(b.dataset.question)));
  }
  async function openQuestion(id, reveal = false) {
    ++epoch;
    if (!sequence) sequence = await api('/api/exams/sequence', filters);
    question = await api('/api/exams/detail', { id, reveal });
    if (dialog.open) renderQuestion();
  }
  function renderQuestion() {
    const q = question, shown = Array.isArray(q.references);
    const selected = q.suggestion?.chapter || q.chapter;
    const pos = sequence?.ids.indexOf(q.id) ?? -1;
    const range = [filters.board, filters.year ? filters.year + '年' : '', filters.paper].filter(Boolean).join(' · ') || '历年题目';
    content.innerHTML = `<div class="ex-heading"><button data-back>← 返回目录</button><b>${esc(q.id)}</b><button data-close>关闭</button></div>
      <div class="ex-sequence"><div class="row"><b>${esc(range)} · 第 ${pos + 1} / ${sequence?.total || 1} 题</b><span class="spacer"></span><button data-q-prev ${pos <= 0 ? 'disabled' : ''}>上一题</button><button data-q-next ${!sequence || pos + 1 >= sequence.total ? 'disabled' : ''}>下一题</button></div><p class="small muted">按本次目录顺序连续练习；选择提交后自动保存，关闭后可继续未做题。未核验答案的题只记录选择。</p></div>
      <p class="small muted">${esc(q.source_type)} · ${esc(q.kind === 'single' ? '单选' : q.kind === 'multi' ? '多选' : q.kind === 'any' ? '不定项' : '题型待核对')} · ${q.answer_status === 'verified' ? '答案已核验' : '答案待核验'}</p>
      ${q.warnings.length ? `<div class="ex-warning"><b>原文完整性提示</b>${q.warnings.map(w => `<p class="ex-prose">${esc(w)}</p>`).join('')}</div>` : ''}
      ${q.material ? `<div class="card ex-prose">${esc(q.material)}</div>` : ''}<h3 class="ex-prose">${esc(q.stem)}</h3>
      <div class="ex-options">${Object.entries(q.options).map(([k, v]) => `<label><input type="${q.kind === 'single' ? 'radio' : 'checkbox'}" name="exChoice" value="${k}" ${(q.result?.answer || q.history[q.history.length - 1]?.answer || '').includes(k) ? 'checked' : ''}><b>${k}.</b><span class="ex-prose">${esc(v)}</span></label>`).join('')}</div>
      <div class="row"><button class="primary" data-practice>提交参考练习</button><button data-reveal>查看解析与核验</button><span class="small muted">参考练习只留记录，不计经验或正式正确率。</span></div>
      <p data-message class="ex-message" role="status" aria-live="polite">${q.result ? esc(q.result.ok === null ? `已记录选择 ${q.result.answer}；答案未核验，不判对错。` : `选择 ${q.result.answer}，${q.result.ok ? '正确' : '错误'}；已核验答案 ${q.answer}。`) : ''}</p>
      ${shown ? `<div class="card"><h3>答案与参考解析</h3><p>${q.answer ? `已核验答案：<b>${esc(q.answer)}</b><br>来源：${esc(q.answer_source)}` : '尚无已核验答案。'}</p>
        ${q.analysis ? `<p class="small muted">${q.analysis_status === 'verified' ? '用户已核验解析' : '参考解析 · 未核验'}</p><div class="ex-prose">${esc(q.analysis)}</div>` : ''}
        ${q.references.map(r => `<details><summary>${esc(r.source)} · ${r.match === 'full' ? '题干与选项匹配' : '仅题干匹配'}</summary><p class="small muted">${esc(r.dataset)} 第 ${r.row + 1} 条；${r.match === 'full' ? '原数据→本题选项：' + Object.entries(r.option_map).map(([a, b]) => a + '→' + b).join('，') : '没有完整选项，不能据此确定答案。'}</p><p class="ex-prose">${esc(r.text)}</p></details>`).join('') || '<p class="muted small">暂无匹配的 Lawyer LLaMA 参考解析。</p>'}</div>` : ''}
      <details class="card" open><summary>科目与章节核对</summary>${q.suggestion ? `<p class="small muted">分类建议依据：${esc(q.suggestion.reason)}</p>` : q.classification_source ? `<p class="small muted">${esc(q.classification_source.method)}：${esc(q.classification_source.reason)}</p>` : ''}<p class="small muted">旧分科：${esc(q.legacy_subject || '未分类')}；选择章节并保存，即确认该归属。</p>
      <label>章节<select id="exEditChapter">${option('', '请选择章节', selected)}${data.chapters.map(c => option(c.id, c.subject + ' · ' + c.name, selected)).join('')}</select></label><label>知识点<input id="exEditTopic" value="${esc(q.suggestion?.topic || q.topic)}"></label><button data-save-class>确认章节</button></details>
      ${shown ? `<details class="card"><summary>核验并补充答案</summary><p class="small muted">依据教材、答案表或法条核对后保存；GPT输出保持参考身份。原文有提示时，请先核对完整题目。</p>
      <div class="ex-filters"><label>答案字母<input id="exAnswer" value="${esc(q.answer)}" placeholder="例如 A 或 ACD" maxlength="4"></label><label>题型<select id="exKind">${option('', '请选择题型', q.kind)}${[['single', '单选'], ['multi', '多选'], ['any', '不定项']].map(([k, v]) => option(k, v, q.kind)).join('')}</select></label></div>
      <label>核对来源<input id="exAnswerSource" value="${esc(q.answer_source)}" placeholder="教材版本、页码 / 答案表 / 法条"></label><label>补充解析<textarea id="exAnalysis" rows="5">${esc(q.analysis)}</textarea></label>
      ${q.warnings.length ? '<label class="row"><input type="checkbox" id="exTextChecked">已核对原卷题干、选项与材料</label>' : ''}<label class="row"><input type="checkbox" id="exAnalysisChecked" ${q.analysis_status === 'verified' ? 'checked' : ''}>补充解析也已核验</label><button data-save-answer>保存已核验答案</button></details>` : ''}
      ${q.history.length ? `<details class="card"><summary>参考练习记录 · ${q.history.length}</summary>${q.history.slice(-10).reverse().map(h => `<p class="small">${esc(h.date.slice(0, 16).replace('T', ' '))} · ${esc(h.answer)} · ${h.ok === null ? '未判分' : h.ok ? '正确' : '错误'}</p>`).join('')}</details>` : ''}`;
    const el = s => content.querySelector(s);
    el('[data-close]').onclick = () => dialog.close();
    el('[data-back]').onclick = () => run(refresh);
    const next = delta => run(async () => { const index = sequence.ids.indexOf(q.id) + delta; if (index >= 0 && index < sequence.total) await openQuestion(sequence.ids[index]); });
    el('[data-q-prev]').onclick = () => next(-1); el('[data-q-next]').onclick = () => next(1);
    el('[data-reveal]').onclick = () => run(() => openQuestion(q.id, true));
    el('[data-practice]').onclick = () => run(async () => { const answer = [...content.querySelectorAll('[name=exChoice]:checked')].map(e => e.value).join(''); question = await api('/api/exams/practice', { id: q.id, answer }); renderQuestion(); });
    el('[data-save-class]').onclick = () => run(async () => { if (!el('#exEditChapter').value) throw Error('请选择章节'); await api('/api/exams/edit', { id: q.id, revision: q.revision, chapter: el('#exEditChapter').value, topic: el('#exEditTopic').value }); await openQuestion(q.id, shown); message('章节已确认。'); });
    if (shown) el('[data-save-answer]').onclick = () => run(async () => { await api('/api/exams/edit', { id: q.id, revision: q.revision, answer: el('#exAnswer').value, kind: el('#exKind').value, answer_source: el('#exAnswerSource').value, analysis: el('#exAnalysis').value, analysis_checked: el('#exAnalysisChecked').checked, text_checked: !!el('#exTextChecked')?.checked }); await openQuestion(q.id, true); message('答案已核验保存；章节确认后可在正式试炼中使用。'); });
  }
  async function startSequence() {
    sequence = await api('/api/exams/sequence', filters);
    if (!sequence.total) throw Error('当前范围没有题目，请调整筛选或导入原卷');
    await openQuestion(sequence.ids[sequence.start]);
  }
  async function open(options = {}) {
    if (dialog?.open) return;
    filters = { board: '', chapter: '', year: '', paper: '', classification: '', q: '', page: 0, ...options };
    delete filters.id; delete filters.practice; delete filters.browse;
    browseMode = !!(options.browse || options.practice || options.id); sequence = null;
    dialog = document.createElement('dialog'); dialog.className = 'ex-dialog' + (browseMode ? ' ex-reading' : ''); dialog.setAttribute('aria-label', '历年真题卷轴');
    content = document.createElement('div'); content.className = 'ex-content'; dialog.append(content); document.body.append(dialog);
    content.innerHTML = '<div class="row"><h2>正在读取真题目录…</h2><button data-close>关闭</button></div><p data-message role="status"></p>';
    content.querySelector('[data-close]').onclick = () => dialog.close();
    dialog.addEventListener('close', () => { ++epoch; clearInterval(timer); dialog.remove(); render(); });
    dialog.showModal();
    try { await refresh(); if (options.id) await openQuestion(options.id); else if (options.practice) await startSequence(); } catch (e) { message(e.message); }
    timer = setInterval(async () => { if (!dialog.open || busy || !data?.job?.running) return; try { const r = await api('/api/exams/search', filters); data.job = r.job; if (!question) { if (!r.job.running) { data = r; renderList(); } else content.querySelector('[data-job]').textContent = jobText(); } } catch (e) { message(e.message); } }, 2500);
  }
  const marks = { 民法: '⚖', 刑法: '⚔', 民诉: '✦', 刑诉: '♜', 行政法: '♛', 商经知: '◇', 三国法: '☉', 理论法: '✧' };
  async function shelfHtml(mode = 'library') {
    const d = await api('/api/exams/overview', {});
    const adventure = mode === 'adventure';
    const preview = (rows, attrs) => rows.map(q => `<button class="ex-preview" ${attrs} data-ex-id="${esc(q.id)}"><b>${esc(q.id)}</b><span>${esc(q.text)}</span><i>打开题目 →</i></button>`).join('');
    const boards = d.boards.map((b, i) => {
      const attrs = b.board === '待分类' ? 'data-ex-unclassified="1"' : `data-ex-board="${esc(b.board)}"`;
      return `<details class="ex-scroll ${!b.total ? 'ex-empty-scroll' : ''}" style="--scroll-hue:${[38, 9, 190, 272, 219, 110, 170, 306][i % 8]};--scroll-delay:${i * .25}s">
        <summary><span class="ex-scroll-crest" aria-hidden="true">${marks[b.board] || '✧'}</span><span class="ex-scroll-title">${esc(b.board)}<small>王立学院 · 法典卷轴</small></span><span class="ex-scroll-number">${b.total}<small>道题</small></span><span class="ex-scroll-hint">点击展开</span></summary>
        <div class="ex-scroll-inside"><div class="row"><b>${esc(b.board)} · ${b.total} 道题</b><span class="muted small">已练 ${b.answered} · 答案已核验 ${b.verified}</span><span class="spacer"></span><button ${attrs} data-ex-browse>查看全部题目</button><button class="primary" ${attrs} data-ex-practice>开始 / 继续刷题</button></div>
          ${b.chapters.length ? `<div class="ex-scroll-chapters">${b.chapters.map(c => `<button ${attrs} data-ex-chapter="${esc(c.id)}" data-ex-browse>${esc(c.subject === b.board ? c.name : c.subject + ' · ' + c.name)} <span>${c.count}</span></button>`).join('')}</div>` : ''}
          <div class="ex-scroll-previews">${preview(b.preview, attrs) || '<p class="muted">尚未导入本科题目，先导入历年原卷即可。</p>'}</div></div></details>`;
    }).join('');
    const sets = d.sets.map(p => `<details class="ex-paper-roll"><summary><span>📜 ${esc(p.label)}</span><b>${p.total} 题</b><span class="muted small">已练 ${p.answered}</span></summary><div class="ex-paper-inside"><div class="row"><button data-ex-year="${p.year}" data-ex-paper="${esc(p.paper)}" data-ex-browse>套卷题目目录</button><button class="primary" data-ex-year="${p.year}" data-ex-paper="${esc(p.paper)}" data-ex-practice>按卷顺序刷题</button></div>${preview(p.preview, `data-ex-year="${p.year}" data-ex-paper="${esc(p.paper)}"`)}</div></details>`).join('');
    return `<section class="ex-shelf" data-ex-shelf><div class="card ex-shelf-intro"><div class="row"><div><div class="rune">${adventure ? '实战 · 卷轴试炼' : '王立学院 · 真题典藏'}</div><h3>${adventure ? '⚔ 按科目 / 套卷刷题' : '📖 八科法典卷轴'}</h3><p class="small muted">共 ${d.total} 道历年题目 · ${d.sets.length} 套原卷。展开卷轴看章节和题目；答案未核验也能练习并保存选择。</p></div><span class="spacer"></span><button class="primary" data-ex-browse>全部题目 / 搜索</button>${adventure ? '' : '<button data-open-exams>导入 / 分类管理</button>'}</div></div><div class="ex-scroll-grid">${boards}</div>
      <details class="card ex-paper-shelf" ${adventure ? 'open' : ''}><summary><b>📜 历年套卷 · ${d.sets.length} 套</b><span class="small muted">按原始年份与卷次 · 跨科目完整保留</span></summary><div class="ex-paper-grid">${sets || '<p class="muted">导入原卷后，套卷会自动出现在这里。</p>'}</div></details></section>`;
  }
  function bindHub(root) {
    root.querySelectorAll('[data-open-exams]').forEach(b => b.onclick = () => open());
    root.querySelectorAll('[data-ex-browse], [data-ex-practice], [data-ex-id]').forEach(b => b.onclick = () => open({
      board: b.dataset.exBoard || '', chapter: b.dataset.exChapter || '', year: b.dataset.exYear || '',
      paper: b.dataset.exPaper || '', unclassified: !!b.dataset.exUnclassified,
      id: b.dataset.exId, practice: b.hasAttribute('data-ex-practice'), browse: true
    }));
  }
  window.EXAMS = { shelfHtml, bindHub, open };
})();
