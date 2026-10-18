"""法考 3.4：知识点索引与解惑定位、我的批注（随时修改、历史、冲突）、AI 定位、记入批注、解惑接入。
假 AI、假库、假 HOME；不碰真实笔记与密钥。"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import legacy_xingce
from rpg import ai, annotations, api, knowledge, knowledge_ai, paths, prompts, trainer


def setUpModule():
    legacy_xingce.restore()          # 其他用例把全局配置切成了行测底本，这里用法考自己的八科


def tearDownModule():
    legacy_xingce.apply()

BOARD = "民法"
NAME = "10-科目/民法"

PROPERTY = """# 物权

## 物权变动

### 不动产登记

不动产物权变动，自记载于不动产登记簿时发生效力。第二百零九条规定，依法属于国家所有的自然资源，所有权可以不登记。

### 善意取得

无处分权人将不动产或者动产转让给受让人的，受让人善意取得所有权须同时满足三个条件。第三百一十一条是根据。
"""
CONTRACT = """# 合同

## 合同的订立

要约与承诺的构成要件。第四百七十一条规定订立合同可以采取要约、承诺方式。

## 违约责任

违约责任的承担方式：继续履行、采取补救措施、赔偿损失。
"""


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vault = self.root / "vault"
        for ctx in (patch.object(Path, "home", return_value=self.root / "home"),
                    patch.dict(os.environ, {"FAKAO_VAULT": str(self.vault)}),
                    patch.object(paths, "SETTINGS_DIR", self.root / "home" / ".fakao-rpg"),
                    patch.object(paths, "SETTINGS_FILE", self.root / "home" / ".fakao-rpg" / "settings.json")):
            ctx.start()
            self.addCleanup(ctx.stop)
        d = self.vault / NAME / "物权"
        d.mkdir(parents=True)
        (d / "物权变动.md").write_text(PROPERTY, encoding="utf-8")
        c = self.vault / NAME / "合同"
        c.mkdir()
        (c / "合同总论.md").write_text(CONTRACT, encoding="utf-8")
        (self.vault / "10-科目/刑法").mkdir(parents=True)
        (self.vault / "10-科目/刑法/总则.md").write_text("# 犯罪构成\n\n三阶层：构成要件该当性、违法性、有责性。", encoding="utf-8")
        self.p = paths.Paths(self.vault)
        self.p.ensure_train_dir()
        self.notes_bytes = {str(f): f.read_bytes() for f in (self.vault / "10-科目").rglob("*.md")}

    def notes_same(self):
        return {str(f): f.read_bytes() for f in (self.vault / "10-科目").rglob("*.md")} == self.notes_bytes

    def q(self, **kw):
        base = {"id": "2019-1-023", "board": BOARD, "stem": "甲将房屋出卖给乙，未办理登记，乙善意取得所有权须满足什么条件？", "options": {"A": "已登记", "B": "善意"},
                "topic": "物权变动", "chapter": "", "analysis": "", "answer": "A"}
        base.update(kw)
        return base


class IndexTest(Base):
    def test_sections_articles_and_headings(self):
        idx = knowledge.ensure(self.p, BOARD, NAME)
        titles = [" › ".join(s["t"]) for s in idx["sections"]]
        self.assertIn("物权 › 物权变动 › 善意取得", titles)
        s = next(x for x in idx["sections"] if x["t"][-1] == "善意取得")
        self.assertEqual(s["a"], [311])                                  # “第三百一十一条”规范成 311
        self.assertEqual(knowledge.articles("第185条、第一百八十五条、第二十条"), {185, 20})
        self.assertTrue(self.notes_same())                                # 笔记始终只读

    def test_incremental_refresh_only_rebuilds_changed_files(self):
        knowledge.ensure(self.p, BOARD, NAME)
        f = self.vault / NAME / "合同/合同总论.md"
        reads = []
        raw = Path.read_text

        def spy(self_, *a, **k):
            reads.append(self_.name)
            return raw(self_, *a, **k)
        time.sleep(0.01)
        f.write_text(CONTRACT + "\n## 无权代理\n\n表见代理的要件。\n", encoding="utf-8")
        with patch.object(Path, "read_text", spy):
            idx = knowledge.ensure(self.p, BOARD, NAME)
        self.assertEqual([r for r in reads if r.endswith(".md")], ["合同总论.md"])   # 没改的笔记不重读
        self.assertTrue(any(s["t"][-1] == "无权代理" for s in idx["sections"]))
        f.unlink()
        idx = knowledge.ensure(self.p, BOARD, NAME)
        self.assertFalse(any(s["f"].endswith("合同总论.md") for s in idx["sections"]))   # 删掉的文件从索引里去掉

    def test_code_fences_do_not_make_headings(self):
        d = self.vault / NAME / "物权/代码.md"
        d.write_text("# 说明\n\n```\n# 这不是标题\n```\n\n## 真标题\n\n正文", encoding="utf-8")
        titles = [" › ".join(s["t"]) for s in knowledge.ensure(self.p, BOARD, NAME)["sections"] if s["f"].endswith("代码.md")]
        self.assertEqual(titles, ["说明", "说明 › 真标题"])


class LocateTest(Base):
    def test_chapter_article_and_keywords(self):
        r = knowledge.locate(self.p, BOARD, NAME, self.q(chapter="10-科目/民法/物权"))
        self.assertTrue(r["found"])
        first = r["sections"][0]
        self.assertIn("善意取得", first["title"])
        self.assertTrue(any("章节归属" in w for w in first["why"]))
        self.assertFalse(any("合同" in s["display"] for s in r["sections"]))        # 别的章节的内容不进来
        r2 = knowledge.locate(self.p, BOARD, NAME, self.q(stem="依据第四百七十一条，订立合同的方式是什么？", options={}, topic=""))
        self.assertIn("合同的订立", r2["sections"][0]["title"])
        self.assertTrue(any("法条第471条" in w for w in r2["sections"][0]["why"]))

    def test_nothing_relevant_says_so_and_does_not_invent(self):
        text, used, found = knowledge.tutor_text(self.p, BOARD, NAME, self.q(stem="完全无关的内容zzz", options={}, topic="", chapter=""))
        self.assertFalse(found)
        self.assertEqual(used, [])
        self.assertIn("没有在你的笔记里找到", text)
        self.assertIn("现行法条", text)

    def test_budget_truncation_and_skipped_are_explicit(self):
        big = self.vault / NAME / "物权/长.md"
        big.write_text("# 长\n\n## 善意取得的条件\n\n" + "善意取得所有权。" * 2000, encoding="utf-8")
        with patch.object(knowledge, "SECTION_LIMIT", 300):
            r = knowledge.locate(self.p, BOARD, NAME, self.q(chapter="10-科目/民法/物权"))
        cut = [s for s in r["sections"] if s["truncated"]]
        self.assertTrue(cut)
        self.assertIn("只读入前 300 字", r["text"])
        with patch.object(knowledge, "SECTION_LIMIT", 300):
            r = knowledge.locate(self.p, BOARD, NAME, self.q(chapter="10-科目/民法/物权"), budget=350)
        self.assertTrue(r["skipped"])
        self.assertTrue(any(u.endswith("（未读入：超出预算）") for u in r["used"]))
        self.assertTrue(r["total"] <= 350)

    def test_annotations_join_with_source_and_analysis_comes_first(self):
        annotations.save(self.p, BOARD, "物权.md", "# 善意取得易错点\n\n善意取得要看受让人善意，别忘了登记。", "")
        annotations.create_analysis(self.p, BOARD)
        r = knowledge.locate(self.p, BOARD, NAME, self.q(chapter="10-科目/民法/物权"))
        names = [s["display"] for s in r["sections"]]
        self.assertTrue(names[0].startswith("批注/民法/分析套路.md"))
        self.assertTrue(any(n.startswith("批注/民法/物权.md") for n in names))
        self.assertIn("我的批注", [w for s in r["sections"] for w in s["why"]])
        self.assertTrue(self.notes_same())


class AnnotationTest(Base):
    def test_save_edit_conflict_history_restore_delete_rename(self):
        r = annotations.save(self.p, BOARD, "合同.md", "# 合同批注\n第一版", "")
        self.assertTrue(r["changed"])
        r2 = annotations.save(self.p, BOARD, "合同.md", "第二版", r["rev"])
        with self.assertRaises(annotations.AnnError) as c:
            annotations.save(self.p, BOARD, "合同.md", "拿旧版本号", r["rev"])
        self.assertTrue(c.exception.conflict)
        self.assertEqual(annotations.read_file(self.p, BOARD, "合同.md")["text"], "第二版")
        h = annotations.history(self.p, BOARD, "合同.md")
        self.assertEqual(len(h), 1)
        r3 = annotations.restore(self.p, BOARD, "合同.md", h[0]["id"], r2["rev"])
        self.assertIn("第一版", annotations.read_file(self.p, BOARD, "合同.md")["text"])
        ren = annotations.rename(self.p, BOARD, "合同.md", "合同法.md", r3["rev"])
        annotations.delete(self.p, BOARD, "合同法.md", ren["rev"])
        self.assertEqual(annotations.files(self.p, BOARD), [])
        self.assertTrue(annotations.history(self.p, BOARD, "合同法.md"))                 # 删掉的也能找回

    def test_bad_paths_and_limits(self):
        for bad in ("../x.md", "/etc/x.md", "a/b/c/d.md", "x.txt", ".h.md", "", "a:b.md"):
            with self.assertRaises(annotations.AnnError, msg=bad):
                annotations.save(self.p, BOARD, bad, "x", "")
        with self.assertRaises(annotations.AnnError):
            annotations.save(self.p, BOARD, "big.md", "字" * (annotations.MAX_FILE + 1), "")
        for bad in ("", "..", ".历史", "a/b"):
            with self.assertRaises(annotations.AnnError, msg=bad):
                annotations.board_dir(self.p, bad)

    def test_proposals_accept_append_new_never_overwrite(self):
        annotations.save(self.p, BOARD, "物权.md", "原批注", "")
        p = annotations.add_proposal(self.p, BOARD, "补一条", [{"path": "物权.md", "action": "append", "text": "新易错点"},
                                                              {"path": "物权.md", "action": "new", "text": "覆盖？"},
                                                              {"path": "../x.md", "action": "append", "text": "越界"},
                                                              {"path": "z.md", "action": "replace", "text": "覆盖"}], {"label": "试炼复盘 x"}, "k1")
        self.assertEqual(len(p["edits"]), 2)
        self.assertEqual(annotations.add_proposal(self.p, BOARD, "x", [{"path": "a.md", "action": "new", "text": "t"}], None, "k1")["id"], p["id"])
        r = annotations.accept(self.p, BOARD, p["id"], [0, 1])
        self.assertEqual((r["applied"], r["left"]), (["物权.md"], 1))
        self.assertIn("没有覆盖", r["skipped"][0])
        text = annotations.read_file(self.p, BOARD, "物权.md")["text"]
        self.assertTrue(text.startswith("原批注") and "新易错点" in text and "覆盖？" not in text)
        self.assertIn("采纳「补一条」", annotations.read_file(self.p, BOARD, "变更记录.md")["text"])
        with self.assertRaises(annotations.AnnError):
            annotations.accept(self.p, "刑法", p["id"], [1])
        annotations.dismiss(self.p, p["id"])
        self.assertEqual(annotations.proposals(self.p, BOARD), [])


class AITest(Base):
    def test_ai_locate_validates_ids_pins_and_does_not_repeat(self):
        q = self.q(chapter="")
        cat = dict(knowledge.catalog(self.p, BOARD, NAME, q))
        good = next(k for k in cat if "违约责任" in k)
        with patch.object(ai, "available", return_value=True), \
                patch.object(ai, "chat_json", return_value={"ids": [good, "编造的编号"], "reason": "r"}) as call:
            r, why = knowledge_ai.ai_locate(self.p, BOARD, NAME, q)
            r2, why2 = knowledge_ai.ai_locate(self.p, BOARD, NAME, q)
        self.assertEqual(call.call_count, 1)
        self.assertIn("固定", why)
        self.assertTrue(any("违约责任" in s["title"] and any("AI" in w for w in s["why"]) for s in r["sections"]))
        sent = call.call_args[0][0][1]["content"]
        self.assertNotIn("要约与承诺的构成要件", sent)                               # 只给目录，不给笔记正文
        # 以后同一道题的解惑也用这个结果
        self.assertTrue(any("违约责任" in s["title"] for s in knowledge.locate(self.p, BOARD, NAME, q)["sections"]))

    def test_ai_locate_unavailable_or_no_valid_pick(self):
        with patch.object(ai, "available", return_value=False), self.assertRaises(annotations.AnnError) as c:
            knowledge_ai.ai_locate(self.p, BOARD, NAME, self.q())
        self.assertIn("API key", str(c.exception))
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value={"ids": ["假的"]}):
            r, why = knowledge_ai.ai_locate(self.p, BOARD, NAME, self.q(stem="随便", options={}))
        self.assertIn("没有", why)

    def test_note_not_needed_and_needed(self):
        ctx = {"question": "题", "answer": "A", "mine": "B", "explain": "讲解"}
        q = self.q(chapter="10-科目/民法/物权")
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value={"needed": False}):
            self.assertIsNone(knowledge_ai.note(self.p, BOARD, NAME, q, ctx, "来源")[0])
        reply = {"needed": True, "summary": "补易错点", "edits": [{"path": "物权.md", "action": "append", "text": "善意取得要三个条件", "reason": "常错"}]}
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value=reply) as call:
            prop, _ = knowledge_ai.note(self.p, BOARD, NAME, q, ctx, "试炼复盘 x")
            again, _ = knowledge_ai.note(self.p, BOARD, NAME, q, ctx, "试炼复盘 x")
        self.assertEqual((prop["id"], call.call_count), (again["id"], 1))
        self.assertIn("善意取得", call.call_args[0][0][1]["content"])               # 定位到的笔记原文一起给 AI
        self.assertEqual(annotations.files(self.p, BOARD), [])                      # 只是建议，没写批注


class TutorTest(Base):
    def test_explain_uses_located_knowledge_and_law_prompt(self):
        with api.open_game(save=False) as g:
            q = self.q(chapter="10-科目/民法/物权")
            text, used, mode = trainer._tutor_material(g, BOARD, q)
            self.assertEqual(mode, trainer.KNOW)
            self.assertIn("善意取得", text)
            self.assertTrue(used and all("合同" not in u for u in used))
            with patch.object(trainer.ai, "chat", return_value="讲解") as chat:
                out, skill, used2 = trainer._explain(g, q, {"answer": "B"})
            self.assertEqual((out, skill), ("讲解", trainer.KNOW))
            system = chat.call_args[0][0][0]["content"]
            self.assertIn("知识点", system)
            self.assertIn("严谨", system)
            self.assertIn("依据知识点", trainer._source_note(skill, used2))
            self.assertIn("没有在你的笔记里找到", trainer._source_note(trainer.KNOW, []))
            self.assertEqual(trainer._skill_digest(g, BOARD, "善意取得"), trainer._tutor_material(g, BOARD, None, "善意取得")[0])

    def test_skill_boards_keep_old_behavior(self):
        sk = self.vault / "copilot/skills/some-skill"
        sk.mkdir(parents=True)
        (sk / "SKILL.md").write_text("# 方法\n原 skill", encoding="utf-8")
        with api.open_game(save=False) as g, patch.object(trainer, "_skill_name", return_value="some-skill"):
            text, used, mode = trainer._tutor_material(g, BOARD, self.q())
        self.assertEqual(mode, "skill")
        self.assertIn("原 skill", text)

    def test_annote_messages(self):
        with api.open_game(save=False) as g:
            q = self.q(chapter="10-科目/民法/物权")
            self.assertIn("先点", trainer._annote(g, BOARD, q, "A", "B", None, "来源")[0]["text"])
            with patch.object(ai, "available", return_value=False):
                self.assertIn("没连上 AI", trainer._annote(g, BOARD, q, "A", "B", "讲解", "来源")[0]["text"])
            reply = {"needed": True, "summary": "补易错点", "edits": [{"path": "物权.md", "action": "append", "text": "x"}]}
            with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value=reply):
                self.assertIn("补易错点", trainer._annote(g, BOARD, q, "A", "B", "讲解", "来源")[0]["text"])


class ApiTest(Base):
    def test_overview_tree_section_preview(self):
        v = api.knowledge_view({})
        row = next(b for b in v["boards"] if b["board"] == BOARD)
        self.assertTrue(row["notes"])
        tree = api.knowledge_tree({"board": BOARD})["files"]
        f = next(x for x in tree if x["display"].endswith("物权变动.md"))
        sec = api.knowledge_section({"board": BOARD, "key": f["key"], "title": f["sections"][0]["title"]})
        self.assertIn("物权", sec["text"])
        for bad in ({"key": "n:../../etc/passwd", "title": "x"}, {"key": f["key"], "title": "不存在的标题"}):
            with self.assertRaises(api.ApiError):
                api.knowledge_section(dict(board=BOARD, **bad))
        pv = api.knowledge_preview({"board": BOARD, "question": "善意取得所有权须满足什么条件", "chapter": "10-科目/民法/物权"})
        self.assertTrue(pv["found"] and pv["sections"] and pv["sections"][0]["excerpt"])
        with self.assertRaises(api.ApiError):
            api.knowledge_preview({"board": "不存在的科目", "question": "x"})

    def test_annotation_endpoints_edit_and_take_effect(self):
        api.annotations_save({"board": BOARD, "path": "物权.md", "text": "# 我的批注\n善意取得别漏了善意要件", "base": ""})
        f = api.annotations_file({"board": BOARD, "path": "物权.md"})
        api.annotations_save({"board": BOARD, "path": "物权.md", "text": "# 我的批注\n善意取得别漏了善意要件，改过", "base": f["rev"]})
        with self.assertRaises(api.ApiError):
            api.annotations_save({"board": BOARD, "path": "物权.md", "text": "旧", "base": f["rev"]})
        with api.open_game(save=False) as g:
            text, used, _ = trainer._tutor_material(g, BOARD, self.q(chapter="10-科目/民法/物权"))
        self.assertIn("改过", text)                                                    # 保存即生效
        self.assertTrue(any(u.startswith("批注/民法/物权.md") for u in used))
        v = api.annotations_view({"board": BOARD})
        self.assertEqual(v["files"], ["物权.md"])
        h = api.annotations_history({"board": BOARD, "path": "物权.md"})["versions"]
        self.assertEqual(len(h), 1)
        self.assertIn("善意取得", api.annotations_history({"board": BOARD, "path": "物权.md", "id": h[0]["id"]})["text"])
        self.assertTrue(self.notes_same())


if __name__ == "__main__":
    unittest.main()
