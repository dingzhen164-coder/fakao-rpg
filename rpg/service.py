"""学习业务：资料、体系、卡片、客观题、主观题、手写、成长。HTTP调用handle；稳定ID、快照及程序计分。"""
import copy
import datetime as dt
import json
import math
import secrets
import time
from pathlib import Path
from .storage import Storage, SUBJECTS, atomic_json
from . import materials, fsrs, ai
from .version import VERSION


def ident():
    return secrets.token_hex(8)


def today():
    return dt.date.today().isoformat()


class Service:
    def __init__(self, settings_dir=None, vault=None):
        self.settings_dir = Path(settings_dir or Path.home() / '.fakao-rpg').expanduser()
        self.settings_file = self.settings_dir / 'settings.json'
        self.settings = json.loads(self.settings_file.read_text(encoding='utf-8')) if self.settings_file.exists() else {}
        self.settings.setdefault('lan_code', '%06d' % secrets.randbelow(1000000))
        self.settings.setdefault('lan', False)
        root = vault or self.settings.get('vault') or self.settings_dir / '演示库'
        self.store = Storage(root)
        self.explicit_vault = bool(vault)
        self.pulses = {}
        self.device = secrets.token_hex(8)

    @property
    def state(self):
        return self.store.state

    def save(self):
        self.store.save()

    def add_xp(self, key, amount, kind):
        if any(e['key'] == key for e in self.state['events']):
            return
        self.state['xp'] += amount
        self.state['events'].append({'key': key, 'amount': amount, 'kind': kind, 'date': today()})

    def dashboard(self):
        s = self.state
        xp = s['xp']
        ranks = ['五级法官助理', '四级法官助理', '三级法官助理', '二级法官助理', '一级法官助理', '初任法官', '资深法官', '高级法官', '大法官', '首席大法官']
        index = 0
        for i in range(1, len(ranks)):
            enough = xp >= s['config']['rank_base'] * i * i
            if i >= 5:
                enough = enough and len({a['question']['subject'] for a in s['attempts'] if a['correct'] and not a['repeat']}) >= min(i - 3, 4)
            if i >= 8:
                enough = enough and any(e.get('assessment') == 'ai' and e.get('ratio', 0) >= .7 for e in s['exams'].values())
            if enough:
                index = i
            else:
                break
        date = today()
        first = [a for a in s['attempts'] if not a['repeat']]
        return {'version': VERSION, 'subjects': SUBJECTS, 'config': s['config'], 'vault': str(self.store.root), 'demo': not bool(self.settings.get('vault') or self.explicit_vault), 'rank': ranks[index], 'next_rank': ranks[min(index + 1, 9)], 'next_xp': s['config']['rank_base'] * (index + 1) ** 2, 'xp': xp, 'seconds': s['activity'].get(date, 0), 'materials': len(s['materials']), 'cards': len(s['cards']), 'questions': len(s['questions']), 'correct_rate': round(100 * sum(a['correct'] for a in first) / len(first)) if first else None, 'due': len(self.card_queue()), 'ai_tokens': sum(u['usage']['total_tokens'] for u in s.get('ai_usage', [])), 'scheduled': date >= s['config']['start_date'], 'lan': bool(self.settings.get('lan')), 'ai_ready': bool(self.settings.get('api_key'))}

    def card_queue(self):
        now = time.time()
        s = self.state
        config = s['config']
        revs = [r for r in s['reviews'] if r['date'] == today()]
        new_done = sum(r['new'] for r in revs)
        new_left = max(0, config['new_per_day'] - new_done)
        rev_left = max(0, config['reviews_per_day'] - len([r for r in revs if not r['new']]))
        old, new = [], []
        for c in s['cards'].values():
            if c.get('due', 0) <= now:
                (old if c.get('reps') else new).append(c)
        return sorted(old, key=lambda c: c.get('due', 0))[:rev_left] + new[:new_left]

    def public_question(self, q):
        return {k: v for k, v in q.items() if k not in ('answer', 'explanation')}

    def handle(self, action, b, local=True):
        with self.store.lock:
            before = copy.deepcopy(self.store.state)
            try:
                result = self._handle(action, b, local)
            except Exception:
                self.store.state = before
                raise
            if action not in ('dashboard', 'materials', 'sources', 'cards', 'questions', 'exams', 'notes', 'settings', 'material_get', 'source_get'):
                self.save()
            return result

    def _handle(self, action, b, local):
        s = self.state
        if action == 'dashboard':
            return self.dashboard()
        if action == 'settings':
            return {'vault': str(self.store.root) if local else '', 'lan': bool(self.settings.get('lan')), 'lan_code': self.settings['lan_code'] if local else '', 'model': self.settings.get('model', 'deepseek-chat'), 'base_url': self.settings.get('base_url', 'https://api.deepseek.com') if local else '', 'has_key': bool(self.settings.get('api_key')), 'local': local}
        if action == 'settings_save':
            if not local:
                raise ValueError('本机设置只能在电脑上修改')
            for k in ('model', 'base_url', 'api_key'):
                if k in b and (k != 'api_key' or b[k]):
                    self.settings[k] = str(b[k]).strip()
            if b.get('clear_key'):
                self.settings.pop('api_key', None)
            if 'lan' in b:
                self.settings['lan'] = bool(b['lan'])
            if b.get('vault'):
                new_store = Storage(str(b['vault']))
                self.settings['vault'] = str(new_store.root)
                self.store = new_store
            atomic_json(self.settings_file, self.settings)
            try:
                self.settings_file.chmod(0o600)
            except OSError:
                pass
            return {'ok': True, 'restart': True}
        if action == 'config':
            for k in ('start_date', 'target_date', 'subjective_date'):
                if k in b:
                    if b[k]:
                        dt.date.fromisoformat(b[k])
                    elif k != 'subjective_date':
                        raise ValueError('开始和目标日期不能为空')
                    s['config'][k] = b[k]
            for k in ('daily_minutes', 'new_per_day', 'reviews_per_day'):
                if k in b:
                    n = int(b[k])
                    if not 0 <= n <= 1440 or (k == 'daily_minutes' and n < 1):
                        raise ValueError('数量必须在允许范围内')
                    s['config'][k] = n
            atomic_json(self.store.rules_file, s['config'])
            return s['config']
        if action == 'sources':
            if not local:
                raise ValueError('资料目录扫描仅限电脑本机')
            return materials.scan(self.store.root)
        if action == 'source_get':
            if not local:
                raise ValueError('原始文件读取仅限电脑本机')
            p = materials.safe_source(self.store.root, b.get('path', ''))
            if p.suffix.lower() not in ('.md', '.txt'):
                raise ValueError('PDF可在原阅读器打开；首版不自动提取PDF')
            if p.stat().st_size > 3000000:
                raise ValueError('文件过大，请按考点拆分')
            return {'text': p.read_text(encoding='utf-8-sig'), 'name': p.name, 'path': b['path']}
        if action == 'material_import':
            source = str(b.get('source') or b.get('name') or '粘贴资料')[:500]
            data = materials.normalize(b.get('text', ''), str(b.get('name') or '新考点.md'))
            mid = materials.digest(source)[:16]
            old = s['materials'].get(mid)
            if old and old['fingerprint'] == data['fingerprint']:
                return old
            data.update({'id': mid, 'source': source, 'status': 'draft', 'chapter': str(data['meta'].get('section') or ''), 'updated': today(), 'teacher': '', 'edition': '', 'practice': [], 'history': (old or {}).get('history', []) + ([{'fingerprint': old['fingerprint'], 'cleaned': old['cleaned'], 'date': today()}] if old else [])})
            s['materials'][mid] = data
            self.store.markdown('资料整理', mid, data['cleaned'])
            self.store.markdown('资料整理/原文快照', mid, data['original'])
            return data
        if action == 'materials':
            return [{k: v for k, v in m.items() if k not in ('original', 'cleaned', 'history', 'question_draft')} for m in s['materials'].values()]
        if action == 'material_get':
            return s['materials'][b['id']]
        if action == 'material_save':
            m = s['materials'][b['id']]
            if not str(b.get('cleaned', '')).strip():
                raise ValueError('整理稿不能为空')
            for k in ('cleaned', 'subject', 'chapter', 'teacher', 'edition'):
                if k in b:
                    m[k] = str(b[k])[:MAX_FIELD(k)]
            m['status'] = 'verified' if b.get('verified') else 'draft'
            self.store.markdown('资料整理', m['id'], m['cleaned'])
            return m
        if action == 'practice':
            m = s['materials'][b['id']]
            if m['status'] != 'verified':
                raise ValueError('请先核对并确认资料')
            text = str(b.get('text', '')).strip()
            if len(text) < 5:
                raise ValueError('请先写下自己的体系回忆')
            ok = bool(b.get('passed'))
            m['practice'].append({'date': today(), 'text': text[:20000], 'passed': ok, 'assessment': 'self'})
            if ok:
                self.add_xp('practice:' + m['id'] + ':' + today(), s['config']['xp_system'], '体系自评')
            return {'ok': True, 'assessment': 'self'}
        if action == 'cards':
            return {'all': list(s['cards'].values()), 'queue': self.card_queue()}
        if action == 'card_add':
            front, back = str(b.get('front', '')).strip(), str(b.get('back', '')).strip()
            if not front or not back:
                raise ValueError('卡片正面和背面不能为空')
            source = b.get('material_id', '')
            if source and s['materials'][source]['status'] != 'verified':
                raise ValueError('资料尚未核对，不能进入背诵')
            if any(c['front'] == front and c['back'] == back and c.get('material_id') == source for c in s['cards'].values()):
                raise ValueError('此卡片已存在')
            c = {'id': ident(), 'front': front[:12000], 'back': back[:20000], 'subject': str(b.get('subject') or '待分类'), 'material_id': source, 'source_version': materials.digest(s['materials'][source]['cleaned']) if source else '', 'reps': 0, 'due': 0, 's': 0, 'd': 0, 'last': 0}
            s['cards'][c['id']] = c
            self.store.markdown('卡片', c['id'], '# '+front+'\n\n'+back+'\n\n来源考点：'+source)
            return c
        if action == 'card_rate':
            c = s['cards'][b['id']]
            if c not in self.card_queue():
                raise ValueError('这张卡不在当前复习队列，不能重复评分')
            g = int(b['rating'])
            if g not in (1, 2, 3, 4):
                raise ValueError('评分必须为1至4')
            now = time.time()
            is_new = not c['reps']
            if is_new:
                c['s'], c['d'] = fsrs.init_s(g), fsrs.init_d(g)
            else:
                elapsed = max(0, (now-c['last']) / 86400)
                r = fsrs.retrievability(elapsed, c['s'])
                c['s'] = fsrs.forget_s(c['d'], c['s'], r) if g == 1 else fsrs.recall_s(c['d'], c['s'], r, g)
                c['d'] = fsrs.next_d(c['d'], g)
            c['due'] = now + (60 if g == 1 else fsrs.interval(c['s'], .9, 36500) * 86400)
            c['last'], c['reps'] = now, c['reps'] + 1
            s['reviews'].append({'card': c['id'], 'date': today(), 'rating': g, 'new': is_new})
            self.add_xp('card:' + c['id'] + ':' + today(), s['config']['xp_card_good'] if g > 1 else s['config']['xp_card_again'], '背诵卡自评')
            return c
        if action == 'questions':
            return [dict(self.public_question(q), wrong=next((not a['correct'] for a in reversed(s['attempts']) if a['qid'] == q['id']), False)) for q in s['questions'].values()]
        if action == 'question_add':
            q = copy.deepcopy(b)
            q['id'] = ident()
            q['type'] = q.get('type', 'single')
            if q['type'] not in ('single', 'multiple', 'indefinite'):
                raise ValueError('未知题型')
            if not isinstance(q.get('options'), dict) or not 2 <= len(q['options']) <= 8:
                raise ValueError('题目须有2至8个选项')
            if not str(q.get('stem', '')).strip():
                raise ValueError('题干不能为空')
            answer = sorted(set(q.get('answer') or []))
            if not answer or any(k not in q['options'] for k in answer) or (q['type'] == 'single' and len(answer) != 1):
                raise ValueError('答案与题型或选项不一致')
            if not b.get('verified'):
                raise ValueError('请确认题干选项和答案已核对')
            q.update({'answer': answer, 'subject': str(q.get('subject') or '待分类'), 'explanation': str(q.get('explanation') or '暂无解析，待补充'), 'point': str(q.get('point') or ''), 'source': str(q.get('source') or '手动录入')})
            s['questions'][q['id']] = q
            return self.public_question(q)
        if action == 'question_answer':
            q = s['questions'][b['id']]
            answer = sorted(set(b.get('answer') or []))
            if not answer or any(k not in q['options'] for k in answer) or (q['type'] == 'single' and len(answer) != 1):
                raise ValueError('请选择有效答案')
            if any(a.get('request_id') == b.get('request_id') for a in s['attempts']) and b.get('request_id'):
                return next(a for a in s['attempts'] if a.get('request_id') == b['request_id'])
            repeat = any(a['qid'] == q['id'] for a in s['attempts'])
            a = {'id': ident(), 'qid': q['id'], 'question': copy.deepcopy(q), 'answer': answer, 'correct': answer == q['answer'], 'date': today(), 'repeat': repeat, 'assessment': 'program', 'request_id': b.get('request_id')}
            s['attempts'].append(a)
            if not repeat:
                self.add_xp('question:' + q['id'], s['config']['xp_question_correct'] if a['correct'] else s['config']['xp_question_wrong'], '客观题首次作答')
            return a
        if action == 'exam_create':
            questions = b.get('questions') or []
            if not questions or len(questions) > 20:
                raise ValueError('请至少添加一道主观题问题，最多20问')
            for q in questions:
                if not str(q.get('prompt', '')).strip():
                    raise ValueError('问题不能为空')
                ids = []
                for p in q.get('points', []):
                    if not p.get('id') or not str(p.get('text', '')).strip() or p['id'] in ids:
                        raise ValueError('采分点需要唯一编号和内容')
                    ids.append(p['id'])
                    score = float(p.get('score', 0))
                    if not math.isfinite(score) or score <= 0 or score > 100:
                        raise ValueError('采分点分值需大于0且不超过100')
                    p['score'] = score
            minutes = int(b.get('minutes', 30))
            if not 1 <= minutes <= 300:
                raise ValueError('限时应为1至300分钟')
            e = {'id': ident(), 'title': str(b.get('title') or '主观题模拟'), 'material': str(b.get('material', ''))[:50000], 'questions': questions, 'mode': b.get('mode', 'exam'), 'minutes': minutes, 'answers': [''] * len(questions), 'submitted': False, 'started': None, 'assessment': None, 'revision': 0, 'strokes': []}
            s['exams'][e['id']] = e
            return self.exam_public(e)
        if action == 'exams':
            return [self.exam_public(e) for e in s['exams'].values()]
        if action == 'exam_start':
            e = s['exams'][b['id']]
            if not e['started']:
                e['started'] = time.time()
            return self.exam_public(e)
        if action == 'exam_save':
            e = s['exams'][b['id']]
            if e['submitted']:
                raise ValueError('试卷已交卷，不能修改作答')
            if e['started'] is None:
                raise ValueError('请先开始作答')
            if e['mode'] == 'exam' and time.time() > e['started'] + e['minutes'] * 60 + 5:
                raise ValueError('考试已到时，请交卷已保存的作答')
            if int(b.get('revision', -1)) != e['revision']:
                raise ValueError('作答版本冲突，请重新打开试卷，避免覆盖已保存内容')
            answers = b.get('answers')
            if not isinstance(answers, list) or len(answers) != len(e['questions']) or any(not isinstance(x,str) or len(x)>40000 for x in answers):
                raise ValueError('作答格式或长度不正确')
            e['answers'] = answers
            if 'strokes' in b:
                self.validate_strokes(b['strokes'])
                e['strokes'] = b['strokes']
            e['revision'] += 1
            return {'revision': e['revision']}
        if action == 'exam_submit':
            e = s['exams'][b['id']]
            if not e['started']:
                raise ValueError('请先开始作答')
            if not e['submitted']:
                e['submitted'], e['ended'] = True, time.time()
                self.add_xp('exam:' + e['id'], s['config']['xp_exam_submit'], '主观题提交（未评分）')
            return self.exam_public(e)
        if action == 'notes':
            return list(s['notes'].values())
        if action == 'note_save':
            self.validate_strokes(b.get('strokes', []))
            n = {'id': b.get('id') or ident(), 'title': str(b.get('title') or '手写笔记')[:120], 'text': str(b.get('text') or '')[:40000], 'strokes': b.get('strokes', []), 'revision': 0}
            old = s['notes'].get(n['id'])
            if old and int(b.get('revision', -1)) != old['revision']:
                raise ValueError('笔记版本冲突，请重新载入')
            n['revision'] = (old['revision'] if old else 0) + 1
            s['notes'][n['id']] = n
            self.store.markdown('笔记', n['id'], '# '+n['title']+'\n\n'+n['text'])
            return n
        if action == 'pulse':
            tab = str(b.get('tab', ''))[:100]
            now = time.monotonic()
            previous = self.pulses.get(tab)
            self.pulses[tab] = now
            if previous and b.get('active') and b.get('visible') and b.get('view') in ('cards', 'system', 'questions', 'exam', 'notes'):
                elapsed = min(30, max(0, now-previous))
                # 同一主机并发标签/设备总时间不重复累加
                last = self.pulses.get('_counted', previous)
                elapsed = min(elapsed, max(0, now-last))
                self.pulses['_counted'] = now
                s['activity'][today()] = s['activity'].get(today(), 0) + elapsed
            return {'seconds': s['activity'].get(today(), 0)}
        if action == 'ai':
            task = b['task']
            if task in ('clean','cards','explain'):
                m = s['materials'][b['id']]
                if task != 'clean' and m['status'] != 'verified':
                    raise ValueError('资料需先核对')
                payload = {'source': m['source'], 'version': m['fingerprint'], 'text': m['original'] if task == 'clean' else m['cleaned'], 'question': str(b.get('question',''))[:2000]}
            elif task == 'grade':
                e = s['exams'][b['id']]
                if not e['submitted']:
                    raise ValueError('交卷前不能AI评阅')
                points = []
                for i,q in enumerate(e['questions']):
                    for p in q.get('points', []):
                        points.append(dict(p, id='%s:%s' % (i,p['id'])))
                if not points:
                    raise ValueError('没有可靠采分点，只能对照参考答案')
                payload = {'material': e['material'], 'questions': e['questions'], 'answers': e['answers'], 'points': points}
            else:
                raise ValueError('未知AI任务')
            result = ai.request(self.settings, s, task, payload)
            data = result['result']
            if task == 'clean':
                if not isinstance(data.get('text'), str) or not isinstance(data.get('warnings'), list):
                    raise ValueError('AI整理格式不完整，未改动整理稿')
                m['ai_draft'] = data['text']
                m['ai_warnings'] = data['warnings']
            elif task == 'cards':
                if not isinstance(data.get('cards'),list) or any(not isinstance(c,dict) or not c.get('front') or not c.get('back') for c in data['cards']):
                    raise ValueError('AI制卡格式不完整')
                m['card_drafts'] = data['cards'][:10]
            elif task == 'grade':
                expected = {p['id']:p for p in points}
                got = data.get('points')
                if not isinstance(got,list) or len(got)!=len(expected) or {p.get('id') for p in got}!=set(expected) or any(type(p.get('hit')) is not bool for p in got):
                    raise ValueError('AI采分点不完整或重复，未记录评分')
                for p in got:
                    i = int(p['id'].split(':',1)[0])
                    evidence = str(p.get('evidence') or '')
                    if p['hit'] and (not evidence.strip() or evidence not in e['answers'][i]):
                        raise ValueError('AI命中点缺少有效作答证据，未记录评分')
                total = sum(p['score'] for p in points)
                score = sum(expected[p['id']]['score'] for p in got if p['hit'])
                e.update({'assessment': 'ai', 'score': score, 'total': total, 'ratio': score/total, 'grading': got})
                self.add_xp('graded:' + e['id'], min(s['config']['xp_exam_ai_max'], round(score)), '主观题AI评阅')
                result.update({'score':score, 'total':total})
            self.store.markdown('AI结果', ident(), json.dumps(result, ensure_ascii=False, indent=2))
            return result
        raise ValueError('未知操作')

    def exam_public(self, e):
        d = copy.deepcopy(e)
        if not e['submitted']:
            for q in d['questions']:
                q.pop('reference', None)
                q.pop('points', None)
        if e['started']:
            d['remaining'] = max(0, int(e['minutes']*60-(time.time()-e['started'])))
        return d

    def validate_strokes(self, strokes):
        if not isinstance(strokes, list) or len(strokes)>5000:
            raise ValueError('笔迹数量超限')
        count = 0
        for stroke in strokes:
            if not isinstance(stroke,list):
                raise ValueError('笔迹格式错误')
            count += len(stroke)
            if count > 100000:
                raise ValueError('笔迹点数量超限，请另建笔记')
            for xy in stroke:
                if not isinstance(xy,list) or len(xy)!=2 or any(not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in xy):
                    raise ValueError('笔迹坐标不合法')


def MAX_FIELD(k):
    return 800000 if k == 'cleaned' else 200
