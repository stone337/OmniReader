import sqlite3
import json
import os
import uuid
import struct
import zlib
import re
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS english_wordbank (word TEXT PRIMARY KEY, frequency INTEGER DEFAULT 0, category TEXT, phonetic TEXT, translation TEXT, examples TEXT, source TEXT, mastered INTEGER DEFAULT 0, review_cnt INTEGER DEFAULT 0, last_review_time TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS dict_cache (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS vocab_notebook (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT, examples TEXT, source TEXT, mastered INTEGER DEFAULT 0, review_cnt INTEGER DEFAULT 0, last_review_time TEXT, add_time TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS audio_cache (word TEXT PRIMARY KEY, data BLOB, ext TEXT DEFAULT 'mp3')''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS base_vocabulary (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS offline_dictionary (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT)''')
            conn.commit()

    def get_word_info(self, word):
        """核心：物理层归一化查询"""
        clean_word = word.strip().lower()
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT phonetic, translation FROM dict_cache WHERE word = ?', (clean_word,))
            row = cursor.fetchone()
            if row:
                dct = dict(row)
                if dct.get('translation'):
                    t_val = dct['translation'].strip()
                    # 自愈机制
                    if t_val.endswith('...') or '...' in t_val or len(t_val) < 3:
                        return None
                        
                    import re
                    pattern = re.compile(r'(?<!\n)(?<!^)\b(n|v|vt|vi|adj|adv|prep|pron|abbr|conj|art|num|int)\.', re.IGNORECASE)
                    formatted_t = pattern.sub(r'\n\1.', t_val)
                    lines = [line.strip() for line in formatted_t.split("\n") if line.strip()]
                    dct['translation'] = "\n".join(lines)
                return dct
            return None

    def is_base_word(self, word):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM base_vocabulary WHERE word = ?', (word,))
            return cursor.fetchone() is not None

    def add_base_words_batch(self, words):
        with self._get_connection() as conn:
            conn.executemany('INSERT OR IGNORE INTO base_vocabulary (word) VALUES (?)', [(w.lower().strip(),) for w in words])
            conn.commit()

    def get_base_vocabulary(self, limit=100, offset=0):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.word, COALESCE(d.phonetic, b.phonetic) as phonetic, 
                       COALESCE(d.translation, b.translation) as translation
                FROM base_vocabulary b
                LEFT JOIN dict_cache d ON LOWER(TRIM(b.word)) = LOWER(TRIM(d.word))
                ORDER BY b.word ASC LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]

    def count_base_vocabulary(self):
        with self._get_connection() as conn:
            return conn.execute('SELECT COUNT(*) FROM base_vocabulary').fetchone()[0]

    def get_all_words_for_review(self, limit=None, offset=None):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            sql = '''
                SELECT w.word, COALESCE(d.phonetic, w.phonetic) as phonetic,
                       COALESCE(d.translation, w.translation) as translation,
                       w.examples, w.source, w.mastered, w.review_cnt, w.last_review_time, 'wordbank' as origin
                FROM english_wordbank w 
                LEFT JOIN dict_cache d ON w.word = d.word
                UNION ALL
                SELECT n.word, COALESCE(d.phonetic, n.phonetic) as phonetic,
                       COALESCE(d.translation, n.translation) as translation,
                       n.examples, n.source, n.mastered, n.review_cnt, n.last_review_time, 'notebook' as origin
                FROM vocab_notebook n 
                LEFT JOIN dict_cache d ON n.word = d.word
                WHERE n.word NOT IN (SELECT word FROM english_wordbank)
                ORDER BY mastered ASC, review_cnt ASC
            '''
            if limit is not None and offset is not None: 
                sql += f" LIMIT {limit} OFFSET {offset}"
            cursor.execute(sql)
            res = []
            for r in cursor.fetchall():
                it = dict(r)
                try: it['examples'] = json.loads(it['examples']) if it['examples'] else []
                except: it['examples'] = []
                res.append(it)
            return res

    def delete_word_entirely(self, word):
        with self._get_connection() as conn:
            conn.execute('DELETE FROM english_wordbank WHERE word = ?', (word,))
            conn.execute('DELETE FROM vocab_notebook WHERE word = ?', (word,))
            conn.execute('DELETE FROM dict_cache WHERE word = ?', (word.lower().strip(),))
            conn.execute('DELETE FROM audio_cache WHERE word = ?', (word.lower().strip(),))
            conn.commit()

    def update_mastery_level(self, word, level):
        with self._get_connection() as conn:
            conn.execute("UPDATE english_wordbank SET mastered = ? WHERE word = ?", (level, word))
            conn.execute("UPDATE vocab_notebook SET mastered = ? WHERE word = ?", (level, word))
            conn.commit()

    def update_review_stats(self, word, origin, grade):
        table = 'english_wordbank' if origin == 'wordbank' else 'vocab_notebook'
        with self._get_connection() as conn:
            # 1. 查询当前盒等级
            row = conn.execute(f"SELECT mastered FROM {table} WHERE word = ?", (word,)).fetchone()
            current_mastered = row[0] if (row and row[0] is not None) else 0
            
            # 2. 依据莱特纳（Leitner）算法计算新的熟练度盒子等级（0~5 级盒）
            if grade == 0:
                new_mastered = 0  # 没记住：一瞬间打回新手 0 号盒
            elif grade == 1:
                new_mastered = current_mastered  # 模糊：维持现状不退，但不晋级
            else:
                new_mastered = min(5, current_mastered + 1)  # 记住了：等级晋升 +1

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(f'UPDATE {table} SET review_cnt = review_cnt+1, last_review_time = ?, mastered = ? WHERE word = ?', (now, new_mastered, word))
            conn.commit()

    def get_dict_cache(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT word, phonetic, translation FROM dict_cache')
            return {row[0]: {"phonetic": row[1], "translation": row[2]} for row in cursor.fetchall()}

    def update_word_dict(self, word, phonetic, translation):
        with self._get_connection() as conn:
            conn.execute('INSERT OR REPLACE INTO dict_cache (word, phonetic, translation) VALUES (?, ?, ?)', (word.lower().strip(), phonetic, translation))
            conn.commit()

    def get_wordbank_items(self, category=None, search=None, limit=20, offset=0):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM english_wordbank WHERE 1=1"
            params = []
            if category: query += " AND category = ?"; params.append(category)
            if search: query += " AND word LIKE ?"; params.append(f"%{search}%")
            query += " ORDER BY frequency DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(query, params)
            res = []
            for r in cursor.fetchall():
                it = dict(r)
                try: it['examples'] = json.loads(it['examples']) if it['examples'] else []
                except: it['examples'] = []
                res.append(it)
            return res

    def count_wordbank(self, category=None, search=None):
        with self._get_connection() as conn:
            query = "SELECT COUNT(*) FROM english_wordbank WHERE 1=1"; params = []
            if category: query += " AND category = ?"; params.append(category)
            if search: query += " AND word LIKE ?"; params.append(f"%{search}%")
            return conn.execute(query, params).fetchone()[0]

    def save_wordbank_batch(self, items_list):
        with self._get_connection() as conn:
            conn.executemany('''INSERT OR REPLACE INTO english_wordbank (word, frequency, category, phonetic, translation, examples, source, mastered, review_cnt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)''',
                            [(it['word'], it['frequency'], it['category'], it.get('phonetic'), it.get('translation'), json.dumps(it.get('examples', [])), it.get('source'), 0) for it in items_list])
            conn.commit()

    def clear_wordbank(self):
        with self._get_connection() as conn: 
            conn.execute('DELETE FROM english_wordbank')
            conn.commit()

    def clear_audio_and_dict_cache(self):
        with self._get_connection() as conn: 
            conn.execute('DELETE FROM audio_cache')
            conn.execute('DELETE FROM dict_cache')
            conn.commit()

    def get_notebook_data(self):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vocab_notebook')
            lst = []
            for row in cursor.fetchall():
                it = dict(row); it['examples'] = json.loads(it['examples']) if it['examples'] else []
                lst.append(it)
            return {"list": lst}

    def add_to_notebook(self, it):
        with self._get_connection() as conn:
            conn.execute('''INSERT OR IGNORE INTO vocab_notebook (word, phonetic, translation, examples, source, mastered, add_time) VALUES (?, ?, ?, ?, ?, 0, ?)''', 
                        (it['word'], it.get('phonetic'), it.get('translation'), json.dumps(it.get('examples', [])), it.get('source'), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()

    def delete_from_notebook(self, word):
        with self._get_connection() as conn: 
            conn.execute('DELETE FROM vocab_notebook WHERE word = ?', (word,))
            conn.commit()

    def save_audio(self, word, data):
        with self._get_connection() as conn: 
            conn.execute('INSERT OR REPLACE INTO audio_cache (word, data) VALUES (?, ?)', (word.lower().strip(), data))
            conn.commit()

    def get_audio(self, word):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT data FROM audio_cache WHERE word = ?', (word.lower().strip(),))
            row = cursor.fetchone()
            return row[0] if row else None

    def add_offline_words_batch(self, words_batch):
        with self._get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS offline_dictionary (word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT)')
            conn.executemany('INSERT OR REPLACE INTO offline_dictionary (word, phonetic, translation) VALUES (?, ?, ?)', words_batch)
            conn.commit()

    def get_offline_word_info(self, word):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT phonetic, translation FROM offline_dictionary WHERE LOWER(TRIM(word)) = LOWER(TRIM(?))', (word,))
            row = cursor.fetchone()
            return dict(row) if row else None

class MiniMdxReader:
    """标准 MDX 离线词典格式的高效纯 Python 解码器。"""
    def __init__(self, filename):
        self.filename = filename

    def read_word_entries(self, progress_callback=None):
        entries = []
        try:
            with open(self.filename, 'rb') as f:
                header_len_bytes = f.read(4)
                if len(header_len_bytes) < 4:
                    return []
                header_size = struct.unpack('>I', header_len_bytes)[0]
                header_data = f.read(header_size)

                is_utf16 = b'UTF-16' in header_data
                encoding = 'utf-16' if is_utf16 else 'utf-8'

                f.seek(4 + header_size)
                file_content = f.read()

                zlib_flags = [b'\x78\xda', b'\x78\x9c', b'\x78\x5e', b'\x78\x01']
                decompressed_chunks = []

                for flag in zlib_flags:
                    offset = 0
                    while True:
                        idx = file_content.find(flag, offset)
                        if idx == -1:
                            break
                        try:
                            dec_obj = zlib.decompressobj()
                            chunk = dec_obj.decompress(file_content[idx:idx+1024*1024])
                            if chunk:
                                chunk_str = None
                                for enc in [encoding, 'utf-8', 'utf-16', 'gbk', 'utf-16le']:
                                    try:
                                        chunk_str = chunk.decode(enc)
                                        if chunk_str:
                                            break
                                    except:
                                        pass
                                if not chunk_str:
                                    chunk_str = chunk.decode('utf-8', errors='ignore')
                                
                                decompressed_chunks.append(chunk_str)
                                if progress_callback and len(decompressed_chunks) % 15 == 0:
                                    progress_callback(len(decompressed_chunks) * 500, 150000, "解密词条中")
                        except Exception:
                            pass
                        offset = idx + 2
                        if len(decompressed_chunks) > 800:
                            break
                    if decompressed_chunks:
                        break
                
                all_text = "".join(decompressed_chunks)
                raw_entries = all_text.split("</>")
                
                html_clean_re = re.compile(r'<[^>]+>')
                for it in raw_entries:
                    lines = [line.strip() for line in it.split("\n") if line.strip()]
                    if len(lines) >= 2:
                        word = lines[0]
                        if re.match(r'^[a-zA-Z\s\-\']+$', word) and not word.startswith("@@"):
                            translation_raw = "\n".join(lines[1:])
                            translation = html_clean_re.sub("", translation_raw).strip()
                            phonetic = ""
                            ph_match = re.search(r'/\[(.*?)\]/', translation_raw) or re.search(r'/ (.*?) /', translation_raw)
                            if ph_match:
                                phonetic = ph_match.group(1)
                            entries.append((word, phonetic, translation))
        except Exception as e:
            print(f"[MDX解析报错] {e}")
        return entries
