"""给 tests/ui_layout_check.cjs 起服务：临时法考库 + 临时本机设置，不碰用户数据、不连真 AI。打印 “UI-READY 网址” 后一直运行。"""
import os
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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
        srv = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        api.RUNTIME.update(port=srv.server_port, lan=False)
        print("UI-READY http://127.0.0.1:%d" % srv.server_port, flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()
