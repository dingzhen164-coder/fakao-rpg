"""玉简（记忆卡片）：Markdown 存取、FSRS 排期、每日上限、撤销、简匣、导入、藏简阁、心跳计时。"""
import legacy_xingce  # noqa: F401  行测底本配置（见 tests/legacy_xingce.py）
import datetime as dt
import tempfile
import time
import unittest
from pathlib import Path

from rpg import api, cards, config, engine, paths, store


class CardsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        (self.vault / "copilot/skills").mkdir(parents=True)
        self.p = paths.Paths(self.vault)
        self.p.ensure_train_dir()
        self.day = dt.date(2026, 10, 7)
        self.g = engine.Game(self.p, config.Rules(), config.Persona(), config.Lines(), store.new_state(self.day), self.day)
        cards._CACHE["key"] = None

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, front, back="答", deck="资料分析::速算", typ="问答", tags=""):
        return cards.add(self.g, {"deck": deck, "type": typ, "front": front, "back": back, "tags": tags})

    def test_markdown_round_trip_and_obsidian_edits(self):
        r = self.add("隔年增长率怎么算？", "r = r1 + r2 + r1×r2", tags="增长 公式")
        f = self.vault / "训练/卡片/资料分析.md"
        text = f.read_text(encoding="utf-8")
        self.assertIn("## 玉简 %s\n简匣: 资料分析::速算\n类型: 问答\n标签: 增长 公式\n### 正\n隔年增长率怎么算？" % r["id"], text)
        # 在 Obsidian 里手写一枚没编号的：读到时补上编号，写回文件
        f.write_text(text + "## 玉简\n简匣: 资料分析\n类型: 填空\n### 正\n比重差小于 {{c1::增长率差}}，{{c2::右边}}\n### 反\n\n", encoding="utf-8")
        notes, _ = cards.load(self.p)
        self.assertEqual(len(notes), 2)
        self.assertTrue(notes[1]["id"])
        self.assertIn("## 玉简 %s\n" % notes[1]["id"], f.read_text(encoding="utf-8"))
        self.assertEqual(cards.card_ords(notes[1]), ["c1", "c2"])
        # 改内容不丢进度
        key = "%s#1" % r["id"]
        cards.answer(self.g, key, 4)
        cards.update(self.g, {"id": r["id"], "back": "r1 + r2 + r1·r2"})
        self.assertEqual(self.g.state["cards"]["sched"][key]["st"], 2)
        # 换到别的顶层简匣 = 换文件
        cards.move(self.g, [r["id"]], "数量关系::工程")
        self.assertIn(r["id"], (self.vault / "训练/卡片/数量关系.md").read_text(encoding="utf-8"))
        self.assertNotIn(r["id"], f.read_text(encoding="utf-8"))

    def test_fsrs_learning_steps_and_intervals(self):
        r = self.add("问")
        key = "%s#1" % r["id"]
        now = time.time()
        iv = cards.intervals(self.g, key, "资料分析::速算", now)
        self.assertEqual((iv[1], iv[2], iv[3]), ("1分钟", "6分钟", "10分钟"))
        self.assertTrue(iv[4].endswith("天"))
        cards.answer(self.g, key, 3, now=now)                       # 通透 → 第二步 10 分钟
        s = self.g.state["cards"]["sched"][key]
        self.assertEqual((s["st"], s["step"]), (1, 1))
        cards.answer(self.g, key, 3, now=now + 700)                 # 再通透 → 毕业，进复习
        s = self.g.state["cards"]["sched"][key]
        self.assertEqual(s["st"], 2)
        self.assertGreaterEqual(s["ivl"], 1)
        # 复习卡：四个评分的间隔 晦涩 ≤ 通透 < 了然，再参进入重参
        s.update(due=self.g.state["cards"]["today"]["d"], last=(dt.date.fromisoformat(s["due"]) - dt.timedelta(days=4)).isoformat())
        iv = cards.intervals(self.g, key, "资料分析::速算", now)
        days = [float(iv[k][:-1]) for k in (2, 3, 4)]
        self.assertTrue(days[0] <= days[1] < days[2])
        self.assertEqual(iv[1], "10分钟")
        cards.answer(self.g, key, 1, now=now)
        s = self.g.state["cards"]["sched"][key]
        self.assertEqual((s["st"], s["lapses"]), (3, 1))

    def test_queue_limits_undo_and_siblings(self):
        for i in range(5):
            self.add("问%d" % i)
        rev = self.add("正", "反", typ="问答+反向")
        cards.deck_action(self.g, {"action": "options", "name": "资料分析", "options": {"new_per_day": 3}})
        order, counts, _ = cards.queue(self.g, "资料分析")
        self.assertEqual(counts["new"], 3)                          # 上层的每日新简数管着子匣
        first = order[0]
        xp = self.g.state["xp"]
        cards.answer(self.g, first, 4)
        self.assertEqual(self.g.state["xp"], xp + cards.XP[4])
        _, counts, _ = cards.queue(self.g, "资料分析")
        self.assertEqual(counts["new"], 2)
        self.assertEqual(cards.undo(self.g), first)
        _, counts, _ = cards.queue(self.g, "资料分析")
        self.assertEqual(counts["new"], 3)
        self.assertEqual(self.g.state["xp"], xp)
        self.assertNotIn(first, self.g.state["cards"]["sched"])
        # 反向玉简：正向温过后，反向今天不再出
        cards.deck_action(self.g, {"action": "options", "name": "资料分析", "options": {"new_per_day": 50}})
        cards.answer(self.g, rev["id"] + "#1", 4)
        order, _, _ = cards.queue(self.g, "资料分析")
        self.assertNotIn(rev["id"] + "#2", order)
        # 暂停的卡不出
        cards.suspend(self.g, [order[0]])
        self.assertNotIn(order[0], cards.queue(self.g, "资料分析")[0])

    def test_tree_rename_delete_and_search(self):
        self.add("甲", deck="资料分析::速算")
        self.add("乙", deck="资料分析::比重", tags="比重")
        tree = {d["name"]: d for d in cards.tree(self.g)}
        self.assertIn("政治理论", tree)                              # 默认 12 个板块
        self.assertEqual((tree["资料分析"]["new"], tree["资料分析::速算"]["new"], tree["资料分析::速算"]["depth"]), (2, 1, 1))
        cards.deck_action(self.g, {"action": "rename", "name": "资料分析::速算", "new": "资料分析::速算技巧"})
        self.assertEqual(cards.search(self.g, {"q": "甲"})["rows"][0]["deck"], "资料分析::速算技巧")
        self.assertEqual(cards.search(self.g, {"q": "比重"})["total"], 1)
        with self.assertRaises(cards.CardError):
            cards.deck_action(self.g, {"action": "delete", "name": "资料分析"})
        cards.deck_action(self.g, {"action": "delete", "name": "资料分析", "with_cards": True})
        self.assertEqual(cards.search(self.g, {})["total"], 0)
        with self.assertRaises(cards.CardError):
            self.add("{{c1}}不对", typ="填空")

    def test_import_anki_text_and_markdown_table(self):
        txt = "#separator:tab\n#html:true\n<b>增长量</b>公式？\t现期×r/(1+r)\t增长\n{{c1::基期}} = 现期/(1+r)\t\n坏行\n"
        r = cards.import_text(self.g, {"deck": "资料分析", "text": txt})
        self.assertEqual((r["added"], r["skipped"]), (2, 1))
        rows = cards.search(self.g, {"deck": "资料分析"})["rows"]
        self.assertEqual(cards.note_get(self.g, rows[0]["id"])["front"], "**增长量**公式？")   # Anki 的粗体转成 Markdown
        self.assertEqual(rows[0]["front"], "增长量公式？")                                       # 藏简阁列表里显示纯文字
        self.assertEqual(rows[1]["type"], "填空")
        table = "Question | Answer | Tags\n------- | -------- | --------\n什么是比重？ | 部分/整体 | 比重\n"
        self.assertEqual(cards.import_text(self.g, {"deck": "资料分析", "text": table.replace(" | ", "|")}) ["added"], 0)
        r = cards.import_text(self.g, {"deck": "资料分析", "text": "#separator:pipe\n" + table})
        self.assertEqual(r["added"], 1)

    def test_import_tables_become_markdown_tables(self):
        """HTML 表格（含 rowspan / colspan 合并格）→ Markdown 表格：左上角那格写内容，被盖住的格子写“〃”；整行合并的第一行是题注"""
        html = ('<div>前言</div><table><tr><th colspan="3">题注</th></tr>'
                '<tr><th>类型</th><th>年龄</th><th>效力</th></tr>'
                '<tr><td rowspan="2">限制</td><td>8周岁以上</td><td>有效</td></tr>'
                '<tr><td>不满18周岁</td><td>待定<br>（追认）</td></tr></table><div>后话</div>')
        self.assertEqual(cards.html_to_md(html),
                         "前言\n\n**题注**\n\n| 类型 | 年龄 | 效力 |\n|---|---|---|\n"
                         "| 限制 | 8周岁以上 | 有效 |\n| 〃 | 不满18周岁 | 待定 （追认） |\n\n后话")
        # 没有 <th> 表头的表：留一行空表头；跨列盖住的格子写“⇢”，跨行写“〃”
        self.assertEqual(cards.html_to_md('<table><tr><td>条约</td><td colspan="2">有义务继承</td></tr><tr><td rowspan="2">债务</td><td>对象</td><td>x</td></tr>'
                                          '<tr><td>规则</td><td>y</td></tr></table>'),
                         "|   |   |   |\n|---|---|---|\n| 条约 | 有义务继承 | ⇢ |\n| 债务 | 对象 | x |\n| 〃 | 规则 | y |")
        # 单元格里的竖线要转义；没有合并格的普通表
        self.assertIn("| a\\|b | c |", cards.html_to_md("<table><tr><th>x</th><th>y</th></tr><tr><td>a|b</td><td>c</td></tr></table>"))
        # 导入后卡面能渲染出表格所需的 Markdown（正面 / 反面都保留）
        r = cards.import_text(self.g, {"deck": "表格", "text": "三分法\t" + html})
        self.assertEqual(r["added"], 1)
        note = cards.search(self.g, {"deck": "表格"})["rows"][0]
        self.assertIn("| 〃 | 不满18周岁 |", cards.note_get(self.g, note["id"])["back"])

    def test_import_colors_lists_headings_and_reimport_updates(self):
        back = ('<h3 style="color: rgb(41, 128, 185)">6 类关键信息</h3><ol><li><b style="color:#c0392b">定义词（拆词法）</b>：拆开</li>'
                '<li><b>主客体</b>：谁对谁做</li></ol><div>出处：第1章&nbsp;五</div>')
        self.assertEqual(cards.html_to_md(back),
                         '### <span style="color:rgb(41, 128, 185)">6 类关键信息</span>\n\n1. **<span style="color:#c0392b">定义词（拆词法）</span>**：拆开\n'
                         '2. **主客体**：谁对谁做\n\n出处：第1章 五')
        self.assertEqual(cards.html_to_md('<font color="red">红</font><span style="color:black">黑</span>'), '<span style="color:red">红</span>黑')
        r = cards.import_text(self.g, {"deck": "定义判断", "text": "要抓哪几类关键信息？\t" + back.replace("<b style", "<b data-x style")})
        self.assertEqual(r["added"], 1)
        nid = cards.search(self.g, {"deck": "定义判断"})["rows"][0]["id"]
        n = cards.note_get(self.g, nid)
        self.assertIn("### ", n["back"])                       # 反面里的小标题不会把反面截断
        self.assertIn("出处：第1章 五", n["back"])
        cards._CACHE["key"] = None
        self.assertIn("出处：第1章 五", cards.note_get(self.g, nid)["back"])   # 存盘再读也一样
        r = cards.import_text(self.g, {"deck": "定义判断", "text": "要抓哪几类关键信息？\t<b>新内容</b>"})
        self.assertEqual((r["added"], r["updated"]), (0, 1))   # 同一个正面：更新，不重复
        self.assertEqual(cards.note_get(self.g, nid)["back"], "**新内容**")

    def test_stats_and_info(self):
        r = self.add("问")
        key = r["id"] + "#1"
        cards.answer(self.g, key, 4, secs=12)
        st = cards.stats(self.g)
        self.assertEqual((st["total_reviews"], st["streak"], st["retention"]), (1, 1, 1.0))
        self.assertEqual(sum(st["forecast"]), 1)
        inf = cards.info(self.g, key)
        self.assertEqual(inf["history"][0]["rating"], "了然")
        self.assertEqual(inf["sched"]["state"], "复习")


class CardsApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        (self.vault / "copilot/skills").mkdir(parents=True)
        self._settings = paths.SETTINGS_FILE, paths.SETTINGS_DIR
        paths.SETTINGS_DIR = self.vault / ".home"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        paths.save_settings({"vault": str(self.vault)})
        cards._CACHE["key"] = None

    def tearDown(self):
        paths.SETTINGS_FILE, paths.SETTINGS_DIR = self._settings
        self.tmp.cleanup()

    def test_review_flow_and_heartbeat(self):
        api.cards_add({"deck": "言语", "type": "问答", "front": "“不刊之论”的刊？", "back": "删改"})
        r = api.cards_next({"deck": "言语"})
        self.assertEqual(r["card"]["front"], "“不刊之论”的刊？")
        self.assertEqual(r["intervals"]["1"] if "1" in r["intervals"] else r["intervals"][1], "1分钟")
        cards.LAST_ANSWER["t"] = 0
        self.assertFalse(api.heartbeat({"seconds": 30, "cards": True})["studying"])      # 没温简不算
        r = api.cards_answer({"deck": "言语", "key": r["card"]["key"], "rating": 4, "secs": 8})
        self.assertTrue(r["done"])
        hb = api.heartbeat({"seconds": 60, "cards": True})
        self.assertTrue(hb["studying"])
        self.assertEqual(hb["minutes"], 1)
        r = api.cards_undo({"deck": "言语"})
        self.assertEqual(r["card"]["front"], "“不刊之论”的刊？")
        d = api.dashboard({})
        self.assertTrue(any(t["type"] == "cards" for t in d["plan"]["tasks"]))


class CardGenTest(CardsApiTest):
    """📄 PDF 制卡（扫描版教材 PDF → 知识点卡 → 刻入）和 AI 方案切换"""

    def _pdf(self):
        """合成一页：「第一部分 国际法」「第一章 …」「知识点一」和标题名是同一行里的两个文字框，一张带合并格的表，然后是知识点二"""
        import pymupdf
        doc = pymupdf.open()
        p = doc.new_page(width=523, height=750)
        f = dict(fontname="china-s", fontsize=12)
        p.insert_text((200, 90), "第一部分", **f); p.insert_text((280, 90), "国际法", **f)
        p.insert_text((195, 150), "第一章", **f); p.insert_text((250, 150), "国际法的渊源", **f)
        p.insert_text((60, 200), "知识点一", **f); p.insert_text((130, 200), "国际法的渊源", **f)
        p.insert_text((60, 230), "国际法的渊源只有国际条约、国际习惯和一般法律原则三项。", **f)
        x0, x1, xm, ys = 60, 460, 140, [260, 300, 340, 380]
        for y in ys:
            p.draw_line((x0, y), (x1, y), width=1.2)
        for x in (x0, xm, x1):
            p.draw_line((x, ys[0]), (x, ys[-1]), width=1.2)
        for k, (a, b) in enumerate([("国际条约", "原则上只约束缔约国"), ("国际习惯", "约束所有主体"), ("一般法律原则", "约束所有主体")]):
            p.insert_text((x0 + 6, ys[k] + 24), a, **f); p.insert_text((xm + 6, ys[k] + 24), b, **f)
        p.insert_text((60, 430), "知识点二", **f); p.insert_text((130, 430), "国际法基本原则", **f)
        p.insert_text((60, 460), "国家主权平等原则、不干涉内政原则。", **f)
        return "data:application/pdf;base64," + __import__("base64").b64encode(doc.tobytes()).decode()

    def _src(self, sid):
        import time
        for _ in range(100):
            st = api.cards_pdf_src({"src": sid})
            if st["state"] != "running":
                return st
            time.sleep(0.1)
        self.fail("数页数超时")

    def test_pdf_cards_end_to_end(self):
        import time
        from rpg import pdfcards
        if not pdfcards.available()[0]:
            self.skipTest("没装 opencv / numpy")
        reg = api.cards_pdf_load({"name": "国际法讲义.pdf", "data": self._pdf()})
        info = self._src(reg["src"])
        self.assertEqual((info["pages"], info["subject"], info["units"]["知识点"]), (1, "国际法", 2))   # 编号和标题分成两个框也认得出
        job = api.cards_pdf_start({"src": info["src"], "subject": "国际法"})["job"]
        for _ in range(120):
            st = api.cards_pdf_status({"job": job})
            if st["state"] != "running":
                break
            time.sleep(0.5)
        self.assertEqual(st["state"], "done", st)
        self.assertEqual([c["front"] for c in st["cards"]], ["【国际法1.1.1】国际法的渊源", "【国际法1.1.2】国际法基本原则"])
        self.assertIn("| 国际条约 | 原则上只约束缔约国 |", st["cards"][0]["back"])      # 表格是 Markdown，没有表头的留空表头
        self.assertTrue(st["cards"][0]["back"].count("|---|---|") == 1)
        a = api.cards_pdf_save({"job": job, "deck": "国际法", "subject": "国际法",
                                "cards": [{"front": c["front"], "back": c["back"], "tags": c["tags"]} for c in st["cards"]]})
        self.assertEqual((a["added"], a["duplicated"]), (2, 0))
        again = api.cards_pdf_save({"job": job, "deck": "国际法", "subject": "国际法", "cards": [{"front": st["cards"][0]["front"], "back": "x"}]})
        self.assertEqual((again["added"], again["duplicated"]), (0, 1))          # 同一本书导入两次不会翻倍
        self.assertEqual(api.cards_search({"deck": "国际法"})["total"], 2)

    def test_pdf_upload_stream(self):
        import io
        from rpg import paths, pdfcards
        if not pdfcards.available()[0]:
            self.skipTest("没装 opencv / numpy")
        raw = __import__("base64").b64decode(self._pdf().split(",", 1)[1])
        r = self._src(pdfcards.load_stream(paths.SETTINGS_DIR, "民法讲义.pdf", io.BytesIO(raw), len(raw))["src"])
        self.assertEqual((r["pages"], r["subject"], r["units"]["知识点"]), (1, "民法", 2))
        # 直接读本机文件（不上传）
        f = paths.SETTINGS_DIR / "本机.pdf"
        f.write_bytes(raw)
        r2 = self._src(api.cards_pdf_open({"path": str(f)})["src"])
        self.assertEqual((r2["pages"], r2["units"]["知识点"]), (1, 2))
        with self.assertRaises(api.ApiError):
            api.cards_pdf_open({"path": str(paths.SETTINGS_DIR / "不存在.pdf")})
        with self.assertRaises(pdfcards.PdfCardError):
            pdfcards.load_stream(paths.SETTINGS_DIR, "x.pdf", io.BytesIO(b"hello world"), 11)
        with self.assertRaises(pdfcards.PdfCardError):
            pdfcards.load_stream(paths.SETTINGS_DIR, "x.pdf", io.BytesIO(raw[:50]), len(raw))        # 没传完

    def test_pdf_cards_section_units(self):
        """法理学这类没有「知识点」标题的书：「第一章 / 第一节」下面的「一、二、三、」各做一张卡，自动认出来"""
        import pymupdf
        from rpg import paths, pdfcards
        if not pdfcards.available()[0]:
            self.skipTest("没装 opencv / numpy")
        doc = pymupdf.open()
        p = doc.new_page(width=523, height=750)
        f = dict(fontname="china-s", fontsize=12)
        for y, t in [(110, "第一章  法的本体"), (150, "第一节  法的定义"), (190, "一、法概念的争议"), (230, "法律和道德之间的联系。"),
                     (270, "二、马克思主义关于法律本质的看法"), (310, "法的正式性。"), (350, "三、法的特征"), (390, "法是调整人的行为的规范。")]:
            p.insert_text((60, y), t, **f)
        f_ = paths.SETTINGS_DIR / "法理学.pdf"
        f_.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(f_))
        r = pdfcards.convert(f_, "法理学")
        self.assertEqual(r["unit"], "小节")
        self.assertEqual([c["front"] for c in r["cards"]], ["【法理学1.1.1】法概念的争议", "【法理学1.1.2】马克思主义关于法律本质的看法", "【法理学1.1.3】法的特征"])

    def _text_pdf(self, rows, name):
        import pymupdf
        from rpg import paths
        doc = pymupdf.open()
        p = doc.new_page(width=523, height=750)
        f = dict(fontname="china-s", fontsize=12)
        for x, y, t in rows:
            p.insert_text((x, y), t, **f)
        f_ = paths.SETTINGS_DIR / name
        f_.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(f_))
        return f_

    def test_pdf_cards_kaodian_with_big_sections(self):
        """商经知这类：「第一章」→「一、概述」→「考点 1  标题」（没有冒号，编号和标题是两个文字框）。「一、概述」是大节标题，不能并进上一个考点"""
        from rpg import pdfcards
        if not pdfcards.available()[0]:
            self.skipTest("没装 opencv / numpy")
        f = self._text_pdf([(200, 80, "第一章  公司法"), (60, 130, "一、概述"), (200, 170, "考点 1"), (270, 170, "公司的概念和特征"),
                            (60, 210, "公司是依法设立的营利性法人。"), (200, 260, "考点 2"), (270, 260, "公司的分类"),
                            (60, 300, "分为有限责任公司和股份有限公司。"), (60, 350, "二、运行"), (200, 390, "考点 3"), (270, 390, "公司治理"),
                            (60, 430, "股东会是权力机构。")], "商经.pdf")
        r = pdfcards.convert(f, "商经知")
        self.assertEqual(r["unit"], "考点")
        self.assertEqual([c["front"] for c in r["cards"]], ["【商经知1.1】公司的概念和特征", "【商经知1.2】公司的分类", "【商经知1.3】公司治理"])
        self.assertNotIn("二、运行", r["cards"][1]["back"])            # 「二、运行」没有被并进上一张卡

    def test_pdf_cards_jiang_and_jie(self):
        """民诉这类：「第三讲」→「第一节」→「一、平等原则」；也有只有「第一讲」→「一、」的"""
        from rpg import pdfcards
        if not pdfcards.available()[0]:
            self.skipTest("没装 opencv / numpy")
        f = self._text_pdf([(160, 60, "第三讲  基本原则与基本制度"), (200, 100, "第一节  基本原则"), (60, 150, "一、平等原则"),
                            (60, 180, "平等原则指诉讼当事人诉讼权利、义务平等。"), (60, 230, "二、同等、对等原则"), (60, 260, "同等原则指外国人享有同样的诉讼权利。"),
                            (60, 310, "三、辩论原则"), (60, 340, "辩论原则指当事人有权进行辩论。")], "民诉.pdf")
        r = pdfcards.convert(f, "民诉")
        self.assertEqual([c["front"] for c in r["cards"]], ["【民诉3.1.1】平等原则", "【民诉3.1.2】同等、对等原则", "【民诉3.1.3】辩论原则"])

    def test_pdf_cards_errors(self):
        with self.assertRaises(api.ApiError):
            api.cards_pdf_load({"name": "x.pdf", "data": "data:application/pdf;base64,"})
        with self.assertRaises(api.ApiError):
            api.cards_pdf_start({"src": "0" * 16})
        with self.assertRaises(api.ApiError):
            api.cards_pdf_status({"job": "nope"})

    def test_ai_profiles_switch(self):
        api.settings_set({"api_key": "sk-deep", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"})
        api.ai_profile({"action": "save", "name": "DeepSeek"})
        api.settings_set({"api_key": "sk-qwen", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"})
        s = api.settings_get({})
        self.assertEqual(s["ai_active"], "")                                 # 改了设置：不再是 DeepSeek 那套
        api.ai_profile({"action": "save", "name": "千问"})
        s = api.ai_profile({"action": "use", "name": "DeepSeek"})
        self.assertEqual((s["model"], s["key_tail"], s["ai_active"]), ("deepseek-chat", "deep", "DeepSeek"))
        self.assertEqual([p["name"] for p in s["ai_profiles"]], ["DeepSeek", "千问"])
        self.assertNotIn("api_key", s["ai_profiles"][0])                      # key 不回给网页
        s = api.ai_profile({"action": "use", "name": "千问"})
        self.assertEqual(s["base_url"], "https://dashscope.aliyuncs.com/compatible-mode/v1")
        api.ai_profile({"action": "delete", "name": "千问"})
        self.assertEqual(api.settings_get({})["ai_active"], "")


class CardsMoreTest(CardsApiTest):
    """2.4.0：学姐讲讲只帮记忆并存进玉简、每日数量的总设置、灵脉图（思维导图）"""

    def test_explain_saved_and_prompt(self):
        from unittest.mock import patch
        from rpg import ai
        api.cards_add({"deck": "政治理论", "type": "问答", "front": "逻辑关系包括？", "back": "全同、全异、种属、交叉"})
        key = api.cards_next({"deck": ""})["card"]["key"]
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", return_value="口诀：同异种交\n### 小标题") as chat:
            r = api.cards_explain({"key": key})
        system = chat.call_args.args[0][0]["content"]
        self.assertIn("不评判", system)
        self.assertNotIn("卡片内容如果有错", system)
        self.assertIn("#### ", r["saved"])
        self.assertIn("＃＃＃ 小标题", r["saved"])                       # 回复里的标题降级，不打乱玉简格式
        text = (self.vault / "训练/卡片/政治理论.md").read_text(encoding="utf-8")
        self.assertIn("### 学姐讲讲\n#### ", text)
        cards._CACHE["key"] = None
        self.assertIn("口诀：同异种交", api.cards_next({"deck": ""})["card"]["ai"])
        self.assertTrue(cards.reviewing())                                 # 在温简页面上就算在复习

    def test_global_daily_limits(self):
        for i in range(5):
            api.cards_add({"deck": "资料分析", "type": "问答", "front": "问%d" % i, "back": "答"})
        api.cards_deck({"action": "options", "name": "*", "options": {"new_per_day": 3}})
        self.assertEqual(api.cards_overview({})["defaults"]["new_per_day"], 3)
        self.assertEqual(api.cards_next({"deck": "资料分析"})["counts"]["new"], 3)
        api.cards_deck({"action": "options", "name": "资料分析", "options": {"new_per_day": 4}})   # 单个匣子另设的优先
        self.assertEqual(api.cards_next({"deck": "资料分析"})["counts"]["new"], 4)

    def test_mindmap(self):
        lst = api.mm_list({})
        self.assertEqual(lst["boards"][0], {"board": "政治理论", "maps": []})
        d = api.mm_get({"board": "资料分析", "name": "资料分析"})            # 第一次打开自动建一幅
        self.assertEqual(d["data"]["root"]["data"]["text"], "资料分析")
        root = {"data": {"text": "资料分析"}, "children": [{"data": {"text": "增长"}, "children": [{"data": {"text": "隔年增长"}}]}]}
        self.assertEqual(api.mm_save({"board": "资料分析", "name": "资料分析", "data": {"root": root, "layout": "mindMap"}})["nodes"], 3)
        r = api.mm_create({"board": "资料分析", "name": "资料分析"})
        self.assertEqual(r["name"], "资料分析（2）")                         # 重名加序号
        api.mm_rename({"board": "资料分析", "name": "资料分析（2）", "new": "速算"})
        self.assertEqual([m["name"] for m in api.mm_list({})["boards"][-1]["maps"]], ["资料分析", "速算"])
        e = api.mm_export({"board": "资料分析", "name": "资料分析", "ext": "md",
                           "data": "data:text/markdown;base64," + __import__("base64").b64encode("# 资料分析".encode()).decode()})
        self.assertEqual(e["path"], "训练/灵脉图/导出/资料分析.md")
        self.assertIn("&t=", e["url"])
        with self.assertRaises(api.ApiError):
            api.mm_export({"board": "资料分析", "name": "x", "ext": "exe", "data": "data:,1"})
        with self.assertRaises(api.ApiError):
            api.mm_get({"board": "../x", "name": "y"})
        api.mm_delete({"board": "资料分析", "name": "速算"})
        self.assertEqual(len(api.mm_list({})["boards"][-1]["maps"]), 1)


class IdiomCardsTest(CardsApiTest):
    """成语实词录里学姐答疑过的词条 → 玉简（逻辑填空::成语实词录）"""

    def entry(self, word, tutor=True):
        return {"word": word, "letter": "B", "detail": {"chars": [{"char": "刊", "meaning": "删改", "like": ["刊误"]}],
                                                       "origin": {"from": "《答李翊书》", "text": "", "note": ""}},
                "sources": [{"key": "k", "id": "真题-1", "board": "逻辑填空", "source": "逻辑填空真题.md", "paper": "2024国考",
                             "blank": 1, "blanks": 1, "answer": "A", "option_text": word, "meaning": "不能删改的言论",
                             "others": [{"word": "至理名言", "option": "B", "meaning": "最正确的道理"}],
                             "compare": "不刊之论强调不可更改", "tutor": tutor, "date": "2026-10-07"}]}

    def test_sync(self):
        from rpg import idioms
        with api.open_game() as g:
            idioms.data(g)["不刊之论"] = self.entry("不刊之论")
            idioms.data(g)["没答疑"] = self.entry("没答疑", tutor=False)
        api.cards_overview({})                                              # 第一次打开修炼殿：补做
        rows = api.cards_search({"deck": "逻辑填空::成语实词录"})["rows"]
        self.assertEqual([r["front"] for r in rows], ["不刊之论 （成语 · 说出意思和用法）"])
        n = api.cards_note({"id": rows[0]["id"]})
        for part in ("**释义**：不能删改的言论", "**逐字**：刊 = 删改（同样用法：刊误）", "**出处**：《答李翊书》",
                     "**辨析**：不刊之论强调不可更改", "- 至理名言：最正确的道理"):
            self.assertIn(part, n["back"])
        self.assertNotIn("真题", n["back"])
        # 温过之后再答疑：同一枚玉简改内容，进度不丢
        key = rows[0]["key"]
        api.cards_answer({"deck": "", "key": key, "rating": 4})
        with api.open_game() as g:
            idioms.data(g)["不刊之论"]["sources"][0]["compare"] = "新的辨析"
            idioms.sync_card(g, "不刊之论")
        self.assertIn("新的辨析", api.cards_note({"id": rows[0]["id"]})["back"])
        self.assertEqual(api.cards_info({"key": key})["sched"]["state"], "复习")
        # 删词条：玉简一起删
        with api.open_game() as g:
            idioms.delete(g, "不刊之论")
        self.assertEqual(api.cards_search({"deck": "逻辑填空"})["total"], 0)
