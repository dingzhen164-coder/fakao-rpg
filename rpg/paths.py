"""
路径：找 Obsidian 法考库（vault）、训练文件夹、本机设置。

约定：
    <库>/10-科目/<科目>/…                            各科笔记（只读；规则.md 的“板块.<科目>”可以指向它，作为咒文书素材和讲题资料）
    <库>/copilot/skills/<skill名>/SKILL.md          可选：某科的 skill（只读）
    <库>/训练/                                       本程序的数据（规则、咒文书、存档……），坚果云同步；
                                                     训练/.法师成长记 是标记文件，自动找库时认它
    ~/.fakao-rpg/settings.json                      本机设置（API key、库路径），不同步、不进仓库

找库的顺序：环境变量 FAKAO_VAULT → 本机设置里的 vault → 从程序所在目录往上找 → 坚果云 / 桌面 / 文稿里找。
自动找只认“有 10-科目 文件夹”或“训练/.法师成长记”的库；手动填的路径只要是文件夹就行。
无论哪种，都拒绝行测修仙传正在用的库（有 FB模考试卷复盘 和存档、没有 训练/.法师成长记）：两个程序的存档都叫 训练/存档/存档.json，混在一起会互相覆盖。
"""
import json
import os
import re
import sys
from pathlib import Path

# 打包成 exe（PyInstaller）时：网页、默认配置在 exe 解出的临时目录里（sys._MEIPASS）；
# 找库从 exe 所在目录往上找（把 exe 放在 <库>/训练/程序/ 里就能自己找到库）
FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent   # 程序根目录
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR)) if FROZEN else APP_DIR                               # 网页、默认配置所在
WEB_DIR = RES_DIR / "web"
DEFAULTS_DIR = RES_DIR / "defaults"                       # 首次运行时复制到 训练/ 的默认配置
SETTINGS_DIR = Path.home() / ".fakao-rpg"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

SKILLS_REL = Path("copilot") / "skills"
SEASONS_REL = Path("FB模考试卷复盘") / "板块复盘"
TRAIN_REL = Path("训练")


def load_settings():
    """本机设置：{"api_key", "base_url", "model", "vault"}，文件不存在就返回空字典"""
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, SETTINGS_FILE)


SUBJECTS_REL = Path("10-科目")
MARKER = ".法师成长记"


def is_xingce_vault(p: Path) -> bool:
    """行测修仙传正在用的库：有 FB模考试卷复盘、有存档、却没有法师成长记的标记文件。不能拿来当法考库（存档同名会互相覆盖）"""
    t = p / TRAIN_REL
    return (p / SEASONS_REL).is_dir() and (t / "存档" / "存档.json").is_file() and not (t / MARKER).is_file()


def looks_like_vault(p: Path, strict=True) -> bool:
    """strict（自动找库）：有 10-科目 或 训练/.法师成长记；否则（环境变量 / 手动填）只要是文件夹。行测库一律不认"""
    try:
        if not p.is_dir() or is_xingce_vault(p):
            return False
        if not strict:
            return True
        return (p / SUBJECTS_REL).is_dir() or (p / TRAIN_REL / MARKER).is_file()
    except OSError:
        return False


def find_vault():
    """返回库根目录（Path）；找不到返回 None，网页会提示用户在“设置”里填写"""
    env = os.environ.get("FAKAO_VAULT")
    if env and looks_like_vault(Path(env).expanduser(), strict=False):
        return Path(env).expanduser().resolve()
    s = load_settings().get("vault")
    if s and looks_like_vault(Path(s).expanduser(), strict=False):
        return Path(s).expanduser().resolve()
    # 推荐把程序放在 <库>/训练/程序/ 里，这样往上两级就是库
    for p in [APP_DIR, *APP_DIR.parents]:
        if looks_like_vault(p):
            return p
    # 程序不在库里（比如 Mac 上把 App 放进了“应用程序”）：到坚果云、桌面、文稿里找一找，找到就记进本机设置
    v = guess_vault()
    if v:
        st = load_settings()
        st["vault"] = str(v)
        save_settings(st)
    return v


SKIP_DIRS = {"Library", "Applications", "node_modules", "AppData", "Pictures", "Music", "Movies", "Videos", "Downloads"}


def guess_vault(home=None, limit=6000):
    """在常见位置（坚果云同步文件夹、桌面、文稿、主目录）往下几层找像法考库的文件夹；只找一个，找不到返回 None"""
    home = Path(home) if home else Path.home()
    roots = [(home / n, 4) for n in ("Nutstore Files", "Nutstore", "坚果云", "我的坚果云", "Desktop", "Documents", "桌面", "文稿")]
    roots.append((home, 2))
    seen = 0
    for root, depth in roots:
        level = [root]
        for _ in range(depth + 1):
            nxt = []
            for d in level:
                seen += 1
                if seen > limit:
                    return None
                try:
                    if looks_like_vault(d):
                        return d.resolve()
                    nxt += sorted(c for c in d.iterdir() if c.is_dir() and not c.name.startswith(".") and c.name not in SKIP_DIRS)
                except OSError:
                    continue
            level = nxt
    return None


class Paths:
    """一个库对应的全部路径。vault 为 None 时各属性也为 None。"""

    def __init__(self, vault):
        self.vault = vault
        self.skills = vault / SKILLS_REL if vault else None
        self.seasons = vault / SEASONS_REL if vault else None
        self.train = vault / TRAIN_REL if vault else None
        self.skeletons = self.train / "骨架" if vault else None
        self.save_dir = self.train / "存档" if vault else None
        self.save_file = self.save_dir / "存档.json" if vault else None
        self.rules = self.train / "规则.md" if vault else None
        self.persona = self.train / "角色设定.md" if vault else None
        self.lines = self.train / "台词库.md" if vault else None

    def _migrate_rules(self):
        """规则的小迁移：只改仍是旧默认值的行，用户改过的值不动。
        每日目标从“只算修炼 120 分钟”改为“修炼 + 听道（网课）合计 300 分钟”，周常分钟同步放大。"""
        f = self.rules
        if not f or not f.is_file():
            return
        t = f.read_text(encoding="utf-8")
        n = re.sub(r"(?m)^(\s*-\s*每日目标分钟\s*[:：]\s*)120\b[^\n]*$",
                   r"\g<1>300  # 修炼 + 听道（网课）合计", t)
        n = re.sub(r"(?m)^(\s*-\s*周常\.修炼分钟\s*[:：]\s*)600\b[^\n]*$", r"\g<1>1500  # 含听道", n)
        if n != t:
            with open(f, "w", encoding="utf-8", newline="\n") as fp:
                fp.write(n)
            NOTICES.append("规则.md 已调整：每日目标 120 → 300 分钟（修炼 + 听道合计），周常功行 600 → 1500 分钟。")

    def ensure_train_dir(self):
        """建 训练/ 文件夹，把缺失的默认配置复制进去。
        已有的配置文件不覆盖；只有它的“配置版本”低于程序里这个文件的版本（config.FILE_VERSIONS，程序升级改了结构）时，
        才把旧文件改名为 “xxx.旧版.md” 备份，再换成新的默认文件。返回被升级的文件名列表。"""
        from .config import FILE_VERSIONS
        from .mdconf import parse, to_num
        if not self.vault:
            return []
        for d in (self.train, self.skeletons, self.save_dir, self.train / "外观" / "背景", self.train / "外观" / "音乐"):
            d.mkdir(parents=True, exist_ok=True)
        mark = self.train / MARKER          # 标记：这个 训练/ 是法师成长记的（自动找库认它）
        if not mark.exists():
            mark.write_text("法师成长记的数据文件夹（这个文件请保留，程序靠它认出法考库）\n", encoding="utf-8")
        quotes = self.train / "语录.md"   # 背景上的语录，用户自己改；只在缺失时复制
        if not quotes.exists() and (DEFAULTS_DIR / "语录.md").exists():
            with open(quotes, "w", encoding="utf-8", newline="\n") as fp:
                fp.write((DEFAULTS_DIR / "语录.md").read_text(encoding="utf-8"))
        upgraded = []
        for name in ("规则.md", "角色设定.md", "台词库.md", "台词库·玄幻.md"):
            dst = self.train / name
            src = DEFAULTS_DIR / name
            if dst.exists():
                ver = to_num(parse(dst.read_text(encoding="utf-8", errors="ignore")).get("配置版本", 1), 1)
                if ver >= FILE_VERSIONS.get(name, 1):
                    continue
                bak = dst.with_name(dst.stem + ".旧版.md")
                if bak.exists():
                    bak.unlink()
                os.replace(dst, bak)
                upgraded.append(name)
            with open(dst, "w", encoding="utf-8", newline="\n") as fp:
                fp.write(src.read_text(encoding="utf-8"))
        # 程序自带的功法（图形推理.md = 图推 24 诀；资料分析.md = 题型识别 + 公式速算）：库里还没有时复制一份草稿，已有的绝不覆盖。
        # （法师成长记没有程序自带的咒文书，AUTO_SKELETONS 为空；这段逻辑留给以后程序自带咒文书时用。）
        for name in AUTO_SKELETONS:
            src = DEFAULTS_DIR / "骨架" / name
            dst = self.skeletons / name
            if not src.exists():
                continue
            text = src.read_text(encoding="utf-8")
            if dst.exists():
                # 库里已有同名功法：不覆盖。若它是别处来的（比如之前按 skill 生成的草稿，“来源skill”不同），
                # 旁边放一份“xxx.程序自带版.md”供对照/替换；是程序自带那份（用户改过也一样）就什么都不做。
                src_of = lambda t: (re.search(r"^来源skill[:：]\s*(.*)$", t, re.M) or [None, ""])[1].strip()
                if src_of(dst.read_text(encoding="utf-8", errors="ignore")) == src_of(text):
                    continue
                dst = self.skeletons / (Path(name).stem + ".程序自带版.md")
                if dst.exists():
                    continue
            with open(dst, "w", encoding="utf-8", newline="\n") as fp:
                fp.write(text)
        self._migrate_rules()
        if upgraded:
            UPGRADED.extend(upgraded)
        from .question_bank import ensure_templates
        ensure_templates(self)
        return upgraded


UPGRADED = []  # 本次运行中被升级的配置文件（网页上提示一次）
NOTICES = []   # 本次运行中对配置做的小改动说明（网页上提示一次）
AUTO_SKELETONS = ()   # 行测修仙传自带图推 / 资料分析功法；法考没有程序自带的咒文书

