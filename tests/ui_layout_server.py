"""给 tests/ui_layout_check.cjs 起服务：临时法考库 + 临时本机设置，不碰用户数据、不连真 AI。打印 “UI-READY 网址” 后一直运行。"""
import os
import sys
import tempfile
os.environ.pop('DEEPSEEK_API_KEY', None)
os.environ.pop('SHENLUN_AI_BASE_URL', None)
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# 在导入前隔离自动找库和旧版设置。
from unittest.mock import patch
_import_home = tempfile.TemporaryDirectory()
_home_patch = patch.object(Path, 'home', return_value=Path(_import_home.name))
_home_patch.start()
from rpg import api, paths  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as t:
        r = Path(t)
        paths.SETTINGS_DIR = r / "home"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        v = r / "法考"
        (v / "10-科目" / "民法").mkdir(parents=True)
        (v / "10-科目" / "民法" / "代理.md").write_text("# 代理\n表见代理：相对人有理由相信行为人有代理权。\n", encoding="utf-8")
        os.environ["FAKAO_VAULT"] = str(v)
        paths.save_settings({"vault": str(v)})
        paths.Paths(v).ensure_train_dir()
        if '--journey-fixture' in sys.argv:
            # 第二批交互用自编卡片，不连接AI、不读取真实题库。
            from rpg import cards
            with api.open_game() as g:
                deck = next(iter(g.boards))
                cards.add(g, dict(deck=deck, type='问答', front='自编练习：解释一个方法的适用条件。', back='先说明条件，再用自己的话举例。'))
                cards.add(g, dict(deck=deck, type='问答', front='自编练习二：用自己的话举例。', back='说明条件与边界。'))
        if '--merge-fixture' in sys.argv:
            # 自编演示成绩，覆盖合并后的走势、双录入方式与手动领奖。
            from rpg import mock_rewards, mock
            with api.open_game() as g:
                for num, score in ((37, 62), (38, 72)):
                    if g.paths.seasons:
                        folder = g.paths.seasons / ('第%d季' % num)
                        folder.mkdir(parents=True, exist_ok=True)
                        board = next(iter(mock.MODULE_OF))
                        (folder / ('01-' + board + '.md')).write_text('### 1. ✅\n\n自编题目：选择A。\n\n### 2. ❌\n\n自编题目：解释条件。\n', encoding='utf-8')
                    g.state.setdefault('mocks', {})[str(num)] = dict(score=score, date=g.t, avg=55, top=88, beat=80, rank=20, people=100, minutes={}, scores={})
                    g.state['boss'].append(dict(d=g.t, name='第%d季' % num, score=score, kind='大比'))
                mock_rewards.offer(g, '自编模考奖励', 72, g.raw_score())
        srv = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        api.RUNTIME.update(port=srv.server_port, lan=False)
        print("UI-READY http://127.0.0.1:%d" % srv.server_port, flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()
