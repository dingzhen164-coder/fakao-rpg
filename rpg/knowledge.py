"""法考知识点索引与解惑定位：先从已有笔记里找到这道题对应的知识点，再分析解答。

法考没有“一个 skill”，资料是用户库里 10-科目/<科目>/ 的笔记（只读）。旧逻辑把整科笔记按路径顺序读到 6 万字为止，
读到什么全看文件排序；现在改成：
1. 程序本地给笔记建索引（不调用 AI）：按标题切成小节，记下路径、标题层级、法条号、关键词，存 训练/知识点索引/<科目>.json，
   笔记改了只重建改过的文件（比对修改时间和大小）。笔记本身始终只读。
2. 解惑时按这道题定位小节：已确认的章节归属（题库里 chapter = 章节文件夹的相对路径）> 题干/选项/解析里的法条号 >
   关键词（标题权重更高）> 「我的批注」（用户自己写的，加分）> 已固定的 AI 定位结果。只取相关小节，在字数预算内按分数从高到低读入；
   过长的小节明说“只读入前 N 字”，超出预算的列在“未读入”，不悄悄截断。
3. 一个相关小节都没找到时明说“没有找到对应知识点”，让学姐按通用法理讲并提示以现行法和教材为准，不拿别的内容冒充笔记。
4. 每个科目可选一份「分析套路.md」（我的批注里），有就优先参考。
程序算分、判分不读这里；定位结果只用于讲解。
"""
import hashlib
import json
import math
import os
import re
import tempfile
import time

from . import annotations, vault

INDEX_DIR = "知识点索引"
BUDGET = 30000            # 给学姐的资料总预算（字）
SECTION_LIMIT = 6000      # 单个小节最多读入（字）
ANALYSIS_LIMIT = 4000
MIN_SCORE = 3.0
REL_CUT = 0.35            # 分数低于最高分这个比例的不要
PIN_BONUS = 20.0
CATALOG_MAX = 600         # 请 AI 定位时最多给它多少个小节标题

HEAD = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.M)
FENCE = re.compile(r"^```.*?^```[ \t]*$", re.M | re.S)
ART = re.compile(r"第\s*([0-9]+|[零〇一二三四五六七八九十百千两]+)\s*条")
CJK = re.compile(r"[一-鿿]+")
_CN = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn2int(s):
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch in _CN:
            cur = _CN[ch]
        elif ch in "十百千":
            unit = {"十": 10, "百": 100, "千": 1000}[ch]
            total += (cur or 1) * unit
            cur = 0
    return total + cur


def articles(text):
    out = set()
    for m in ART.finditer(text or ""):
        try:
            n = _cn2int(m.group(1))
        except Exception:
            continue
        if 0 < n < 5000:
            out.add(n)
    return out


def bigrams(text):
    out = set()
    for run in CJK.findall(text or ""):
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


# ---------------------------------------------------------------- 资料位置
def notes_root(paths, name):
    """科目的笔记文件夹；这个名字指向的是 skill（有 SKILL.md）或不存在则返回 None（走旧逻辑）"""
    d = vault.skill_dir(paths, name)
    if d and not (d / "SKILL.md").is_file():
        return d
    return None


def _sources(paths, board, name):
    """[(key, 绝对路径, 显示路径)]：笔记（n:相对库路径）+ 我的批注（a:相对批注目录路径）"""
    out = []
    d = notes_root(paths, name)
    if d:
        for f in vault._notes_files(d):
            rel = f.relative_to(paths.vault).as_posix()
            out.append(("n:" + rel, f, rel))
    for rel in annotations.files(paths, board):
        out.append(("a:" + rel, annotations.board_dir(paths, board) / rel, "批注/%s/%s" % (board, rel)))
    return out


def _display(sec, board):
    path = sec["f"][2:]
    return ("批注/%s/%s" % (board, path) if sec["f"].startswith("a:") else path)


# ---------------------------------------------------------------- 索引
def _split(text, stem):
    fences = [(m.start(), m.end()) for m in FENCE.finditer(text)]
    heads = [m for m in HEAD.finditer(text) if not any(a <= m.start() < b for a, b in fences)]
    secs, stack = [], []
    first_end = heads[0].start() if heads else len(text)
    if text[:first_end].strip():
        secs.append({"t": [stem], "l": 0, "s": 0, "e": first_end})
    for i, m in enumerate(heads):
        level, title = len(m.group(1)), re.sub(r"[*_`]", "", m.group(2)).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        secs.append({"t": [x[1] for x in stack], "l": level, "s": m.start(),
                     "e": heads[i + 1].start() if i + 1 < len(heads) else len(text)})
    return secs


def _section(key, text, raw):
    body = text[raw["s"]:raw["e"]]
    first = re.sub(r"[#*_`>\[\]]", "", body.split("\n", 1)[1] if "\n" in body else "")[:160].replace("\n", " ")
    return {"f": key, "t": raw["t"], "l": raw["l"], "s": raw["s"], "e": raw["e"], "n": raw["e"] - raw["s"],
            "a": sorted(articles(body)), "k": " ".join(raw["t"]) + "\n" + first}


def _index_file(board):
    return INDEX_DIR + "/" + board + ".json"


def _atomic_json(f, data):
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(f.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
            json.dump(data, fp, ensure_ascii=False)
        os.replace(name, f)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _load_json(f):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def ensure(paths, board, name):
    """建立或增量刷新这个科目的索引，返回 {files, sections}；只重读改过（修改时间或大小变了）的文件"""
    f = paths.train / _index_file(annotations._board(board))
    old = _load_json(f)
    old = old if isinstance(old, dict) and old.get("version") == 1 else {"version": 1, "files": {}, "sections": []}
    src = _sources(paths, board, name)
    stats = {}
    for key, p, _ in src:
        try:
            st = p.stat()
            stats[key] = [st.st_mtime_ns, st.st_size]
        except OSError:
            continue
    same = {k for k, v in stats.items() if old["files"].get(k) == v}
    sections = [s for s in old["sections"] if s["f"] in same]
    changed = len(same) != len(old["files"]) or set(stats) != set(old["files"])
    for key, p, _ in src:
        if key in same or key not in stats:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        sections += [_section(key, text, raw) for raw in _split(text, p.stem)]
        changed = True
    if changed:
        old = {"version": 1, "files": stats, "sections": sections, "built": time.strftime("%Y-%m-%d %H:%M:%S")}
        _atomic_json(f, old)
    return {"files": stats, "sections": sections}


# ---------------------------------------------------------------- 定位
def _qkey(q):
    base = str(q.get("id") or "") or str(q.get("stem") or "")[:200]
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def _pins(paths, board):
    f = paths.train / INDEX_DIR / (annotations._board(board) + ".pins.json")
    d = _load_json(f)
    return d if isinstance(d, dict) else {}


def _pin_id(sec):
    return sec["f"] + "|" + " › ".join(sec["t"])


def pin(paths, board, q, ids):
    d = _pins(paths, board)
    d[_qkey(q)] = list(ids)[:20]
    _atomic_json(paths.train / INDEX_DIR / (annotations._board(board) + ".pins.json"), d)


def query_text(q):
    opts = q.get("options")
    ot = " ".join(str(v) for v in opts.values()) if isinstance(opts, dict) else str(opts or "")
    return " ".join([str(q.get("stem") or ""), ot, str(q.get("topic") or ""), str(q.get("analysis") or "")[:1500]])


def locate(paths, board, name, q, budget=BUDGET):
    """按这道题定位知识点。返回 {found, sections:[{display,title,chars,why,truncated,text}], skipped:[...], total, budget, text, used}。
    name：规则里这个科目的资料名（笔记文件夹）。q：题库里的题（board、chapter、topic、stem、options、analysis）。"""
    idx = ensure(paths, board, name)
    secs = idx["sections"]
    qtext = query_text(q)
    qarts, qbi = articles(qtext), bigrams(qtext)
    chapter = str(q.get("chapter") or "").strip().strip("/")
    pins = set(_pins(paths, board).get(_qkey(q), []))
    n = max(1, len(secs))
    sbi = [bigrams(s["k"]) for s in secs]
    tbi = [bigrams(" ".join(s["t"])) for s in secs]
    df = {}
    for b in sbi:
        for g in b:
            df[g] = df.get(g, 0) + 1
    usable = {g for g in qbi if g in df and df[g] <= max(3, 0.3 * n)}                   # 太常见的词不算线索
    idf = {g: math.log(1 + n / df[g]) for g in usable}
    scored = []
    for i, s in enumerate(secs):
        why, score = [], 0.0
        if chapter and s["f"].startswith("n:") and s["f"][2:].startswith(chapter + "/"):
            score += 4.0
            why.append("章节归属")
        hit = [a for a in s["a"] if a in qarts]
        if hit:
            score += 6.0 * len(hit[:3])
            why.append("法条第" + "、".join(str(a) for a in hit[:3]) + "条")
        words = [g for g in usable if g in sbi[i]]
        if words:
            score += sum(idf[g] * (2.0 if g in tbi[i] else 1.0) for g in words)
            top = sorted(words, key=lambda g: -idf[g])[:3]
            why.append("关键词：" + "、".join(top))
        forced = False
        if s["f"].startswith("a:") and score > 0:        # 自己写的批注：只要和这道题有一点关联就带上（不受相对分数线限制）
            score += 3.0
            forced = True
            why.append("我的批注")
        if _pin_id(s) in pins:
            score += PIN_BONUS
            forced = True
            why.append("已固定（AI 定位）")
        if score >= MIN_SCORE or forced:
            scored.append((score, i, why, forced))
    chosen, skipped, parts, total, cache = [], [], [], 0, {}
    # 分析套路优先（有就带上，不参与打分）
    ana = [s for s in secs if s["f"] == "a:" + annotations.ANALYSIS]
    texts = {}

    def read(s):
        key = s["f"]
        if key not in texts:
            p = (annotations.board_dir(paths, board) / key[2:]) if key.startswith("a:") else (paths.vault / key[2:])
            texts[key] = p.read_text(encoding="utf-8", errors="ignore")
        return texts[key]

    def take(s, why, limit, score):
        nonlocal total
        raw = read(s)[s["s"]:s["e"]].strip("\n")
        trunc = len(raw) > limit
        body = raw[:limit] + ("\n（本小节过长，只读入前 %d 字，完整内容见原文件）" % limit if trunc else "")
        if total + len(body) > budget:
            skipped.append({"display": _display(s, board), "title": " › ".join(s["t"]), "chars": s["n"], "why": why})
            return
        total += len(body)
        excerpt = re.sub(r"\s+", " ", re.sub(r"^#+[^\n]*\n", "", raw, count=1)).strip()[:120]
        item = {"display": _display(s, board), "title": " › ".join(s["t"]), "chars": len(raw), "why": why, "truncated": trunc,
                "score": round(score, 1), "excerpt": excerpt}
        chosen.append(item)
        parts.append("=== %s ===\n%s" % (item["display"] + " › " + item["title"], body))

    ana_chars = 0
    for s in ana:
        if ana_chars >= ANALYSIS_LIMIT:
            break
        take(s, ["分析套路"], ANALYSIS_LIMIT - ana_chars, 99)
        ana_chars += min(s["n"], ANALYSIS_LIMIT)
    if scored:
        top = max(x[0] for x in scored)
        for score, i, why, forced in sorted(scored, key=lambda x: (-x[0], x[1])):
            if (score < REL_CUT * top and not forced) or secs[i]["f"] == "a:" + annotations.ANALYSIS:
                continue
            take(secs[i], why, SECTION_LIMIT, score)
    found = any(c["why"] != ["分析套路"] for c in chosen)
    used = [c["display"] + " › " + c["title"] + ("（截取）" if c["truncated"] else "") for c in chosen]
    used += [x["display"] + " › " + x["title"] + "（未读入：超出预算）" for x in skipped]
    return {"found": found, "sections": chosen, "skipped": skipped, "total": total, "budget": budget,
            "text": "\n\n".join(parts), "used": used, "sections_total": len(secs)}


def tutor_text(paths, board, name, q):
    """给学姐的资料文字和读到的清单：(text, used, found)。一个相关小节都没有时 text 里明说，不让学姐把别的内容当成笔记"""
    r = locate(paths, board, name, q)
    if r["found"]:
        head = "（以下是按这道题从你的笔记里定位到的知识点原文，分析时以它们为准；来源写在每段的标题里）\n\n"
        return head + r["text"], r["used"], True
    tail = ("\n\n" + r["text"]) if r["text"] else ""
    return ("（没有在你的笔记里找到这道题对应的知识点。请明说“笔记里没有找到对应知识点”，再按通用法理讲，"
            "并提示学员以现行法条和教材为准；不要把没有依据的内容说成是笔记里的。）" + tail), r["used"], False


# ---------------------------------------------------------------- 浏览（藏经阁里看知识点树）
def tree(paths, board, name):
    idx = ensure(paths, board, name)
    files = {}
    for s in idx["sections"]:
        files.setdefault(s["f"], []).append({"title": " › ".join(s["t"]), "level": s["l"], "chars": s["n"], "articles": s["a"][:6]})
    out = []
    for key, secs in sorted(files.items(), key=lambda kv: (kv[0].startswith("a:"), kv[0])):
        out.append({"key": key, "display": "批注/%s/%s" % (board, key[2:]) if key.startswith("a:") else key[2:], "annotation": key.startswith("a:"),
                    "chars": sum(x["chars"] for x in secs), "sections": secs})
    return out


def section_text(paths, board, name, key, title):
    """读一个小节原文（只读）。key 必须是索引里有的文件，不接受任意路径"""
    idx = ensure(paths, board, name)
    for s in idx["sections"]:
        if s["f"] == key and " › ".join(s["t"]) == title:
            p = (annotations.board_dir(paths, board) / key[2:]) if key.startswith("a:") else (paths.vault / key[2:])
            return {"display": _display(s, board), "title": title, "text": p.read_text(encoding="utf-8", errors="ignore")[s["s"]:s["e"]]}
    raise annotations.AnnError("没有这个小节")


def catalog(paths, board, name, q=None):
    """请 AI 定位时给它的目录（只有路径和标题，不含正文）。小节太多时只留章节归属内的和关键词命中的"""
    secs = ensure(paths, board, name)["sections"]
    chapter = str((q or {}).get("chapter") or "").strip("/")
    if len(secs) > CATALOG_MAX and chapter:
        inside = [s for s in secs if s["f"][2:].startswith(chapter + "/")]
        secs = inside or secs
    return [(_pin_id(s), "%s › %s（%d 字）" % (_display(s, board), " › ".join(s["t"]), s["n"])) for s in secs[:CATALOG_MAX]]
