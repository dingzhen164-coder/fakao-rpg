"""静态文件缓存：背景图/脚本带 ETag，浏览器再问时没变就回 304，不再每次重下几MB的4K背景。仅自编夹具，不碰用户数据。"""
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from rpg import api


class StaticCacheTests(unittest.TestCase):
    def get(self, name, etag=None):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request("http://127.0.0.1:%d/%s" % (srv.server_address[1], name))
            if etag:
                req.add_header("If-None-Match", etag)
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, r.headers, r.read()
            except urllib.error.HTTPError as e:
                with e:
                    return e.code, e.headers, e.read()
        finally:
            srv.shutdown()
            srv.server_close()

    def test_image_is_revalidated_with_304_instead_of_downloaded_again(self):
        name = "assets/beauty/trial/tower.png"
        status, head, body = self.get(name)
        self.assertEqual(status, 200)
        self.assertGreater(len(body), 10000)
        self.assertEqual(head["Cache-Control"], "no-cache")
        tag = head["ETag"]
        status, head2, body2 = self.get(name, tag)
        self.assertEqual((status, body2), (304, b""))
        self.assertEqual(head2["ETag"], tag)
        self.assertEqual(self.get(name, '"other-version"')[0], 200)

    def test_versioned_art_url_is_kept_by_the_browser_but_scripts_are_asked_each_time(self):
        name = "assets/beauty/trial/tower.png"
        self.assertEqual(self.get(name + "?v=123")[1]["Cache-Control"], "public, max-age=31536000, immutable")
        self.assertEqual(self.get(name)[1]["Cache-Control"], "no-cache")
        status, head, _ = self.get("app.js?v=123")
        self.assertEqual(head["Cache-Control"], "no-cache", "脚本即使带版本号也每次问一下，更新后不会读到旧代码")
        self.assertEqual(self.get("app.js", head["ETag"])[0], 304)

    def test_index_page_is_revalidated_and_api_is_never_cached(self):
        status, head, _ = self.get("index.html")
        self.assertEqual(self.get("index.html", head["ETag"])[0], 304)
        self.assertEqual(self.get("api/dashboard")[1]["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
