"""藏经阁·典籍索引的「我的批注」：每个科目一个可随时修改的批注目录。

存放：训练/知识点批注/<科目>/**.md（程序可写；用户库里的笔记始终只读）。批注是自己对知识点的补充：易错点、对比表、口诀、案例；
另外每个科目可选一份「分析套路.md」（如民法的请求权基础分析、刑法的构成要件层层分析），没有也不影响解惑。
历史：训练/知识点批注/.历史/<科目>/<相对路径>/<时间>.md（每次保存、删除、改名前先留一份，可回滚）。
待审建议：训练/知识点批注/.待审/<id>.json（解惑后「记入批注」由 AI 起草，用户采纳后才写入）。
保存带版本号（内容哈希）：两处同时改，后保存的会收到冲突提示，不会悄悄覆盖。程序算分、判分不读这里的任何内容。
解惑定位时批注和原笔记一起取（见 knowledge.py），并标明来源。
"""
import hashlib
import json
import os
import re
import tempfile
import time

DIR = "知识点批注"
HIST = ".历史"
PENDING = ".待审"
ANALYSIS = "分析套路.md"
MAX_FILE = 200_000
MAX_FILES = 200
MAX_DEPTH = 3
KEEP_HISTORY = 50
MAX_EDITS = 6
MAX_EDIT_TEXT = 6000
BAD_NAME = re.compile(r'[\\:*?"<>|\x00-\x1f]')
ANALYSIS_TEMPLATE = "# {board} · 分析套路\n\n> 遇到这一科的题，先按什么顺序分析（可选；写了解惑就会优先参考）。\n\n1. \n2. \n3. \n"


class AnnError(ValueError):
    def __init__(self, msg, conflict=False):
        super().__init__(msg)
        self.conflict = conflict


def root(paths):
    return paths.train / DIR if paths.train else None


def _board(board):
    b = str(board or "").strip()
    if not b or b.startswith(".") or BAD_NAME.search(b) or "/" in b or len(b) > 40:
        raise AnnError("科目名不合法")
    return b


def board_dir(paths, board):
    r = root(paths)
    if not r:
        raise AnnError("还没有连接资料库")
    return r / _board(board)


def _rel(rel):
    s = str(rel or "").replace("\\", "/").strip()
    if s.startswith("/") or re.match(r"^[A-Za-z]:", s):
        raise AnnError("文件名不合法（不能是绝对路径）")
    parts = s.strip("/").split("/")
    if not s or len(parts) > MAX_DEPTH or any(not p or p in (".", "..") or p.startswith(".") or BAD_NAME.search(p) or len(p) > 80 for p in parts):
        raise AnnError("文件名不合法（只能是 .md，最多 %d 层）" % MAX_DEPTH)
    if not parts[-1].lower().endswith(".md"):
        raise AnnError("只能是 .md 文件")
    return "/".join(parts)


def _file(paths, board, rel):
    d = board_dir(paths, board)
    f = d / _rel(rel)
    if d.resolve() not in f.resolve().parents:
        raise AnnError("文件名不合法")
    return f


def rev(data):
    return hashlib.sha1(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()[:16]


def _atomic(f, text, suffix=".md"):
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(f.parent), prefix=".tmp-", suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(text)
        os.replace(name, f)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _read(f):
    return f.read_text(encoding="utf-8", errors="ignore")


def files(paths, board):
    """批注文件（相对路径；分析套路.md 在前，其余按路径排序；.历史/.待审 不算）"""
    try:
        d = board_dir(paths, board)
    except AnnError:
        return []
    if not d.is_dir():
        return []
    out = []
    for p in d.rglob("*.md"):
        rel = p.relative_to(d)
        if any(x.startswith(".") for x in rel.parts) or len(rel.parts) > MAX_DEPTH:
            continue
        out.append(rel.as_posix())
    return sorted(out, key=lambda r: (r != ANALYSIS, r == "变更记录.md", tuple(r.split("/"))))


def read_file(paths, board, rel):
    f = _file(paths, board, rel)
    if not f.is_file():
        raise AnnError("没有这个文件")
    t = _read(f)
    return {"path": _rel(rel), "text": t, "rev": rev(t), "editable": True}


# ---------------------------------------------------------------- 历史
def _hist_dir(paths, board, rel):
    return root(paths) / HIST / _board(board) / _rel(rel)


def _stash(paths, board, rel, text):
    d = _hist_dir(paths, board, rel)
    d.mkdir(parents=True, exist_ok=True)
    if any(_read(p) == text for p in d.glob("*.md")):
        return
    name = time.strftime("%Y%m%d-%H%M%S")
    f, i = d / (name + ".md"), 1
    while f.exists():
        i += 1
        f = d / ("%s-%d.md" % (name, i))
    _atomic(f, text)
    for p in sorted(d.glob("*.md"))[:-KEEP_HISTORY]:
        try:
            p.unlink()
        except OSError:
            pass


def history(paths, board, rel):
    d = _hist_dir(paths, board, rel)
    out = []
    for p in sorted(d.glob("*.md"), reverse=True) if d.is_dir() else []:
        t = p.stem
        at = "%s-%s-%s %s:%s:%s" % (t[0:4], t[4:6], t[6:8], t[9:11], t[11:13], t[13:15]) if re.match(r"^\d{8}-\d{6}", t) else t
        out.append({"id": p.stem, "at": at, "chars": len(_read(p))})
    return out


def history_text(paths, board, rel, vid):
    f = _hist_dir(paths, board, rel) / (re.sub(r"[^0-9\-]", "", str(vid)) + ".md")
    if not f.is_file():
        raise AnnError("没有这个历史版本")
    return _read(f)


# ---------------------------------------------------------------- 修改
def save(paths, board, rel, text, base):
    if not isinstance(text, str):
        raise AnnError("内容不对")
    if len(text) > MAX_FILE:
        raise AnnError("文件太长（上限 %d 字），请拆成几个文件" % MAX_FILE)
    f = _file(paths, board, rel)
    if f.is_file():
        cur = _read(f)
        if base != rev(cur):
            raise AnnError("这个文件在别处被改过了，请先刷新再改（你的内容没有丢，先复制出来）", conflict=True)
        if cur == text:
            return {"rev": rev(cur), "changed": False}
        _stash(paths, board, rel, cur)
    else:
        if base:
            raise AnnError("这个文件已经不存在了，请刷新", conflict=True)
        if len(files(paths, board)) >= MAX_FILES:
            raise AnnError("一个科目最多 %d 个批注文件" % MAX_FILES)
    _atomic(f, text)
    return {"rev": rev(text), "changed": True}


def delete(paths, board, rel, base):
    f = _file(paths, board, rel)
    if not f.is_file():
        raise AnnError("没有这个文件")
    cur = _read(f)
    if base != rev(cur):
        raise AnnError("这个文件在别处被改过了，请先刷新", conflict=True)
    _stash(paths, board, rel, cur)
    f.unlink()
    return {"deleted": _rel(rel)}


def rename(paths, board, rel, new_rel, base):
    f, g = _file(paths, board, rel), _file(paths, board, new_rel)
    if not f.is_file():
        raise AnnError("没有这个文件")
    if g.exists():
        raise AnnError("已经有同名文件")
    cur = _read(f)
    if base != rev(cur):
        raise AnnError("这个文件在别处被改过了，请先刷新", conflict=True)
    _stash(paths, board, rel, cur)
    _atomic(g, cur)
    f.unlink()
    return {"path": _rel(new_rel), "rev": rev(cur)}


def restore(paths, board, rel, vid, base):
    return save(paths, board, rel, history_text(paths, board, rel, vid), base)


def create_analysis(paths, board):
    f = _file(paths, board, ANALYSIS)
    if f.is_file():
        raise AnnError("已经有分析套路了")
    return save(paths, board, ANALYSIS, ANALYSIS_TEMPLATE.replace("{board}", _board(board)), "")


# ---------------------------------------------------------------- 待审建议（解惑后「记入批注」）
def _atomic_json(f, data):
    _atomic(f, json.dumps(data, ensure_ascii=False, indent=1), ".json")


def _load(f):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _clean_edits(edits):
    out = []
    for e in edits or []:
        if not isinstance(e, dict):
            continue
        action, text = e.get("action"), str(e.get("text") or "").strip()
        if action not in ("append", "new") or not text:
            continue
        try:
            rel = _rel(e.get("path"))
        except AnnError:
            continue
        out.append({"path": rel, "action": action, "text": text[:MAX_EDIT_TEXT], "reason": str(e.get("reason") or "")[:300], "done": False})
    return out[:MAX_EDITS]


def add_proposal(paths, board, summary, edits, source=None, key=""):
    _board(board)
    d = root(paths) / PENDING
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        old = _load(p)
        if old and key and old.get("board") == board and old.get("key") == key:
            return old
    edits = _clean_edits(edits)
    if not edits:
        raise AnnError("没有可用的修改建议")
    pid = "%s-%s" % (time.strftime("%Y%m%d%H%M%S"), hashlib.sha1((board + str(time.time()) + summary).encode("utf-8")).hexdigest()[:6])
    data = {"id": pid, "board": board, "summary": str(summary or "")[:200], "source": source or {}, "key": key,
            "created": time.strftime("%Y-%m-%d %H:%M"), "edits": edits}
    _atomic_json(d / (pid + ".json"), data)
    return data


def proposals(paths, board=None):
    r = root(paths)
    d = r / PENDING if r else None
    out = []
    for p in sorted(d.glob("*.json"), reverse=True) if d and d.is_dir() else []:
        data = _load(p)
        if isinstance(data, dict) and data.get("id") == p.stem and (board is None or data.get("board") == board):
            out.append(data)
    return out


def _proposal(paths, pid):
    pid = re.sub(r"[^0-9a-f\-]", "", str(pid or ""))
    f = root(paths) / PENDING / (pid + ".json")
    data = _load(f) if f.is_file() else None
    if not isinstance(data, dict) or data.get("id") != pid:
        raise AnnError("这条建议已经不存在了")
    return f, data


def dismiss(paths, pid):
    _proposal(paths, pid)[0].unlink()
    return {"dismissed": True}


def accept(paths, board, pid, picks):
    """采纳勾选的修改：append 追加到文件末尾（没有就新建）；new 遇到同名文件不覆盖。写完记进 变更记录.md。"""
    f, data = _proposal(paths, pid)
    if data.get("board") != board:
        raise AnnError("这条建议不属于这个科目")
    edits = data["edits"]
    chosen = [i for i in (picks or []) if isinstance(i, int) and 0 <= i < len(edits) and not edits[i].get("done")]
    if not chosen:
        raise AnnError("请先勾选要采纳的修改")
    applied, skipped = [], []
    for i in chosen:
        e = edits[i]
        target = _file(paths, board, e["path"])
        if e["action"] == "new" or not target.is_file():
            if target.is_file():
                skipped.append("%s（已有同名文件，没有覆盖）" % e["path"])
                continue
            save(paths, board, e["path"], e["text"].rstrip("\n") + "\n", "")
        else:
            cur = _read(target)
            save(paths, board, e["path"], cur.rstrip("\n") + "\n\n" + e["text"].rstrip("\n") + "\n", rev(cur))
        e["done"] = True
        applied.append(e["path"])
    if applied:
        log = board_dir(paths, board) / "变更记录.md"
        cur = _read(log) if log.is_file() else "# 变更记录\n\n每次采纳建议都会在这里留一行。\n"
        src = (data.get("source") or {}).get("label")
        _atomic(log, cur.rstrip("\n") + "\n- %s 采纳「%s」→ %s%s\n" % (time.strftime("%Y-%m-%d %H:%M"), data.get("summary", ""), "、".join(applied),
                                                                  "（来源：%s）" % src if src else ""))
    if all(e.get("done") for e in edits):
        f.unlink()
    else:
        _atomic_json(f, data)
    return {"applied": applied, "skipped": skipped, "left": sum(not e.get("done") for e in edits)}
