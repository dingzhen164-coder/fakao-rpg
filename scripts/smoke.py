"""安装包启动冒烟：隔离设置和库，检查真实HTTP服务后退出。"""
import json,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 cmd=[sys.argv[1]]+sys.argv[2:]+['--settings-dir',str(Path(tmp)/'settings'),'--vault',str(Path(tmp)/'vault'),'--port',str(port),'--no-browser']
 p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 try:
  for i in range(60):
   try:
    with urllib.request.urlopen('http://127.0.0.1:%s/health'%port,timeout=1) as r:result=json.load(r)
    assert result['app']=='fakao-rpg'
    print('SMOKE-OK',result['version']);break
   except (OSError,ValueError):
    if p.poll() is not None:raise RuntimeError(p.stdout.read().decode(errors='replace'))
    time.sleep(.5)
  else:raise RuntimeError('安装包未启动')
 finally:
  p.terminate();p.wait(timeout=15)
