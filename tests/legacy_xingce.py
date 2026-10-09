"""测试用：把程序切回“行测修仙传”的底本配置（行测板块、修仙风格、行测默认文件）。

法师成长记是从行测修仙传 3.3.0 复制来的，引擎（经验、位阶、晋升试炼、试炼塔、符文卡、手札……）一行没改，
原来那一大批用例按行测的板块和数字写成，继续用它们守住引擎本身；法考自己的配置（八科、玄幻、300 分制、
多选题、找库）另在 tests/test_fakao.py 里测。

用法：在测试模块最上面 `import legacy_xingce`（导入即生效，整个测试进程都按行测底本跑），
test_fakao.py 自己用 legacy_xingce.restore() / apply() 切换。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from rpg import cards, config, mock, paths, themes  # noqa: E402

XC_DEFAULTS = HERE / "fixtures" / "xingce_defaults"

XC_RULES = {
    "开始日期": "2026-09-29", "目标日": "2027-12-01", "每日目标分钟": 300, "每日理想经验": 300,
    "渡劫灵根.70": "激活5 玄阶2", "渡劫灵根.75": "激活7 玄阶4 地阶1", "渡劫灵根.80": "激活9 玄阶6 地阶3",
    "渡劫灵根.85": "激活10 地阶5 天阶2", "灵根正确率.常识判断": "45, 50, 55, 60, 65, 70, 75, 80",
}
XC_BATCHES = [["论证逻辑", "形式逻辑", "一拖五"], ["片段阅读", "逻辑填空", "政治理论"], ["资料分析", "数量关系"],
              ["定义判断", "类比推理", "图形推理"]]
XC_BOARDS = {
    "论证逻辑": ("xue-rui-argument-logic", ["论证逻辑"]), "形式逻辑": ("xue-rui-formal-logic", ["形式逻辑"]),
    "一拖五": ("xue-rui-yituowu", ["一拖五"]), "片段阅读": ("center-comprehension-jiangwei", ["中心理解", "语句排序"]),
    "逻辑填空": ("xingce-luojitiankong", ["逻辑填空"]), "政治理论": ("political-theory-reasoning", ["政治理论"]),
    "资料分析": ("xingce-ziliao", ["资料分析"]), "数量关系": ("xingce-shuliang", ["数量关系"]),
    "定义判断": ("xingce-dingyi", ["定义判断"]), "类比推理": ("xingce-leibi", ["类比关系"]), "图形推理": ("xingce-tuxing", ["图形推理"]),
}
XC_DECKS = ["政治理论", "常识判断", "逻辑填空", "片段阅读", "数量关系", "图形推理", "定义判断",
            "类比推理", "论证逻辑", "形式逻辑", "一拖五", "资料分析"]
XC_MODULES = (
    ("政治理论", ("政治理论",)), ("常识判断", ("常识判断",)),
    ("言语理解", ("逻辑填空", "中心理解", "语句排序", "片段阅读")), ("数量关系", ("数量关系",)),
    ("判断推理", ("图形推理", "定义判断", "类比关系", "类比推理", "论证逻辑", "形式逻辑", "一拖五")), ("资料分析", ("资料分析",)),
)
XC_FIXED = {"言语理解": (("逻辑填空", 15), ("片段阅读", 10), ("语句表达", 5)),
            "判断推理": (("图形推理", 10), ("定义判断", 10), ("类比推理", 5), ("论证逻辑", 5), ("一拖五", 5))}

_SAVED = None


def _snapshot():
    return dict(rules=dict(config.DEFAULT_RULES), batches=config.DEFAULT_BATCHES, boards=config.DEFAULT_BOARDS,
                side=config.DEFAULT_SIDE, defaults=paths.DEFAULTS_DIR, auto=paths.AUTO_SKELETONS, theme=themes.DEFAULT_THEME,
                decks=cards.DEFAULT_DECKS, modules=(mock.MODULES, mock.MODULE_OF, mock.MODULE_NAMES, mock.FIXED))


def apply():
    global _SAVED
    if _SAVED is None:
        _SAVED = _snapshot()
    config.DEFAULT_RULES.update(XC_RULES)
    config.DEFAULT_BATCHES = XC_BATCHES
    config.DEFAULT_BOARDS = XC_BOARDS
    config.DEFAULT_SIDE = {"常识判断": 0.6}
    paths.DEFAULTS_DIR = XC_DEFAULTS
    paths.AUTO_SKELETONS = ("图形推理.md", "资料分析.md")
    themes.DEFAULT_THEME = "修仙"
    cards.DEFAULT_DECKS = XC_DECKS
    mock.MODULES, mock.MODULE_OF = XC_MODULES, {b: m for m, bs in XC_MODULES for b in bs}
    mock.MODULE_NAMES, mock.FIXED = [m for m, _ in XC_MODULES], XC_FIXED


def restore():
    """切回法师成长记自己的配置"""
    if _SAVED is None:
        return
    s = _SAVED
    config.DEFAULT_RULES.clear()
    config.DEFAULT_RULES.update(s["rules"])
    config.DEFAULT_BATCHES, config.DEFAULT_BOARDS, config.DEFAULT_SIDE = s["batches"], s["boards"], s["side"]
    paths.DEFAULTS_DIR, paths.AUTO_SKELETONS, themes.DEFAULT_THEME = s["defaults"], s["auto"], s["theme"]
    cards.DEFAULT_DECKS = s["decks"]
    mock.MODULES, mock.MODULE_OF, mock.MODULE_NAMES, mock.FIXED = s["modules"]


apply()
