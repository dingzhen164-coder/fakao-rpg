"""标准库HTTP入口。仅本机默认监听；启用局域网需口令；无远程命令执行、无第三方运行依赖。"""
import argparse
import hashlib
import hmac
import ipaddress
import json
import mimetypes
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from rpg.service import Service
from rpg.version import VERSION

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))


def make_server(service, host='127.0.0.1', port=8766):
    session_key = secrets.token_bytes(32)
    token = hmac.new(session_key, service.settings['lan_code'].encode(), hashlib.sha256).hexdigest()
    failures = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # 不记录密钥、资料正文和URL参数
        def local(self):
            return self.client_address[0] in ('127.0.0.1', '::1')
        def authorized(self):
            return self.local() or any(hmac.compare_digest(p.strip(), 'fg_session=' + token) for p in self.headers.get('Cookie','').split(';'))
        def host_ok(self):
            host = self.headers.get('Host','').split(':')[0]
            if host == 'localhost':
                return True
            try:
                addr = ipaddress.ip_address(host)
                return addr.is_loopback or (service.settings.get('lan') and addr.is_private)
            except ValueError:
                return False
        def respond(self, code, body, typ='application/json; charset=utf-8', cookie=None):
            raw = json.dumps(body, ensure_ascii=False).encode() if isinstance(body,(dict,list)) else body
            if isinstance(raw,str):
                raw=raw.encode()
            self.send_response(code)
            self.send_header('Content-Type',typ)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            if cookie:
                self.send_header('Set-Cookie',cookie)
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            if not self.host_ok():
                return self.respond(403,{'error':'不允许此Host'})
            path=urllib.parse.urlsplit(self.path).path
            if path.startswith('/api/'):
                if not self.authorized():
                    return self.respond(401,{'error':'请先输入局域网口令'})
                if path=='/api/dashboard':
                    return self.respond(200,service.handle('dashboard',{},self.local()))
                return self.respond(404,{'error':'接口不存在'})
            if path=='/health':
                return self.respond(200,{'app':'fakao-rpg','version':VERSION})
            rel=urllib.parse.unquote(path).lstrip('/') or 'index.html'
            p=(ROOT/'web'/rel).resolve()
            try:
                p.relative_to((ROOT/'web').resolve())
            except ValueError:
                return self.respond(403,{'error':'路径不合法'})
            if not p.is_file():
                return self.respond(404,{'error':'文件不存在'})
            typ=mimetypes.guess_type(str(p))[0] or 'application/octet-stream'
            if typ.startswith('text/') or typ=='application/javascript':
                typ+='; charset=utf-8'
            return self.respond(200,p.read_bytes(),typ)
        def do_POST(self):
            if not self.host_ok():
                return self.respond(403,{'error':'不允许此Host'})
            origin=self.headers.get('Origin')
            if origin and urllib.parse.urlsplit(origin).netloc!=self.headers.get('Host'):
                return self.respond(403,{'error':'拒绝跨站请求'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.respond(415,{'error':'必须使用JSON'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=5000000:
                    raise ValueError('请求体过大或为空')
                body=json.loads(self.rfile.read(n))
                if not isinstance(body,dict):
                    raise ValueError('请求体须为对象')
                action=urllib.parse.urlsplit(self.path).path.removeprefix('/api/') if sys.version_info>=(3,9) else urllib.parse.urlsplit(self.path).path[5:]
                if action=='login':
                    import time
                    ip=self.client_address[0]
                    recent=[t for t in failures.get(ip,[]) if time.monotonic()-t<60]
                    failures[ip]=recent
                    if len(recent)>=10:
                        return self.respond(429,{'error':'尝试过多，请一分钟后重试'})
                    if not hmac.compare_digest(str(body.get('code','')),service.settings['lan_code']):
                        failures[ip].append(time.monotonic())
                        return self.respond(403,{'error':'口令不正确'})
                    return self.respond(200,{'ok':True},cookie='fg_session='+token+'; HttpOnly; SameSite=Strict; Path=/')
                if not self.authorized():
                    return self.respond(401,{'error':'请先输入局域网口令'})
                if action=='shutdown':
                    if not self.local():
                        return self.respond(403,{'error':'只能在电脑本机退出程序'})
                    self.respond(200,{'ok':True})
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                    return
                result=service.handle(action,body,self.local())
                return self.respond(200,result)
            except (ValueError,KeyError,TypeError) as e:
                return self.respond(400,{'error':str(e) if isinstance(e,ValueError) else '资料不存在或请求格式错误'})
            except Exception:
                return self.respond(500,{'error':'操作未完成，请检查存档目录是否可写；原资料不会被覆盖'})
    http=ThreadingHTTPServer((host,port),Handler)
    http.daemon_threads=True
    return http


def main():
    parser=argparse.ArgumentParser(description='法官成长记')
    parser.add_argument('--vault',help='Obsidian库根目录')
    parser.add_argument('--settings-dir',help='隔离本机设置，仅测试或便携用途')
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    service=Service(args.settings_dir,args.vault)
    host='0.0.0.0' if service.settings.get('lan') else '127.0.0.1'
    http=make_server(service,host,args.port)
    url='http://127.0.0.1:%s' % http.server_port
    if sys.stdout is not None:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        print('法官成长记 %s · %s\n可在设置中退出程序。' % (VERSION,url),flush=True)
    if not args.no_browser:
        threading.Timer(.7,lambda:webbrowser.open(url)).start()
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http.server_close()

if __name__=='__main__':
    main()
