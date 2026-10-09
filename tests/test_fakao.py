"""法师成长记自己的配置：法考八科、固定玄幻（法师位阶）、单选 / 多选 / 不定项、300 分制录分、找法考库、不误用行测库。

其他测试模块按行测底本跑（tests/legacy_xingce.py）；这个模块开始时切回法师成长记的配置，结束时再切回去。"""
import legacy_xingce
import datetime as dt
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from rpg import api, config, engine, paths, question_bank as bank, store, themes, trainer, vault

EIGHT = ["民法", "刑法", "民诉", "刑诉", "行政法", "商经知", "三国法", "理论法"]


def setUpModule():
    legacy_xingce.restore()


def tearDownModule():
    legacy_xingce.apply()


def q(ident, answer, kind=""):
    return ('\n## 题目 %s\n### 知识点\n表见代理\n%s### 题干\n甲以乙的名义……\n'
            '### 选项\nA. 甲\nB. 乙\nC. 丙\nD. 丁\n### 答案\n%s\n### 解析\n依据《民法典》第172条\n') % (
        ident, ('### 题型\n%s\n' % kind) if kind else '', answer)


class ConfigTest(unittest.TestCase):
    def test_eight_subjects_timeline_and_mage_style(self):
        r = config.Rules("")
        self.assertEqual(list(r.boards), EIGHT)
        self.assertEqual(r.batches, [["民法", "刑法"], ["民诉", "刑诉"], ["行政法", "商经知"], ["三国法", "理论法"]])
        self.assertEqual(r.side, {})
        self.assertEqual(r.boards["民法"]["skill"], "10-科目/民法")
        self.assertEqual((str(r.date("开始日期")), str(r.date("目标日")), r.num("每日目标分钟")), ("2026-12-01", "2027-09-10", 180))
        self.assertEqual(themes.DEFAULT_THEME, "玄幻")
        self.assertEqual([themes.realm_name("玄幻", s) for s in (50, 51, 60, 64, 75, 85)],
                         ["平民 · 未觉醒", "魔法学徒一星", "初级法师下位", "初级法师上位", "大魔导师下位", "法神·上岸者"])
        self.assertEqual(themes.get("玄幻")["terms"]["brand"], "🔮 法师成长记")
        p = config.Persona("")
        self.assertEqual((p["导师名"], p["称呼"]), ("艾琳学姐", "小法师"))
        # 默认规则文件和程序里的默认值一致
        from_file = config.Rules((paths.DEFAULTS_DIR / "规则.md").read_text(encoding="utf-8"))
        self.assertEqual(list(from_file.boards), EIGHT)
        self.assertEqual(from_file.batches, r.batches)
        for k in ("开始日期", "目标日", "每日目标分钟", "每日理想经验", "渡劫灵根.85"):
            self.assertEqual(str(from_file.get(k)), str(r.get(k)), k)


class VaultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._settings = paths.SETTINGS_FILE, paths.SETTINGS_DIR
        paths.SETTINGS_DIR = self.tmp / "home"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        self._env = os.environ.pop("FAKAO_VAULT", None)

    def tearDown(self):
        paths.SETTINGS_FILE, paths.SETTINGS_DIR = self._settings
        if self._env is not None:
            os.environ["FAKAO_VAULT"] = self._env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_train_dir_marker_templates_and_detection(self):
        v = self.tmp / "法考"
        v.mkdir()
        self.assertFalse(paths.looks_like_vault(v))                  # 自动找库：空文件夹不认
        self.assertTrue(paths.looks_like_vault(v, strict=False))     # 手动填：文件夹就行
        p = paths.Paths(v)
        p.ensure_train_dir()
        self.assertTrue((v / "训练" / paths.MARKER).is_file())
        self.assertTrue(paths.looks_like_vault(v))                   # 有了标记，自动找库也认
        self.assertEqual(sorted(f.name for f in (v / "训练/题库").glob("*.md")), sorted(b + "真题.md" for b in EIGHT))
        self.assertEqual(list((v / "训练/骨架").glob("*.md")), [])   # 法考没有程序自带的咒文书

    def test_xingce_vault_is_refused(self):
        xc = self.tmp / "行测"
        (xc / "FB模考试卷复盘/板块复盘").mkdir(parents=True)
        (xc / "训练/存档").mkdir(parents=True)
        (xc / "训练/存档/存档.json").write_text("{}", encoding="utf-8")
        self.assertTrue(paths.is_xingce_vault(xc))
        self.assertFalse(paths.looks_like_vault(xc, strict=False))
        os.environ["FAKAO_VAULT"] = str(xc)
        try:
            self.assertIsNone(paths.find_vault())
        finally:
            os.environ.pop("FAKAO_VAULT", None)
        with self.assertRaises(api.ApiError) as cm:
            api.settings_set({"vault": str(xc)})
        self.assertIn("行测修仙传", str(cm.exception))
        ok = self.tmp / "法考"
        ok.mkdir()
        api.settings_set({"vault": str(ok)})
        self.assertEqual(paths.find_vault(), ok.resolve())

    def test_subject_notes_folder_is_material(self):
        v = self.tmp / "法考"
        (v / "10-科目/民法/总则").mkdir(parents=True)
        (v / "10-科目/民法/总则/代理.md").write_text("# 代理\n表见代理：相对人有理由相信……", encoding="utf-8")
        (v / "10-科目/民法/.隐藏.md").write_text("不该读", encoding="utf-8")
        (v / "10-科目/刑法").mkdir(parents=True)                     # 空文件夹：不算有资料
        p = paths.Paths(v)
        p.ensure_train_dir()
        self.assertEqual(vault.skill_dir(p, "10-科目/民法"), v / "10-科目/民法")
        self.assertIsNone(vault.skill_dir(p, "10-科目/刑法"))
        self.assertIsNone(vault.skill_dir(p, "../外面"))
        text = vault.skill_digest(p, "10-科目/民法")
        self.assertIn("表见代理", text)
        self.assertNotIn("不该读", text)
        with self.assertRaises(ValueError):
            vault.skill_digest(p, "10-科目/民法", limit=5)
        tutor, used = vault.skill_for_tutor(p, "10-科目/民法")
        self.assertIn("表见代理", tutor)
        self.assertEqual(used, ["总则/代理.md"])
        _, refs = vault.skill_material(p, "10-科目/民法")
        self.assertEqual(refs, ["10-科目/民法/总则/代理.md"])
        g = engine.Game(p, config.Rules(""), config.Persona(""), config.Lines(), store.new_state(dt.date(2026, 12, 1)), dt.date(2026, 12, 1))
        self.assertTrue(g.has_skill("民法"))
        self.assertFalse(g.has_skill("刑法"))


class BankKindTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = paths.Paths(Path(self.tmp.name))
        self.paths.ensure_train_dir()
        self.day = dt.date(2026, 12, 2)
        self.g = engine.Game(self.paths, config.Rules(""), config.Persona(""), config.Lines(), store.new_state(self.day), self.day)
        self.file = self.paths.train / "题库/民法真题.md"
        self.task = {"type": "bank", "board": "民法", "title": "实战", "target": "民法", "id": "bank:民法"}

    def tearDown(self):
        self.tmp.cleanup()
        trainer.SESSIONS.clear()

    def test_parse_kinds_and_normalized_answers(self):
        self.file.write_text(q("01", "A") + q("02", "b, a d") + q("03", "C", "不定项") + q("04", "AB", "单选"), encoding="utf-8")
        qs, errs = bank.read(self.paths, "民法")
        by = {x["id"]: x for x in qs}
        self.assertEqual((by["01"]["kind"], by["01"]["answer"]), ("single", "A"))
        self.assertEqual((by["02"]["kind"], by["02"]["answer"]), ("multi", "ABD"))
        self.assertEqual((by["03"]["kind"], by["03"]["answer"]), ("any", "C"))
        self.assertTrue(bank.is_multi(by["03"]))                    # 不定项哪怕答案只有一个，也按多选作答
        self.assertTrue(any("04" in e and "单选" in e for e in errs))

    def test_multi_exam_toggle_and_all_or_nothing(self):
        self.file.write_text(q("01", "ABD") + q("02", "C", "不定项") + q("03", "B"), encoding="utf-8")
        r = trainer.start(self.g, self.task)
        sid = r["session"]
        self.assertIn("可选多个", str(r))
        for k in "ABD":                                              # 多选：勾上，不翻页
            r = trainer.action(self.g, sid, "exam_pick:0:" + k)
        self.assertIn("✓ D", str(r["input"]))
        r = trainer.action(self.g, sid, "exam_pick:0:B")             # 再点一次取消
        self.assertNotIn("✓ B", str(r["input"]))
        r = trainer.action(self.g, sid, "exam_pick:0:B")
        r = trainer.action(self.g, sid, "exam_next")
        r = trainer.action(self.g, sid, "exam_pick:1:C")
        r = trainer.action(self.g, sid, "exam_pick:1:A")             # 不定项选多了 → 错
        r = trainer.action(self.g, sid, "exam_next")
        r = trainer.action(self.g, sid, "exam_pick:2:B")             # 单选：选完自动停在最后一题
        r = trainer.action(self.g, sid, "exam_submit")
        res = bank.state(self.g)["runs"]["民法"]["results"]
        self.assertEqual([(x["answer"], x["ok"]) for x in res], [("ABD", True), ("AC", False), ("B", True)])

    def test_single_rejects_multiple_letters(self):
        self.file.write_text(q("01", "A"), encoding="utf-8")
        run = bank.begin(self.g, "民法", "new")
        with self.assertRaises(bank.BankError):
            bank.record(self.g, run, "AB")
        self.assertEqual(bank.record(self.g, run, "a") is not None, True)
        self.assertTrue(run["results"][0]["ok"])


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = self.tmp / "法考"
        (self.vault / "10-科目").mkdir(parents=True)
        self._settings = paths.SETTINGS_FILE, paths.SETTINGS_DIR
        paths.SETTINGS_DIR = self.tmp / "home"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        paths.save_settings({"vault": str(self.vault)})

    def tearDown(self):
        paths.SETTINGS_FILE, paths.SETTINGS_DIR = self._settings
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state(self):
        return json.loads((self.vault / "训练/存档/存档.json").read_text(encoding="utf-8"))

    def test_boss_300_scale_and_fixed_theme(self):
        d = api.dashboard({})
        self.assertEqual(d["theme"]["name"], "玄幻")
        self.assertEqual(d["persona"]["tutor"], "艾琳学姐")
        api.boss({"name": "客观题模考1", "score": "210", "scale": 300})
        api.boss({"name": "百分制", "score": "75"})
        self.assertEqual([b["score"] for b in self.state()["boss"]], [70.0, 75.0])
        with self.assertRaises(api.ApiError):
            api.boss({"name": "超了", "score": "301", "scale": 300})
        with self.assertRaises(api.ApiError):
            api.theme_set({"theme": "修仙"})
        api.theme_set({"theme": "玄幻"})


if __name__ == "__main__":
    unittest.main()
