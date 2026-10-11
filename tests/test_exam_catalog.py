"""历年题目录的安全边界、导入一致性、参考匹配与正式判分隔离。"""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import exam_catalog as ex, question_bank as bank
from rpg.paths import Paths

PAPER = '''### 单项选择题
#### 1. 关于证据，下列哪一说法错误？
- [ ] **A.** 甲
- [ ] **B.** 乙
- [ ] **C.** 丙
- [ ] **D.** 丁
#### 2.
关于证据，下列哪一说法正确？
- [ ] **A.** 甲
- [ ] **B.** 乙
- [ ] **C.** 丙
- [ ] **D.** 丁
'''


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Paths(Path(self.tmp.name))
        self.source = self.p.vault / '60-真题库/02-法考回忆版-2018-2025/2025-试卷一.md'
        self.source.parent.mkdir(parents=True)
        self.source.write_text(PAPER, encoding='utf-8')
        self.chapter = '10-科目/04-刑事诉讼法/02-证据'
        (self.p.vault / self.chapter).mkdir(parents=True)
        old = self.p.vault / '60-真题库/03-按学科分类/02-刑法/题.md'
        old.parent.mkdir(parents=True)
        old.write_text('## 2025年 · 试卷一 · 第1题\n', encoding='utf-8')
        self.ident = '2025-试卷一-001'

    def tearDown(self):
        ex.JOBS.pop(str(self.p.vault), None)
        self.tmp.cleanup()

    def imported(self):
        ex.scan(self.p, {'commit': True})
        return ex.detail(self.p, {'id': self.ident, 'reveal': True})

    def edit(self, **kwargs):
        q = ex.detail(self.p, {'id': self.ident})
        return ex.edit(self.p, dict(id=self.ident, revision=q['revision'], **kwargs))

    def test_preview_idempotence_sources_readonly_and_history(self):
        original = self.source.read_bytes()
        self.assertEqual(ex.scan(self.p, {})['total'], 2)
        self.assertFalse(self.p.train.exists())
        q = self.imported()
        self.assertEqual((q['classification'], q['board'], q['legacy_subject']), ('legacy', '刑法', '刑法'))
        ex.practice(self.p, {'id': self.ident, 'answer': 'A'})
        self.edit(chapter=self.chapter, topic='证明责任')
        self.assertEqual(ex.scan(self.p, {'commit': True})['added'], 0)
        q = ex.detail(self.p, {'id': self.ident})
        self.assertEqual((q['board'], len(q['history'])), ('刑诉', 1))
        self.assertEqual(self.source.read_bytes(), original)
        self.assertTrue(list((self.p.train / '题库/历年目录备份').glob('*.json')))

    def test_reference_is_not_answer_or_game_score(self):
        q = self.imported()
        row = {'input': q['stem'] + '\nA. 甲\nB. 乙\nC. 丙\nD. 丁', 'output': 'GPT判断答案是A。'}
        r = ex.references(self.p, {'name': 'sample.json', 'rows': [row]})
        self.assertEqual(r['full'], 1)
        hidden = ex.detail(self.p, {'id': self.ident})
        self.assertNotIn('references', hidden)
        result = ex.practice(self.p, {'id': self.ident, 'answer': 'B'})
        self.assertIsNone(result['result']['ok'])
        self.assertEqual(result['answer'], '')
        self.assertFalse(ex.official_questions(self.p, '刑法'))
        self.assertFalse(self.p.save_file.exists())

    def test_exact_mapping_negation_fact_changes_and_nested_rows(self):
        self.assertNotEqual(ex.normalize('1.5万元'), ex.normalize('15万元'))
        q = self.imported()
        row = {'input': q['stem'] + '\nA. 乙\nB. 甲\nC. 丁\nD. 丙', 'output': 'A是对的'}
        hit = ex.match_references({q['id']: q}, [('nested.json', [[row]])])[q['id']][0]
        self.assertEqual(hit['option_map'], {'A': 'B', 'B': 'A', 'C': 'D', 'D': 'C'})
        row['input'] = row['input'].replace('错误', '正确')
        self.assertEqual(ex.match_references({q['id']: q}, [('x', [row])]), {})
        row['input'] = q['stem'] + '\nA. 甲2\nB. 乙\nC. 丙\nD. 丁'
        self.assertFalse(ex.match_references({q['id']: q}, [('x', [row])]))
        q['material'] = '缺失材料'
        self.assertFalse(ex.match_references({q['id']: q}, [('x', [{'input': q['stem'], 'output': '参考'}])]))

    def test_verification_gate_and_stable_key_after_classification(self):
        self.imported()
        self.edit(answer='A', kind='single', answer_source='教材第8页')
        self.assertFalse(ex.official_questions(self.p, '刑法'))
        self.edit(chapter=self.chapter, topic='证明责任')
        q = ex.official_questions(self.p, '刑诉')[0]
        self.assertEqual(q['key'], '历年::' + self.ident)
        self.assertEqual(bank.topic_head(q['topic'], '刑诉'), '证据')
        self.assertEqual(bank.read_all(self.p, '刑诉')[0][0]['answer'], 'A')
        original = self.source.read_bytes()
        bank.save_tutor_to_bank(self.p, q, 'AI解惑仍需核验', '2026-10-11')
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(ex.detail(self.p, {'id': self.ident, 'reveal': True})['answer_status'], 'verified')
        self.assertIn('AI生成 · 未核验', ex.official_questions(self.p, '刑诉')[0]['analysis'])
        rec = ex.practice(self.p, {'id': self.ident, 'answer': 'A'})
        self.assertTrue(rec['result']['ok'])

    def test_source_change_revokes_answer_but_keeps_history(self):
        self.imported()
        self.edit(chapter=self.chapter, answer='A', answer_source='教材', kind='single')
        ex.practice(self.p, {'id': self.ident, 'answer': 'A'})
        self.source.write_text(PAPER.replace('甲', '甲修订'), encoding='utf-8')
        self.assertEqual(ex.scan(self.p, {'commit': True})['changed'], 2)
        q = ex.detail(self.p, {'id': self.ident, 'reveal': True})
        self.assertEqual(q['answer_status'], 'pending')
        self.assertEqual(len(q['history']), 1)
        self.assertFalse(q['references'])

    def test_invalid_answer_source_revision_and_chapter_do_not_save(self):
        q = self.imported()
        for body in [dict(answer='AB', kind='single', answer_source='教材'), dict(answer='A', kind='single'), dict(chapter='不存在')]:
            with self.assertRaises(ex.CatalogError):
                ex.edit(self.p, dict(id=self.ident, revision=q['revision'], **body))
        self.edit(chapter=self.chapter)
        with self.assertRaises(ex.CatalogError):
            ex.edit(self.p, {'id': self.ident, 'revision': 0, 'chapter': self.chapter})

    def test_shared_material_multiline_and_stray_are_not_option_text(self):
        text = PAPER.replace('#### 2.', '> [!example] 共用材料\n> 请回答第2〜2题\n> 完整材料\n\n#### 2.')
        qs = ex.parse_paper(text, 2025, '试卷一', '原卷')
        self.assertEqual(qs[0]['options']['D'], '丁')
        self.assertIn('完整材料', qs[1]['material'])
        text = PAPER.replace('#### 2.', '> [!example] 共用材料\n> D.这是选项残句\n\n#### 2.')
        qs = ex.parse_paper(text, 2025, '试卷一', '原卷')
        self.assertTrue(qs[0]['warnings'])
        self.assertTrue(qs[1]['warnings'])
        self.assertFalse(qs[1]['material'])
        with self.assertRaises(ex.CatalogError):
            ex.parse_paper(PAPER.replace('- [ ] **C.** 丙\n', ''), 2025, '试卷一', '原卷')

    def test_paths_duplicate_originals_and_corrupt_catalog(self):
        with self.assertRaises(ex.CatalogError):
            ex.scan(self.p, {'folder': '../'})
        self.imported()
        self.source.with_name('2025-试卷二.md').write_text(PAPER, encoding='utf-8')
        another = self.source.parent / '副本/2025-试卷一.md'
        another.parent.mkdir(); another.write_text(PAPER, encoding='utf-8')
        with self.assertRaises(ex.CatalogError):
            ex.scan(self.p, {'commit': True})
        f = self.p.train / '题库/历年目录.json'
        f.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ex.CatalogError):
            ex.load(self.p)
        self.assertEqual(f.read_text(encoding='utf-8'), '{broken')

    def test_ai_suggestions_are_cached_and_batch_confirmation_is_explicit(self):
        self.imported()
        def response(messages, **kwargs):
            ids = [q['id'] for q in json.loads(messages[1]['content'])['questions']]
            return {'items': [dict(id=i, chapter=self.chapter, topic='证明责任', reason='考查证据制度') for i in ids]}
        with patch.object(ex.ai, 'available', return_value=True), patch.object(ex.ai, 'chat_json', side_effect=response) as chat:
            ex.classify(self.p, {'limit': 20})
            for _ in range(100):
                if not ex.JOBS[str(self.p.vault)]['running']: break
                time.sleep(.01)
            self.assertFalse(ex.JOBS[str(self.p.vault)]['running'])
            self.assertEqual(chat.call_count, 1)
            with self.assertRaises(ex.CatalogError):
                ex.classify(self.p, {})
        q = ex.detail(self.p, {'id': self.ident})
        self.assertEqual(q['classification'], 'legacy')
        ex.confirm_batch(self.p, {'items': [dict(id=q['id'], revision=q['revision'])]})
        self.assertEqual(ex.detail(self.p, {'id': self.ident})['board'], '刑诉')

    def test_filters_and_none_vault(self):
        self.imported(); self.edit(chapter=self.chapter)
        self.assertEqual(ex.search(self.p, {'board': '刑诉', 'chapter': self.chapter})['total'], 1)
        self.assertEqual(ex.search(self.p, {'q': '错误', 'year': 2025})['total'], 1)
        self.assertFalse(ex.official_questions(Paths(None), '刑诉'))
