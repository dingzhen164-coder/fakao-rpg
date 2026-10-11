"""发布前浏览器检查：虚构题库，覆盖导入、参考不判分、核验和四种布局。

手动执行需开发依赖 playwright；程序及前端不依赖它。截图输出到指定目录。
"""
import json
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
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width': 1280, 'height': 860})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url)
                page.locator('#nav [data-view="train"]').click()
                page.locator('[data-hall="shizhan"]').click()
                page.locator('[data-open-exams]').click()
                page.locator('[data-scan]').click()
                page.get_by_text('预览：1 张原卷、1 题', exact=False).wait_for()
                assert not (vault / '训练/题库/历年目录.json').exists()
                page.locator('[data-import]').click()
                page.locator('[data-question]').wait_for()
                page.get_by_text('导入与参考解析', exact=False).click()
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
                page.get_by_text('导入与参考解析', exact=False).click()

                rows = [{'input': '界面测试题：哪个选项是甲？\nA. 乙\nB. 甲\nC. 丁\nD. 丙', 'output': '虚构测试解析：原数据B对应本题A。'}]
                page.locator('#exReferenceFile').set_input_files({'name': 'sample.json', 'mimeType': 'application/json', 'buffer': json.dumps(rows, ensure_ascii=False).encode('utf-8')})
                page.get_by_text('标准答案未改变。', exact=False).wait_for()
                page.locator('[data-question]').click()
                page.locator('[name="exChoice"][value="A"]').check()
                page.locator('[data-practice]').click()
                page.get_by_text('答案未核验，不判对错。', exact=False).wait_for()
                q = exam_catalog.detail(paths.Paths(vault), {'id': '2025-试卷一-001', 'reveal': True})
                assert q['answer'] == '' and q['history'][0]['ok'] is None
                assert not exam_catalog.official_questions(paths.Paths(vault), '刑诉')
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
                page.locator('#exBoard').select_option('刑诉')
                page.locator('#exChapter').select_option(chapter)
                page.locator('[data-question]').wait_for()
                for width, height in [(1280, 860), (800, 1280)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for theme in ['light', 'dark']:
                        page.evaluate('(theme) => { document.documentElement.dataset.theme = theme; document.documentElement.style.colorScheme = theme; }', theme)
                        page.locator('.ex-content[aria-busy]').wait_for(state='detached')
                        page.screenshot(path=str(output / ('%s-%s-list.png' % (width, theme))), animations='disabled')
                        assert page.locator('.ex-dialog').evaluate('(e) => e.scrollWidth <= e.clientWidth + 1'), '目录横向溢出'
                        page.locator('[data-question]').click()
                        page.locator('[data-reveal]').click()
                        page.get_by_text('Lawyer LLaMA · GPT生成 · 未核验', exact=False).click()
                        page.locator('.ex-content[aria-busy]').wait_for(state='detached')
                        page.screenshot(path=str(output / ('%s-%s-detail.png' % (width, theme))), animations='disabled')
                        assert page.locator('.ex-dialog').evaluate('(e) => e.scrollWidth <= e.clientWidth + 1'), '题目横向溢出'
                        page.locator('[data-back]').click()
                        page.locator('[data-question]').wait_for()
                page.locator('[data-close]').click()
                page.locator('.ex-dialog').wait_for(state='detached')
                assert not errors, '\n'.join(errors)
                browser.close()
        finally:
            srv.shutdown(); srv.server_close()
    print('EXAMS-UI-OK: 导入、参考不判分、核验、章节筛选、电脑/平板亮暗色布局')


if __name__ == '__main__':
    main()
