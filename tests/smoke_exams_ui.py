"""发布前浏览器检查：虚构题库，覆盖导入、参考不判分、核验和四种布局。

手动执行需开发依赖 playwright；程序及前端不依赖它。截图输出到指定目录。
"""
import json
import copy
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rpg import paths, exam_catalog
from playwright.sync_api import sync_playwright
import server


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else 'ui-screenshots').resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        paths.SETTINGS_DIR = root / 'settings'
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / 'settings.json'
        vault = root / 'vault'; vault.mkdir()
        os.environ['FAKAO_VAULT'] = str(vault)
        chapter = '10-科目/04-刑事诉讼法/02-证据'
        (vault / chapter).mkdir(parents=True)
        source = vault / '60-真题库/2025-试卷一.md'
        source.parent.mkdir()
        source.write_text('### 单项选择题\n#### 1. 界面测试题：哪个选项是甲？\n'
                          '- [ ] **A.** 甲\n- [ ] **B.** 乙\n- [ ] **C.** 丙\n- [ ] **D.** 丁\n', encoding='utf-8')
        original = source.read_bytes()
        server.prepare()
        srv, url = server.start_server(8876, False)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))
                page = browser.new_page(viewport={'width': 1280, 'height': 860})
                def show_panel(selector):
                    page.locator(selector).wait_for(state='attached')
                    page.wait_for_timeout(100)
                    ids = page.locator(selector).first.evaluate("(el) => {const ids=[];for(let p=el;p;p=p.parentElement)if(p.hidden&&getComputedStyle(p).display==='none'&&p.getAttribute('role')==='tabpanel')ids.unshift(p.id);return ids;}")
                    for panel_id in ids:
                        page.locator('[role=tab][aria-controls="%s"]' % panel_id).click()

                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url)
                page.evaluate("go('train')")
                page.evaluate("go('bank')")
                assert page.locator('[data-open-exams]').count() == 0
                page.evaluate("go('skeleton')")
                page.locator('[data-libtab="yujian"]').click()
                page.locator('[data-open-exams]').click()
                page.locator('[data-catalog-tab="import"]').click()
                page.locator('.ex-content[aria-busy]').wait_for(state='detached')
                page.locator('[data-scan]').click()
                page.get_by_text('预览：1 张原卷、1 题', exact=False).wait_for()
                assert not (vault / '训练/题库/历年目录.json').exists()
                page.locator('[data-import]').click()
                page.locator('[data-question]').wait_for()
                page.locator('[data-catalog-tab="classification"]').click()
                page.locator('.ex-content[aria-busy]').wait_for(state='detached')
                q = exam_catalog.detail(paths.Paths(vault), {'id': '2025-试卷一-001'})
                package = {'format': 'fakao-rpg-classification', 'version': 1, 'items': [
                    dict(id=q['id'], fingerprint=q['fingerprint'], chapter=chapter, confidence='review', reason='测试复核')]}
                page.locator('#exOfflineFile').set_input_files({'name': 'classification.json', 'mimeType': 'application/json',
                    'buffer': json.dumps(package, ensure_ascii=False).encode('utf-8')})
                page.get_by_text('预览：可采用 0 题；另 1 题', exact=False).wait_for()
                assert exam_catalog.load(paths.Paths(vault))['questions'][q['id']]['classification'] == 'pending'
                page.locator('[data-offline-adopt]').click()
                page.get_by_text('已导入：可采用', exact=False).wait_for()
                page.locator('#exClass').select_option('review')
                page.locator('[data-question]').wait_for()
                page.locator('#exClass').select_option('')
                page.locator('[data-question]').wait_for()
                page.locator('[data-confirm-filtered]').click()
                page.get_by_text('已一次采用 1 题', exact=False).wait_for()
                assert exam_catalog.load(paths.Paths(vault))['questions'][q['id']]['classification'] == 'confirmed'
                page.locator('[data-catalog-tab="references"]').click()
                page.locator('.ex-content[aria-busy]').wait_for(state='detached')

                rows = [{'input': '界面测试题：哪个选项是甲？\nA. 乙\nB. 甲\nC. 丁\nD. 丙', 'output': '虚构测试解析：原数据B对应本题A。'}]
                page.locator('#exReferenceFile').set_input_files({'name': 'sample.json', 'mimeType': 'application/json', 'buffer': json.dumps(rows, ensure_ascii=False).encode('utf-8')})
                page.get_by_text('标准答案未改变。', exact=False).wait_for()
                page.get_by_text('已自动导入 1 道题的参考解析', exact=False).wait_for()
                assert page.locator('[data-question]').count() == 1
                assert page.locator('[data-classify]').is_hidden()
                for width, height in [(1280, 860), (800, 1280)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for theme in ['light', 'dark']:
                        page.evaluate('(t) => document.documentElement.dataset.theme = t', theme)
                        page.screenshot(path=str(output / ('%s-%s-reference-results.png' % (width, theme))), animations='disabled')
                page.locator('[data-question]').click()
                assert page.locator('dialog[open]').count() == 0
                assert page.locator('#view > .ex-page').count() == 1
                page.get_by_text('虚构测试解析：原数据B对应本题A。', exact=True).wait_for()
                assert page.locator('.ex-answer-view details').first.get_attribute('open') is not None
                # 无需作答即可主动读解析，未自动核验答案。
                assert not exam_catalog.detail(paths.Paths(vault), {'id': q['id'], 'reveal': True})['answer']
                page.locator('[name="exChoice"][value="A"]').check()
                page.locator('[data-practice]').click()
                page.get_by_text('答案未核验，不判对错。', exact=False).wait_for()
                q = exam_catalog.detail(paths.Paths(vault), {'id': '2025-试卷一-001', 'reveal': True})
                assert q['answer'] == '' and q['history'][0]['ok'] is None
                assert not exam_catalog.official_questions(paths.Paths(vault), '刑诉')
                page.get_by_text('科目与章节核对', exact=True).click()
                page.locator('#exEditChapter').select_option(chapter)
                page.locator('#exEditTopic').fill('证明责任')
                page.locator('[data-save-class]').click()
                page.get_by_text('章节已确认。', exact=True).wait_for()
                page.get_by_text('核验并补充答案', exact=True).click()
                page.locator('#exAnswer').fill('A')
                page.locator('#exKind').select_option('single')
                page.locator('#exAnswerSource').fill('虚构UI测试答案表')
                page.locator('[data-save-answer]').click()
                page.get_by_text('答案已核验保存', exact=False).wait_for()
                assert exam_catalog.official_questions(paths.Paths(vault), '刑诉')[0]['answer'] == 'A'
                assert source.read_bytes() == original
                page.locator('[data-back]').click()
                page.locator('[data-catalog-tab="questions"]').click()
                page.locator('.ex-content[aria-busy]').wait_for(state='detached')
                page.locator('#exBoard').select_option('刑诉')
                page.locator('#exChapter').select_option(chapter)
                page.locator('[data-question]').wait_for()
                for width, height in [(1280, 860), (800, 1280)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for theme in ['light', 'dark']:
                        page.evaluate('(theme) => { document.documentElement.dataset.theme = theme; document.documentElement.style.colorScheme = theme; }', theme)
                        page.locator('.ex-content[aria-busy]').wait_for(state='detached')
                        page.screenshot(path=str(output / ('%s-%s-list.png' % (width, theme))), animations='disabled')
                        assert page.locator('.ex-page').evaluate('(e) => e.scrollWidth <= e.clientWidth + 1'), '目录横向溢出'
                        page.locator('[data-question]').click()
                        page.locator('[data-reveal]').click()
                        page.get_by_text('虚构测试解析：原数据B对应本题A。', exact=True).wait_for()
                        page.locator('.ex-content[aria-busy]').wait_for(state='detached')
                        page.screenshot(path=str(output / ('%s-%s-detail.png' % (width, theme))), animations='disabled', full_page=True)
                        assert page.locator('.ex-page').evaluate('(e) => e.scrollWidth <= e.clientWidth + 1'), '题目横向溢出'
                        page.locator('[data-back]').click()
                        page.locator('[data-question]').wait_for()
                # 统计入口清除之前的科目/年份等筛选，显示保存的解析。
                page.locator('#exYear').select_option('2025')
                page.locator('[data-stat-tab="references"]').click()
                page.locator('.ex-content[aria-busy]').wait_for(state='detached')
                assert page.locator('#exBoard').input_value() == ''
                assert page.locator('#exYear').input_value() == ''
                page.locator('[data-ref-question]').click()
                page.get_by_text('虚构测试解析：原数据B对应本题A。', exact=True).wait_for()
                page.locator('[data-close]').click()
                page.locator('.ex-page').wait_for(state='detached')
                page.locator('[data-ex-references]').click()
                page.locator('[data-question]').wait_for()
                page.locator('[data-question]').click()
                page.get_by_text('虚构测试解析：原数据B对应本题A。', exact=True).wait_for()
                page.locator('[data-close]').click()
                page.locator('[data-libtab="yujian"].on').wait_for()
                page.locator('[data-open-exams]').wait_for()
                page.locator('.ex-page').wait_for(state='detached')
                page.get_by_text('共 1 道历年题目', exact=False).wait_for()
                # 虚构多科跨卷题库：校验未核验题直接可见、卷轴、跨科套卷与连续刷题。
                pth = paths.Paths(vault)
                catalog = exam_catalog.load(pth)
                original_q = catalog['questions']['2025-试卷一-001']
                subjects = list(exam_catalog.SUBJECTS.values())
                subjects = list(dict.fromkeys(subjects))
                for i in range(2, 26):
                    item = copy.deepcopy(original_q)
                    board = subjects[(i - 2) % len(subjects)]
                    item.update(id='2025-试卷一-%03d' % i, number=i, board=board, subject=board,
                                stem='虚构展示题：%s的第%s题，应当如何适用法律？' % (board, i),
                                history=[], references=[], answer='', answer_status='pending')
                    catalog['questions'][item['id']] = item
                for i, board in enumerate(subjects, 1):
                    item = copy.deepcopy(original_q)
                    item.update(id='2024-试卷二-%03d' % i, year=2024, paper='试卷二', number=i, board=board,
                                stem='虚构旧卷题：%s的案例问题。' % board, history=[], references=[],
                                answer='', answer_status='pending')
                    catalog['questions'][item['id']] = item
                exam_catalog.save(pth, catalog)
                page.evaluate('render()')
                page.locator('.ex-scroll').first.wait_for()
                assert page.locator('.ex-scroll').count() == 8
                page.get_by_text('共 33 道历年题目', exact=False).wait_for()
                for width, height in [(1280, 860), (800, 1280)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for theme in ['light', 'dark']:
                        page.evaluate('(t) => document.documentElement.dataset.theme = t', theme)
                        page.screenshot(path=str(output / ('%s-%s-scroll-shelf.png' % (width, theme))), animations='disabled')
                        assert page.locator('.ex-shelf').evaluate('(e) => e.scrollWidth <= e.clientWidth + 1')
                board_roll = page.locator('.ex-scroll').filter(has=page.locator('[data-ex-board="刑诉"][data-ex-practice]'))
                board_roll.locator('summary').click()
                for width, height in [(1280, 860), (800, 1280)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for theme in ['light', 'dark']:
                        page.evaluate('(t) => document.documentElement.dataset.theme = t', theme)
                        page.screenshot(path=str(output / ('%s-%s-scroll-open.png' % (width, theme))), animations='disabled')
                        assert board_roll.evaluate('(e) => e.scrollWidth <= e.clientWidth + 1')
                expected = exam_catalog.sequence(pth, {'board': '刑诉'})
                first_id = expected['ids'][expected['start']]
                board_roll.locator('[data-ex-practice]').click()
                page.locator('.ex-study-head').get_by_text(first_id, exact=True).wait_for()
                page.locator('[name="exChoice"][value="B"]').check()
                page.locator('[data-q-next]').click()
                page.locator('.ex-study-head').get_by_text(expected['ids'][expected['start'] + 1], exact=True).wait_for()
                page.locator('[data-q-prev]').click()
                page.locator('.ex-study-head').get_by_text(first_id, exact=True).wait_for()
                assert page.locator('[name="exChoice"][value="B"]').is_checked()
                page.locator('[name="exChoice"][value="A"]').check()
                page.locator('[data-practice]').click()
                page.get_by_text('答案未核验，不判对错。', exact=False).wait_for()
                assert exam_catalog.detail(pth, {'id': first_id, 'reveal': True})['history'][-1]['ok'] is None
                page.locator('[data-close]').click()
                page.locator('.ex-page').wait_for(state='detached')
                page.evaluate("go('train')")
                page.evaluate("go('bank')")
                # 3.0.4试炼类型分面板，按真实模块标签进入科目卷轴。
                page.locator('[data-ex-shelf]').wait_for(state='attached')
                page.wait_for_timeout(100)
                ids = page.locator('[data-ex-shelf]').evaluate("(el) => {const ids=[];for(let p=el;p;p=p.parentElement)if(p.hidden&&getComputedStyle(p).display==='none'&&p.getAttribute('role')==='tabpanel')ids.unshift(p.id);return ids;}")
                for panel_id in ids:
                    page.locator('[role=tab][aria-controls="%s"]' % panel_id).click()
                page.locator('[data-ex-shelf]').wait_for()
                assert page.locator('[data-open-exams]').count() == 0
                for width, height in [(1280, 860), (800, 1280)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for theme in ['light', 'dark']:
                        page.evaluate('(t) => document.documentElement.dataset.theme = t', theme)
                        page.screenshot(path=str(output / ('%s-%s-adventure-scrolls.png' % (width, theme))), animations='disabled')
                paper = page.locator('.ex-paper-roll').first
                paper.locator('summary').click()
                paper.locator('[data-ex-practice]').click()
                page.locator('.ex-study-head').get_by_text('2025-试卷一-002', exact=True).wait_for()
                page.locator('.ex-study-side').get_by_role('heading', name='第 2 / 25 题', exact=True).wait_for()
                page.locator('[data-q-next]').click()
                page.locator('.ex-study-head').get_by_text('2025-试卷一-003', exact=True).wait_for()
                page.locator('[data-close]').click()
                page.locator('.ex-page').wait_for(state='detached')
                # 套卷题目目录中的每一题可直达详情。
                paper = page.locator('.ex-paper-roll').first
                paper.locator('summary').click()
                paper.locator('[data-ex-id="2025-试卷一-003"]').click()
                page.locator('.ex-study-head').get_by_text('2025-试卷一-003', exact=True).wait_for()
                page.evaluate("go('home')")
                page.locator('.ex-page').wait_for(state='detached')
                page.locator('.portal-world').wait_for()
                assert page.locator('.hero').count() == 0
                page.set_viewport_size({'width': 1280, 'height': 860})
                page.locator('[data-portal-go="dwelling"]').click()
                page.locator('.hero').wait_for(state='attached')
                page.wait_for_timeout(100)
                hero_panel = page.locator('.hero').evaluate("(el) => el.closest('[role=tabpanel]')?.id")
                if hero_panel:
                    page.locator('[role=tab][aria-controls="%s"]' % hero_panel).click()
                page.locator('.hero').wait_for()
                page.evaluate("go('settings')")
                show_panel('.portal-settings')
                page.locator('.portal-settings').wait_for()
                page.locator('.portal-settings').evaluate("el => { if (el.tagName === 'DETAILS') el.open = true; }")
                page.locator('[data-portal-device]').select_option('desktop')
                page.locator('[data-portal-selected]').select_option('dwelling')
                page.locator('[data-portal-x]').fill('37')
                page.locator('[data-portal-x]').press('Tab')
                page.locator('[data-portal-save]').click()
                page.evaluate("go('home')")
                page.locator('.portal-world').wait_for()
                assert page.locator('[data-portal-go="dwelling"]').evaluate("el => el.style.getPropertyValue('--px')") == '37%'
                page.reload()
                page.locator('.portal-world').wait_for()
                assert page.locator('[data-portal-go="dwelling"]').evaluate("el => el.style.getPropertyValue('--px')") == '37%'
                for width, height in [(1280, 860), (800, 1280)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for theme in ['light', 'dark']:
                        page.evaluate("t => document.documentElement.dataset.theme = t", theme)
                        page.screenshot(path=str(output / ('portal-%s-%s.png' % (width, theme))))
                assert page.evaluate('EXAMS.isOpen()') is False
                assert not errors, '\n'.join(errors)

                browser.close()
        finally:
            srv.shutdown(); srv.server_close()
    print('EXAMS-UI-OK: 导入、参考不判分、核验、章节筛选、电脑/平板亮暗色布局')


if __name__ == '__main__':
    main()
