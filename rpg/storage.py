"""训练目录内原子存档与每日备份。Service调用；schema_version=1，数据含materials/cards/questions/attempts/exams/notes/events。"""
import copy
import datetime as dt
import json
import os
import secrets
import threading
from pathlib import Path

DEFAULT_CONFIG = {'start_date': '2026-12-01', 'target_date': '2027-09-10', 'subjective_date': '', 'daily_minutes': 180, 'new_per_day': 20, 'reviews_per_day': 200}
SUBJECTS = ['民法', '刑法', '民事诉讼法', '刑事诉讼法', '行政法与行政诉讼法', '商经知', '三国法', '理论法']


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.%s.tmp' % secrets.token_hex(4))
    try:
        with tmp.open('w', encoding='utf-8', newline='\n') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()


class Storage:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.train = self.root / '训练'
        if self.train.is_symlink():
            raise ValueError('训练目录不能是符号链接')
        self.file = self.train / '存档' / '存档.json'
        self.lock = threading.RLock()
        self.check(self.file)
        if self.file.exists():
            try:
                self.state = json.loads(self.file.read_text(encoding='utf-8'))
            except (ValueError, OSError) as e:
                raise ValueError('存档无法读取，请先备份并从训练/存档/备份恢复；不会覆盖原存档') from e
            if self.state.get('schema_version') != 1:
                raise ValueError('此存档版本不受支持，请使用对应版本程序')
        else:
            self.state = {}
        defaults = {'schema_version': 1, 'config': copy.deepcopy(DEFAULT_CONFIG), 'materials': {}, 'cards': {}, 'questions': {}, 'attempts': [], 'exams': {}, 'notes': {}, 'events': [], 'activity': {}, 'reviews': [], 'xp': 0}
        for k, v in defaults.items():
            self.state.setdefault(k, v)
        for k, v in DEFAULT_CONFIG.items():
            self.state['config'].setdefault(k, v)

    def check(self, path):
        path = Path(path)
        try:
            path.resolve().relative_to(self.train.resolve())
            self.train.resolve().relative_to(self.root)
        except ValueError:
            raise ValueError('写入位置必须在库内训练目录中')
        # 防止目录软链接绕过训练边界
        for p in [self.train, path] + list(path.parents):
            if p == self.root:
                break
            if p.is_symlink():
                raise ValueError('数据路径不允许符号链接')
        return path

    def save(self):
        self.check(self.file)
        today = dt.date.today().isoformat()
        backup = self.check(self.file.parent / '备份' / ('存档-%s.json' % today))
        if self.file.exists() and not backup.exists():
            previous = json.loads(self.file.read_text(encoding='utf-8'))
            atomic_json(backup, previous)
        atomic_json(self.file, self.state)
        backups = sorted(backup.parent.glob('存档-*.json'))
        for p in backups[:-30]:
            self.check(p).unlink()

    def markdown(self, folder, ident, text):
        if not ident or any(c not in '0123456789abcdefghijklmnopqrstuvwxyz-_' for c in ident):
            raise ValueError('内容编号不合法')
        path = self.check(self.train / folder / (ident + '.md'))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(text, encoding='utf-8')
        os.replace(str(tmp), str(path))
