"""只读扫描既有资料与OCR结构整理。normalize返回原文、整理稿、元信息、警告和题目草稿；不做法律内容推断。"""
import hashlib
import json
import re
from pathlib import Path

SOURCE_DIRS = ['10-科目', '20-错题', '30-案例', '40-法条与年度变动', '50-复习管理', '60-真题库', '99-讲义PDF', '99-知识点库']
MAX_TEXT = 800000


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def metadata(text):
    m = re.match(r'^\ufeff?---\s*\n(.*?)\n---\s*\n', text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ':' not in line:
                continue
            k, v = line.split(':', 1)
            v = v.strip()
            try:
                meta[k.strip()] = json.loads(v)
            except ValueError:
                meta[k.strip()] = v.strip('"\'')
        return meta, text[m.end():]
    return meta, text


def normalize(text, name):
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        raise ValueError('请选择非空Markdown或文本，单篇最多80万字符')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    meta, body = metadata(text)
    title = str(meta.get('title') or Path(name).stem)[:120]
    subject = str(meta.get('subject') or '待分类')[:50]
    warnings = []
    if '思维导图' in body or '示意图' in body:
        warnings.append('导图/示意图已变为线性文字，层级及连线需对照原页核查。')
    if re.search(r'^[一十→+]|^实体程序|^例外十', body, re.M):
        warnings.append('检测到疑似表格和OCR连接字符；尚未推断或修正法律含义。')
    if re.search(r'\n\d{1,4}\s*\n', body):
        warnings.append('检测到孤立数字，可能是印刷页码；保留原文供核对。')
    if '随堂练习' in body:
        warnings.append('检测到随堂练习；跨页题干、选项、脚注与答案需核对。')
    lines = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r'^<!--\s*OCR_PAGE:', line):
            n = re.search(r'OCR_PAGE:\s*(\d+)', line)
            lines.append('\n> OCR页标记：%s（与印刷页码分别记录）\n' % (n.group(1) if n else '待核对'))
        elif line in ['原则', '例外', '实体', '程序']:
            lines.append('\n## ' + line + '\n')
        elif line.startswith('「随堂练习') or line.startswith('[随堂练习'):
            lines.append('\n## 随堂练习（待核对）\n' + line)
        elif re.match(r'^[ABCD][.．、]', line):
            lines.append('\n' + line)
        else:
            lines.append(line)
    clean = '\n\n'.join(lines)
    if not clean.startswith('# '):
        clean = '# ' + title + '\n\n' + clean
    qdraft = None
    qm = re.search(r'[「\[]随堂练习\s*\d*\s*(.*?)(?:[（(]20\d{2}[^\n]*|\n[友注]：|\n①)', body, re.S)
    opts = dict(re.findall(r'^([ABCD])[.．、]\s*(.+)$', body, re.M))
    ans = re.search(r'答案\s*[:：]\s*([ABCD]+)', body)
    if qm and len(opts) == 4 and ans:
        qdraft = {'stem': qm.group(1).strip(), 'options': {k: opts[k] for k in sorted(opts)}, 'answer': sorted(set(ans.group(1))), 'type': 'single' if len(ans.group(1)) == 1 else 'multiple', 'explanation': '', 'subject': subject, 'point': title, 'status': 'draft'}
    pages = re.findall(r'OCR_PAGE:\s*(\d+)', body)
    return {'title': title, 'subject': subject, 'meta': meta, 'original': text, 'cleaned': clean, 'warnings': warnings, 'pages': pages, 'question_draft': qdraft, 'fingerprint': digest(text)}


def safe_source(root, rel):
    root = Path(root).resolve()
    p = root / str(rel)
    if p.is_symlink() or any(x.is_symlink() for x in p.parents if x != root and root in x.parents):
        raise ValueError('资料路径不能使用符号链接')
    try:
        p.resolve().relative_to(root)
    except ValueError:
        raise ValueError('资料路径不在选定库中')
    if not p.parts or Path(rel).parts[0] not in SOURCE_DIRS:
        raise ValueError('只能读取约定的资料目录')
    if p.suffix.lower() not in ('.md', '.txt', '.pdf', '.png', '.jpg', '.jpeg'):
        raise ValueError('不支持此资料格式')
    return p


def scan(root):
    root = Path(root)
    result = []
    for folder in SOURCE_DIRS:
        base = root / folder
        if not base.is_dir() or base.is_symlink():
            continue
        for p in sorted(base.rglob('*')):
            if p.is_file() and p.suffix.lower() in ('.md', '.txt', '.pdf') and not p.is_symlink():
                try:
                    rel = p.relative_to(root).as_posix()
                    safe_source(root, rel)
                except ValueError:
                    continue
                result.append({'path': rel, 'name': p.name, 'size': p.stat().st_size, 'kind': p.suffix.lower()[1:]})
                if len(result) >= 3000:
                    return result
    return result
