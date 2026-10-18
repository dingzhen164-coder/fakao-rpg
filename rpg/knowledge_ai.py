"""典籍索引的 AI 辅助（都是用户点一下才调用一次，不做后台自动请求）：
- ai_locate：「请 AI 帮忙定位」。只把小节目录（路径和标题，不含笔记正文）交给 AI，挑出相关小节；结果固定在这道题上（以后解惑也用），
  同一道题不重复请求。
- note：解惑后「记入批注」。判断要不要补一条自己的批注，要补就起草，存成待审建议，用户采纳后才写入。
AI 输出是 JSON，程序校验（编号必须在目录里、路径与动作合法）后才使用；校验不过重试一次，仍失败就不保存。
"""
import hashlib

from . import ai, annotations, knowledge, prompts


class AIUnavailable(annotations.AnnError):
    pass


def _call(messages, **kw):
    if not ai.available():
        raise AIUnavailable("还没有填写 AI 的 API key（设置里填写后才能用）")
    last = None
    for _ in range(2):
        try:
            r = ai.chat_json(messages, **kw)
            if isinstance(r, dict):
                return r
        except ai.AIError as e:
            last = e
    raise annotations.AnnError("AI 没有给出可用的结果：%s" % (last or "格式不对"))


def ai_locate(paths, board, name, q):
    if knowledge.notes_root(paths, name) is None:
        raise annotations.AnnError("这个科目没有笔记文件夹可以定位")
    pinned = knowledge._pins(paths, board).get(knowledge._qkey(q))
    if pinned:
        return knowledge.locate(paths, board, name, q), "这道题已经固定过 AI 定位结果了"
    cat = knowledge.catalog(paths, board, name, q)
    if not cat:
        raise annotations.AnnError("笔记里还没有可定位的小节")
    r = _call(prompts.knowledge_locate(board, knowledge.query_text(q)[:3000], cat), temperature=0.1, max_tokens=800, timeout=120)
    valid = {k for k, _ in cat}
    ids = [i for i in (r.get("ids") or []) if isinstance(i, str) and i in valid][:6]
    if not ids:
        return knowledge.locate(paths, board, name, q), "AI 也没有在目录里找到对应的小节"
    knowledge.pin(paths, board, q, ids)
    return knowledge.locate(paths, board, name, q), "已按 AI 的挑选定位，并固定在这道题上"


def note(paths, board, name, q, ctx, label):
    """返回 (建议或 None, 说明)"""
    located = knowledge.locate(paths, board, name, q)["text"][:12000] if knowledge.notes_root(paths, name) else ""
    key = "note:" + hashlib.sha1((board + str(ctx.get("question")) + str(ctx.get("explain"))).encode("utf-8")).hexdigest()[:12]
    for p in annotations.proposals(paths, board):
        if p.get("key") == key:
            return p, "这道题已经有一条待审建议了"
    r = _call(prompts.ann_note(board, located, ctx), temperature=0.2, max_tokens=2000, timeout=180)
    if not r.get("needed"):
        return None, "笔记已经说清（或只是个别情况），不用补批注"
    prop = annotations.add_proposal(paths, board, r.get("summary") or "补一条批注", r.get("edits"), {"label": label}, key)
    return prop, "已生成一条待审建议"
