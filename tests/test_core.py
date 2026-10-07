"""隔离假库，验证原文保护、OCR、复习、答案隐藏、机考保存和接口边界。"""
import copy,json,tempfile,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from rpg.service import Service
from rpg.materials import safe_source
from server import make_server
from rpg.version import VERSION
SAMPLE='''---
subject: "民法"
knowledge_point: 2
title: "考点样例"
---
# 知识点 002
原则
这是一段用于验证排版的文字。
（示意图）
「随堂练习1 一个测试问题？（2020测试，单）
②答案：C。
5
<!-- OCR_PAGE: 15 -->
A.选项甲
C.选项丙
图示关系
B.选项乙
D.选项丁
'''
class Core(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.s=Service(self.root/'settings',self.root/'vault')
 def call(self,a,b=None,local=True):return self.s.handle(a,b or {},local)
 def material(self):return self.call('material_import',{'text':SAMPLE,'name':'002.md'})
 def verified(self):
  m=self.material();return self.call('material_save',{'id':m['id'],'cleaned':m['cleaned'],'verified':True})
 def question(self,kind='single',answer=None):return self.call('question_add',{'stem':'测试题','subject':'民法','options':{'A':'甲','B':'乙','C':'丙','D':'丁'},'answer':answer or ['C'],'type':kind,'verified':True,'explanation':'测试解析'})
 def exam(self):return self.call('exam_create',{'material':'案例材料','questions':[{'prompt':'问题','reference':'参考答案保密','points':[{'id':'p1','text':'测试要点','score':2}]}],'minutes':1})
 def test_ocr_cross_page(self):
  m=self.material();self.assertEqual(m['subject'],'民法');self.assertEqual(m['question_draft']['answer'],['C']);self.assertEqual(list(m['question_draft']['options']),list('ABCD'));self.assertNotIn('图示关系',m['question_draft']['options']['C']);self.assertTrue(m['warnings']);self.assertEqual(m['pages'],['15'])
 def test_stable_import_id(self):
  a=self.material();self.material();self.assertEqual(len(self.s.state['materials']),1);changed=self.call('material_import',{'text':SAMPLE+'\n新段落','name':'002.md'});self.assertEqual(changed['id'],a['id']);self.assertEqual(changed['status'],'draft');self.assertEqual(len(changed['history']),1)
 def test_original_readonly(self):
  f=self.s.store.root/'99-知识点库';f.mkdir(parents=True);p=f/'002.md';p.write_text(SAMPLE);d=self.call('source_get',{'path':'99-知识点库/002.md'});self.call('material_import',{'text':d['text'],'name':d['name'],'source':d['path']});self.assertEqual(p.read_text(),SAMPLE)
 def test_path_escape_and_symlink(self):
  for p in ['../private.md','训练/secret.md','/etc/passwd']:
   with self.assertRaises(ValueError):safe_source(self.s.store.root,p)
  train=self.s.store.train;train.mkdir(parents=True,exist_ok=True);(train/'资料整理').symlink_to(self.root)
  with self.assertRaises(ValueError):self.material()
 def test_draft_learning_blocked(self):
  m=self.material()
  with self.assertRaises(ValueError):self.call('card_add',{'front':'问','back':'答','material_id':m['id']})
  with self.assertRaises(ValueError):self.call('practice',{'id':m['id'],'text':'测试回忆','passed':True})
 def test_fsrs_repeat_protection(self):
  m=self.verified();c=self.call('card_add',{'front':'测试问','back':'测试答','material_id':m['id']});self.call('card_rate',{'id':c['id'],'rating':3});self.assertGreater(c['s'],0);self.assertGreater(c['due'],time.time())
  with self.assertRaises(ValueError):self.call('card_rate',{'id':c['id'],'rating':3})
  self.assertEqual(self.s.state['xp'],3)
 def test_new_card_limit(self):
  self.call('config',{'new_per_day':1})
  for i in range(3):self.call('card_add',{'front':'问'+str(i),'back':'答'})
  self.assertEqual(len(self.call('cards')['queue']),1)
 def test_answers_hidden_and_idempotent(self):
  q=self.question();self.assertNotIn('answer',q);self.assertNotIn('explanation',q);a=self.call('question_answer',{'id':q['id'],'answer':['C'],'request_id':'one'});self.assertTrue(a['correct']);self.call('question_answer',{'id':q['id'],'answer':['C'],'request_id':'one'});self.assertEqual(len(self.s.state['attempts']),1)
 def test_multiple_and_wrong_review(self):
  q=self.question('multiple',['A','C']);self.assertFalse(self.call('question_answer',{'id':q['id'],'answer':['A']})['correct']);self.assertTrue(self.call('questions')[0]['wrong']);a=self.call('question_answer',{'id':q['id'],'answer':['C','A']});self.assertTrue(a['correct']);self.assertTrue(a['repeat']);self.assertFalse(self.call('questions')[0]['wrong']);self.assertEqual(self.s.state['xp'],1)
 def test_exam_revision_resume_and_hidden(self):
  e=self.exam();i=e['id'];self.assertNotIn('reference',e['questions'][0]);self.assertNotIn('points',e['questions'][0]);self.call('exam_start',{'id':i});self.call('exam_save',{'id':i,'revision':0,'answers':['测试答案']})
  with self.assertRaises(ValueError):self.call('exam_save',{'id':i,'revision':0,'answers':['旧答案']})
  r=Service(self.root/'settings',self.root/'vault');self.assertEqual(r.state['exams'][i]['answers'],['测试答案']);self.assertEqual(self.call('exam_submit',{'id':i})['questions'][0]['reference'],'参考答案保密');self.call('exam_submit',{'id':i});self.assertEqual(self.s.state['xp'],10)
  with self.assertRaises(ValueError):self.call('exam_save',{'id':i,'revision':1,'answers':['改答']})
 def test_exam_expiry(self):
  e=self.exam();self.call('exam_start',{'id':e['id']});self.s.state['exams'][e['id']]['started']=time.time()-100
  with self.assertRaises(ValueError):self.call('exam_save',{'id':e['id'],'revision':0,'answers':['超时答案']})
  self.assertTrue(self.call('exam_submit',{'id':e['id']})['submitted'])
 def test_grading_evidence(self):
  e=self.exam();self.call('exam_start',{'id':e['id']});self.call('exam_save',{'id':e['id'],'revision':0,'answers':['测试要点覆盖']});self.call('exam_submit',{'id':e['id']});good={'result':{'points':[{'id':'0:p1','hit':True,'evidence':'测试要点','feedback':'已覆盖'}]},'cached':False,'usage':{'total_tokens':10}}
  with patch('rpg.ai.request',return_value=good):self.assertEqual(self.call('ai',{'task':'grade','id':e['id']})['score'],2)
  bad=copy.deepcopy(good);bad['result']['points'][0]['evidence']='不存在的内容'
  with patch('rpg.ai.request',return_value=bad),self.assertRaises(ValueError):self.call('ai',{'task':'grade','id':e['id']})
 def test_invalid_ai_hits(self):
  e=self.exam();self.call('exam_start',{'id':e['id']});self.call('exam_submit',{'id':e['id']});bad={'result':{'points':[{'id':'0:p1','hit':'true','evidence':'无'}]}}
  with patch('rpg.ai.request',return_value=bad),self.assertRaises(ValueError):self.call('ai',{'task':'grade','id':e['id']})
  self.assertIsNone(self.s.state['exams'][e['id']]['assessment'])
 def test_notes_revision_and_coordinates(self):
  n=self.call('note_save',{'title':'测试笔记','strokes':[[[.1,.2],[.2,.3]]],'text':'记录'})
  with self.assertRaises(ValueError):self.call('note_save',dict(n,revision=0))
  with self.assertRaises(ValueError):self.call('note_save',{'strokes':[[[float('nan'),.2]]]})
 def test_backup_version_defaults(self):
  self.material();self.call('card_add',{'front':'问题','back':'答案'});self.assertEqual(len(list((self.s.store.file.parent/'备份').glob('*.json'))),1);self.assertIn('## '+VERSION,Path('changelog.md').read_text());self.assertEqual(self.call('dashboard')['config']['daily_minutes'],180)
 def test_settings_remote_restricted(self):
  with self.assertRaises(ValueError):self.call('settings_save',{'api_key':'secret'},False)
  self.call('settings_save',{'api_key':'secret'});r=self.call('settings',local=False);self.assertNotIn('api_key',r);self.assertEqual(r['lan_code'],'');self.assertEqual(r['vault'],'')

 def test_config_failure_rolls_back(self):
  before=copy.deepcopy(self.s.state['config'])
  with self.assertRaises(ValueError):self.call('config',{'start_date':'2026-12-02','daily_minutes':-1})
  self.assertEqual(self.s.state['config'],before)
 def test_rules_external_change(self):
  rules=json.loads(self.s.store.rules_file.read_text());rules['daily_minutes']=210;self.s.store.rules_file.write_text(json.dumps(rules));r=Service(self.root/'settings',self.root/'vault');self.assertEqual(r.state['config']['daily_minutes'],210)

class HttpTests(unittest.TestCase):
 setUp=Core.setUp
 def test_origin_and_host(self):
  srv=make_server(self.s,'127.0.0.1',0);threading.Thread(target=srv.serve_forever,daemon=True).start();self.addCleanup(srv.server_close);self.addCleanup(srv.shutdown);base='http://127.0.0.1:'+str(srv.server_port)
  with urllib.request.urlopen(base+'/health') as r:self.assertEqual(json.load(r)['version'],VERSION)
  req=urllib.request.Request(base+'/api/dashboard',data=b'{}',headers={'Content-Type':'application/json','Origin':'http://evil.test'})
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
  self.assertEqual(e.exception.code,403)
  with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(urllib.request.Request(base+'/',headers={'Host':'evil.test'}))
 def test_lan_login_and_local_settings(self):
  srv=make_server(self.s,'127.0.0.1',0);srv.RequestHandlerClass.local=lambda _:False
  threading.Thread(target=srv.serve_forever,daemon=True).start();self.addCleanup(srv.server_close);self.addCleanup(srv.shutdown);base='http://127.0.0.1:'+str(srv.server_port)
  def post(action,body,cookie=''):
   return urllib.request.urlopen(urllib.request.Request(base+'/api/'+action,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Cookie':cookie}))
  with self.assertRaises(urllib.error.HTTPError) as e:post('dashboard',{})
  self.assertEqual(e.exception.code,401)
  with post('login',{'code':self.s.settings['lan_code']}) as r:cookie=r.headers['Set-Cookie'].split(';')[0]
  with post('settings',{},cookie) as r:self.assertEqual(json.load(r)['lan_code'],'')
  with self.assertRaises(urllib.error.HTTPError):post('settings_save',{'api_key':'bad'},cookie)
if __name__=='__main__':unittest.main()
