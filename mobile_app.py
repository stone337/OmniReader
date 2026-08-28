import flet as ft
import re
import os
import sys
import threading
import traceback
import datetime
import shutil

# =====================================================================
# 🛡️ Flet 全版本万能兼容防护盾 (Polyfills)
# 100% 动态补全并对齐所有 Flet 版本的 border、padding、margin 与 borderRadius 属性差异
# =====================================================================
if not hasattr(ft.border, "all"):
    ft.border.all = lambda width=1, color="black": ft.border.Border(
        top=ft.border.BorderSide(width, color),
        bottom=ft.border.BorderSide(width, color),
        left=ft.border.BorderSide(width, color),
        right=ft.border.BorderSide(width, color)
    )
if not hasattr(ft.border, "only"):
    ft.border.only = lambda top=None, bottom=None, left=None, right=None: ft.border.Border(
        top=top, bottom=bottom, left=left, right=right
    )
if not hasattr(ft.padding, "symmetric"):
    ft.padding.symmetric = lambda horizontal=0, vertical=0: ft.padding.Padding(horizontal, vertical, horizontal, vertical)
if not hasattr(ft.padding, "only"):
    ft.padding.only = lambda left=0, top=0, right=0, bottom=0: ft.padding.Padding(left, top, right, bottom)
if not hasattr(ft.margin, "only"):
    ft.margin.only = lambda left=0, top=0, right=0, bottom=0: ft.margin.Margin(left, top, right, bottom)
if not hasattr(ft.margin, "symmetric"):
    ft.margin.symmetric = lambda horizontal=0, vertical=0: ft.margin.Margin(horizontal, vertical, horizontal, vertical)
if not hasattr(ft.border_radius, "only"):
    ft.border_radius.only = lambda top_left=0, top_right=0, bottom_left=0, bottom_right=0: ft.border_radius.BorderRadius(
        top_left, top_right, bottom_left, bottom_right
    )
if not hasattr(ft.border_radius, "all"):
    ft.border_radius.all = lambda value=0: ft.border_radius.BorderRadius(value, value, value, value)
if not hasattr(ft, "NavigationDestination") and hasattr(ft, "NavigationBarDestination"):
    ft.NavigationDestination = ft.NavigationBarDestination

# =====================================================================
# 📱 移动端前后端合流与数据库接口导入
# =====================================================================
from english_db import DatabaseManager
from mobile_tts import MobileTTSEngine

# iOS 扁平美学偏好色系
BG_MAIN = "#F2F2F7"        # iOS System Gray 6 (奶油底色)
BG_CARD = "#FFFFFF"        # 悬浮纯白卡片
PRIMARY_COLOR = "#007AFF"  # iOS 经典蓝色
HIGHLIGHT_COLOR = "#FF9500" # iOS 琥珀橘金
TEXT_MAIN = "#1C1C1E"      # 深灰黑
TEXT_SUB = "#8E8E93"       # 经典中灰
BORDER_COLOR = "#E5E5EA"   # 极细分割线

def main(page: ft.Page):
    # 🐞 极速调试滚屏日志记录器
    logs_list = []
    
    # 调试文本框 (黑客绿高亮)
    debug_text = ft.Text(
        value="[00:00] 🐞 调试天眼控制台已启动...\n", 
        size=10, 
        font_family="monospace", 
        color="#00FF00",
        selectable=True
    )
    
    # 滚动容器
    debug_console = ft.Container(
        content=ft.Column([
            ft.Text("🐞 手机真机/模拟器实时调试日志看板", size=9, weight="bold", color="#8E8E93"),
            debug_text
        ], scroll=ft.ScrollMode.AUTO, spacing=2),
        bgcolor="#000000",
        padding=8,
        height=130, # 锁定 130 像素高度
        border=ft.border.only(bottom=ft.BorderSide(2, PRIMARY_COLOR))
    )

    def log_debug(msg):
        now_str = datetime.datetime.now().strftime("%M:%S")
        full_msg = f"[{now_str}] {msg}\n"
        print(full_msg) # 同时输出到系统 stdio
        logs_list.append(full_msg)
        if len(logs_list) > 15:
            logs_list.pop(0) # 保持最新 15 行
        debug_text.value = "".join(logs_list)
        try:
            page.update()
        except:
            pass

    try:
        log_debug("OmniReader 正在初始化手机环境...")
        
        page.title = "📱 English OmniReader 移动研习端"
        page.window_width = 420
        page.window_height = 820
        page.window_resizable = True
        page.bgcolor = BG_MAIN
        page.padding = 0
        page.spacing = 0

        # 计算并创建可写私有数据目录
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        log_debug(f"手机 APP 路径: {BASE_DIR}")
        
        writeable_dir = os.path.expanduser("~")
        if sys.platform == "win32":
            writeable_dir = os.path.join(BASE_DIR, "workbench_data")
            
        log_debug(f"手机可写私有目录: {writeable_dir}")
        os.makedirs(writeable_dir, exist_ok=True)
        
        DB_PATH = os.path.join(writeable_dir, "workbench.db")
        log_debug(f"SQLite 物理连接路径: {DB_PATH}")

        # 首次启动自愈释放
        assets_db = os.path.join(BASE_DIR, "workbench_data", "workbench.db")
        log_debug(f"出厂预装只读词典路径: {assets_db}")
        
        if not os.path.exists(DB_PATH):
            log_debug("检测到 App 首次冷启动，正在释放预置词典...")
            if os.path.exists(assets_db):
                try:
                    shutil.copy(assets_db, DB_PATH)
                    log_debug("[OK] 词典数据库复制成功并完全就绪！")
                except Exception as e:
                    log_debug(f"[!] 复制词典数据库失败: {e}")
            else:
                log_debug("[!] 警告：未在 assets 中找到预置 workbench.db 文件！")
        else:
            log_debug("[OK] 缓存目录中已存在可写数据库。")

        log_debug("正在连接并实例化 DatabaseManager...")
        db = DatabaseManager(DB_PATH)
        log_debug("[OK] 数据库实例化成功！")

        log_debug("正在装配手机专属原生发音中枢 TTSEngine...")
        tts = MobileTTSEngine(page)
        log_debug("[OK] 原生发音中枢装配成功！")

        # 状态变量
        current_tab = "read"
        current_playing_index = -1
        review_queue = []
        review_index = 0

        # =====================================================================
        # 🌟 查词 Bottom Sheet (手机端原生 Embedded Bottom Sheet Overlay)
        # =====================================================================
        lbl_word = ft.Text("Word", size=18, weight=ft.FontWeight.BOLD, color=TEXT_MAIN)
        lbl_phonetic = ft.Text("/['word]/", size=13, color=TEXT_SUB)
        txt_translation = ft.TextField(
            value="", 
            multiline=True, 
            read_only=True, 
            border=ft.InputBorder.NONE,
            text_size=13,
            color=TEXT_MAIN,
            expand=True
        )

        # 底部查词滑滑卡容器
        bottom_sheet = ft.Container(
            content=ft.Column(
                controls=[
                    # iOS 经典拖动 Handle
                    ft.Container(
                        width=40, height=5, bgcolor=BORDER_COLOR, border_radius=3, alignment=ft.alignment.Alignment(0, 0)
                    ),
                    # 头部大字及关闭按键
                    ft.Row(
                        controls=[
                            lbl_word,
                            ft.IconButton(
                                icon="close", 
                                icon_color=TEXT_SUB, 
                                icon_size=16, 
                                bgcolor="#F2F2F7",
                                on_click=lambda e: hide_sheet()
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    # 音标与播放
                    ft.Row(
                        controls=[
                            lbl_phonetic,
                            ft.TextButton(
                                content=ft.Row([ft.Icon("volume_up", size=14, color=PRIMARY_COLOR), ft.Text("发音", size=11, color=PRIMARY_COLOR)]),
                                on_click=lambda e: play_word_pronunciation(lbl_word.value)
                            )
                        ]
                    ),
                    # 翻译展示区
                    txt_translation,
                    # 底部按钮
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                content=ft.Text("➕ 记入生词本", color="#ffffff"), 
                                bgcolor=PRIMARY_COLOR, 
                                height=36,
                                on_click=lambda e: add_to_notebook(lbl_word.value)
                            ),
                            ft.FilledButton(
                                content=ft.Text("🗑 物理清删", color="#ffffff"), 
                                bgcolor="#FF3B30", 
                                height=36,
                                on_click=lambda e: delete_word_from_db(lbl_word.value)
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=BG_CARD,
            border_radius=ft.border_radius.BorderRadius(top_left=20, top_right=20, bottom_left=0, bottom_right=0),
            border=ft.border.all(1, BORDER_COLOR),
            padding=20,
            height=220,
            bottom=-220, # 初始状态缩在最底端屏幕外
            animate_position=ft.Animation(300, ft.AnimationCurve.DECELERATE) # 💥 顺滑 iOS 上滑下滑手势动画！
        )

        def play_word_pronunciation(word):
            if word:
                log_debug(f"🔊 发音: {word}")
                # 自动异步播放该单词的发音
                threading.Thread(target=lambda: tts.speak_text_list([word], start_idx=0), daemon=True).start()

        def add_to_notebook(word):
            if not word: return
            translation = txt_translation.value
            db.add_to_notebook(word, lbl_phonetic.value, translation, "[]", "Mobile App")
            log_debug(f"[生词本] ➕ 记入: {word}")
            render_notebook_list()
            hide_sheet()

        def delete_word_from_db(word):
            if not word: return
            db.delete_from_notebook(word)
            log_debug(f"[生词本] 🗑 物理删除: {word}")
            render_notebook_list()
            hide_sheet()

        def show_sheet(word_text, phonetic_text="/[word]/", translation_text=""):
            log_debug(f"🔍 点击单词查词: {word_text}")
            lbl_word.value = word_text
            res = db.lookup_word(word_text, prioritize_mdx=True)
            if res:
                lbl_phonetic.value = f"/[{res.get('phonetic', '') or word_text}]/"
                txt_translation.value = res.get("translation", "暂无翻译")
                log_debug(f"[本地词典] 命中: {word_text}")
            else:
                lbl_phonetic.value = phonetic_text
                txt_translation.value = translation_text if translation_text else "正在联网查询中..."
                log_debug(f"[词典] 未命中缓存: {word_text}")
                
            bottom_sheet.bottom = 0 
            page.update()
            play_word_pronunciation(word_text)

        def hide_sheet():
            bottom_sheet.bottom = -220 
            page.update()

        # =====================================================================
        # 📖 Tab 1: 阅读语音界面
        # =====================================================================
        demo_paragraph = "Hello and welcome to your brand new English OmniReader! This is a high performance mobile software designed with pure apple minimalist aesthetics. Try clicking any word on this screen to see the native bottom sheet slide up smoothly from the bottom with automatic high fidelity pronunciation!"
        
        word_spans = []
        for raw_w in demo_paragraph.split(" "):
            clean_w = re.sub(r'[^a-zA-Z]', '', raw_w)
            word_spans.append(
                ft.TextSpan(
                    text=raw_w + " ",
                    style=ft.TextStyle(size=16, color=TEXT_MAIN),
                    on_click=lambda e, w=clean_w: show_sheet(w)
                )
            )

        reader_rich_text = ft.Text(
            spans=word_spans,
        )

        tab_read = ft.Container(
            content=ft.Column(
                controls=[
                    # 顶部 iOS Header Row
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text("📖 OmniReader", size=16, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
                                ft.Row([
                                    ft.IconButton(icon="folder_open", icon_color=PRIMARY_COLOR, icon_size=18),
                                    ft.IconButton(icon="bookmarks", icon_color=PRIMARY_COLOR, icon_size=18),
                                ])
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        bgcolor=BG_CARD,
                        height=52,
                        padding=ft.padding.symmetric(horizontal=16),
                        border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR))
                    ),
                    # 中间文章阅读视区
                    ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=reader_rich_text,
                                bgcolor="#FDFBF7", 
                                border_radius=12,
                                border=ft.border.all(1, BORDER_COLOR),
                                padding=18,
                                expand=True
                            )
                        ]),
                        padding=12,
                        expand=True
                    ),
                    # 底部网易云音乐控制条
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.IconButton(icon="skip_previous", icon_color=PRIMARY_COLOR),
                                ft.FilledButton(
                                    content=ft.Text("▶️ 播放语音", color="#ffffff"), 
                                    bgcolor=PRIMARY_COLOR, 
                                    height=32,
                                    on_click=lambda e: play_paragraph_audio()
                                ),
                                ft.IconButton(icon="skip_next", icon_color=PRIMARY_COLOR),
                            ], alignment=ft.MainAxisAlignment.CENTER),
                        ]),
                        bgcolor=BG_CARD,
                        height=60,
                        border_radius=16,
                        border=ft.border.all(1, BORDER_COLOR),
                        margin=ft.margin.only(left=12, right=12, bottom=8)
                    )
                ],
                spacing=0
            ),
            expand=True
        )

        def play_paragraph_audio():
            log_debug("▶️ 开始播放全文段落...")
            sentences = [s.strip() for s in demo_paragraph.split(".") if s.strip()]
            threading.Thread(target=lambda: tts.speak_text_list(sentences, start_idx=0), daemon=True).start()

        # =====================================================================
        # 📓 Tab 2: 生词本界面
        # =====================================================================
        notebook_list_container = ft.ListView(expand=True, padding=12)

        def render_notebook_list():
            log_debug("正在渲染本地生词列表...")
            notebook_list_container.controls.clear()
            try:
                nb_data = db.get_notebook_data()["list"]
                log_debug(f"从 SQLite 成功读取生词: {len(nb_data)} 个")
                if not nb_data:
                    notebook_list_container.controls.append(
                        ft.Container(
                            content=ft.Text("生词本目前空空如也~\n请点击【阅读语音】里的单词加入积累吧！", color=TEXT_SUB, text_align=ft.TextAlign.CENTER, size=13),
                            alignment=ft.alignment.Alignment(0, 0),
                            padding=50
                        )
                    )
                else:
                    for item in nb_data:
                        word = item["word"]
                        translation = item.get("translation", "")
                        phonetic = item.get("phonetic", "")
                        
                        notebook_list_container.controls.append(
                            ft.Container(
                                content=ft.Column([
                                    ft.Row([
                                        ft.Text(word, size=14, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
                                        ft.IconButton(icon="delete_outline", icon_color="#FF3B30", icon_size=16, on_click=lambda e, w=word: delete_word_from_db(w))
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Text(f"/[{phonetic}]/  {translation}", size=12, color=TEXT_SUB, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
                                ], spacing=4),
                                bgcolor=BG_CARD,
                                border_radius=12,
                                border=ft.border.all(1, BORDER_COLOR),
                                padding=12,
                                margin=ft.margin.symmetric(vertical=4),
                                on_click=lambda e, w=word, p=phonetic, t=translation: show_sheet(w, p, t) 
                            )
                        )
            except Exception as e:
                log_debug(f"[!] 渲染列表异常: {e}")
            page.update()

        # =====================================================================
        # ⚡ 莱特纳（Leitner）科学背词叠层遮罩板 (iOS Stack Overlay)
        # =====================================================================
        lbl_rev_counter = ft.Text("复习进度：0/0", size=13, weight=ft.FontWeight.BOLD, color=TEXT_SUB)
        lbl_rev_word = ft.Text("Word", size=24, weight=ft.FontWeight.BOLD, color=TEXT_MAIN)
        lbl_rev_ph = ft.Text("/['word]/", size=14, color=TEXT_SUB)
        txt_rev_trans = ft.TextField(
            value="", 
            multiline=True, 
            read_only=True, 
            border=ft.InputBorder.NONE,
            text_size=13,
            color=TEXT_SUB,
            expand=True
        )
        
        btn_reveal_rev = ft.ElevatedButton(
            content=ft.Text("👁 遮挡 / 点击看释义", color="#ffffff"), 
            bgcolor=PRIMARY_COLOR, 
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=19)),
            on_click=lambda e: reveal_rev_card()
        )
        
        grade_box_rev = ft.Row(visible=False, alignment=ft.MainAxisAlignment.CENTER)

        review_overlay = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row([
                            ft.IconButton(icon="arrow_back_ios_new", icon_color=PRIMARY_COLOR, icon_size=16, on_click=lambda e: close_review_flow()),
                            ft.Text("⚡ 莱特纳科学复习", size=16, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
                            ft.Container(width=16)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        bgcolor=BG_CARD,
                        height=52,
                        padding=ft.padding.symmetric(horizontal=12),
                        border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR))
                    ),
                    ft.Container(content=lbl_rev_counter, alignment=ft.alignment.Alignment(0, 0), padding=ft.padding.only(top=16)),
                    ft.Container(
                        content=ft.Column([
                            ft.Container(content=lbl_rev_word, alignment=ft.alignment.Alignment(0, 0), on_click=lambda e: play_word_pronunciation(lbl_rev_word.value)),
                            ft.Container(content=lbl_rev_ph, alignment=ft.alignment.Alignment(0, 0), on_click=lambda e: play_word_pronunciation(lbl_rev_word.value)),
                            ft.Container(content=txt_rev_trans, bgcolor="#F8FAFC", border=ft.border.all(1, BORDER_COLOR), padding=15, border_radius=10, expand=True),
                            ft.Container(content=ft.ElevatedButton("🔊 播放发音", color=PRIMARY_COLOR, bgcolor="#F2F2F7", on_click=lambda e: play_word_pronunciation(lbl_rev_word.value)), alignment=ft.alignment.Alignment(0, 0), padding=ft.padding.only(bottom=15))
                        ], spacing=10),
                        bgcolor=BG_CARD,
                        border_radius=18,
                        border=ft.border.all(1, BORDER_COLOR),
                        padding=20,
                        margin=20,
                        expand=True
                    ),
                    ft.Container(content=btn_reveal_rev, alignment=ft.alignment.Alignment(0, 0), padding=ft.padding.only(bottom=15)),
                    ft.Container(content=grade_box_rev, alignment=ft.alignment.Alignment(0, 0), padding=ft.padding.only(bottom=15))
                ],
                spacing=0
            ),
            bgcolor=BG_MAIN,
            visible=False, 
            expand=True
        )

        def select_review_queue(queue):
            nonlocal review_queue, review_index
            if not queue: return
            review_queue = queue
            review_index = 0
            
            choice_box.visible = False
            lbl_rev_counter.visible = True
            btn_reveal_rev.visible = True
            grade_box_rev.visible = False
            
            load_review_card()

        def load_review_card():
            nonlocal review_index
            if review_index >= len(review_queue):
                close_review_flow()
                return
                
            it = review_queue[review_index]
            lbl_rev_counter.value = f"复习进度：{review_index+1} / {len(review_queue)}"
            lbl_rev_word.value = it["word"]
            lbl_rev_ph.value = f"/[{it.get('phonetic', '') or '暂无音标'}]/"
            
            txt_rev_trans.value = "🙈 释义已隐藏，请先回想，点击下方看释义..."
            txt_rev_trans.color = TEXT_SUB
            
            btn_reveal_rev.visible = True
            grade_box_rev.visible = False
            page.update()
            play_word_pronunciation(it["word"])

        def reveal_rev_card():
            if review_index < len(review_queue):
                it = review_queue[review_index]
                txt_rev_trans.value = it.get("translation", "暂无翻译")
                txt_rev_trans.color = TEXT_MAIN
                
                btn_reveal_rev.visible = False
                grade_box_rev.visible = True
                page.update()
                play_word_pronunciation(it["word"])

        def submit_review_grade(grade):
            nonlocal review_index
            if review_index < len(review_queue):
                it = review_queue[review_index]
                db.update_review_stats(it["word"], origin="notebook", grade=grade)
                review_index += 1
                load_review_card()

        def close_review_flow():
            tts.stop()
            review_overlay.visible = False
            render_notebook_list()
            page.update()

        choice_box = ft.Column(spacing=12, alignment=ft.MainAxisAlignment.CENTER)
        
        grade_box_rev.controls = [
            ft.ElevatedButton("🔴 没记住", color="#ffffff", bgcolor="#FF3B30", on_click=lambda e: submit_review_grade(0)),
            ft.ElevatedButton("🟡 模糊", color="#ffffff", bgcolor=HIGHLIGHT_COLOR, on_click=lambda e: submit_review_grade(1)),
            ft.ElevatedButton("🟢 记住了", color="#ffffff", bgcolor="#34C759", on_click=lambda e: submit_review_grade(2)),
        ]

        def start_review_flow():
            log_debug("⚡ 开启莱特纳科学复习中枢...")
            nb_data = db.get_notebook_data()["list"]
            if not nb_data: return

            import datetime
            now = datetime.datetime.now()
            
            due_words = []
            new_words = []
            mastered_words = []
            intervals = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}

            for item in nb_data:
                box = item.get("mastered", 0) or 0
                last_review_str = item.get("last_review_time", "")
                is_new = (item.get("review_cnt", 0) or 0) == 0
                
                if is_new:
                    new_words.append(item)
                elif box >= 5:
                    mastered_words.append(item)
                
                is_due = False
                if not last_review_str:
                    is_due = True
                else:
                    try:
                        last_time = datetime.datetime.strptime(last_review_str, "%Y-%m-%d %H:%M:%S")
                        delta_days = (now - last_time).days
                        if box == 0:
                            is_due = (now - last_time).total_seconds() >= 12 * 3600
                        else:
                            is_due = delta_days >= intervals.get(box, 1)
                    except:
                        is_due = True
                if is_due:
                    due_words.append(item)

            choice_box.controls.clear()
            
            stats_card = ft.Container(
                content=ft.Column([
                    ft.Text("📊 莱特纳科学记忆统计", size=14, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
                    ft.Text(f"🎯 今日到期待复习： {len(due_words)} 个\n🆕 待启蒙新词数： {len(new_words)} 个\n📈 已通关已掌握： {len(mastered_words)} 个\n📁 全部生词总数： {len(nb_data)} 个", size=12, color=TEXT_SUB, weight=ft.FontWeight.BOLD)
                ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=BG_CARD,
                border_radius=14,
                border=ft.border.all(1, BORDER_COLOR),
                padding=15,
                margin=10
            )
            choice_box.controls.append(stats_card)
            
            choice_box.controls.append(
                ft.Container(
                    content=ft.Text("💡 莱特纳算法说明：\n系统将生词分成 0~5 号记忆盒子，等级越高复习间隔越长（最高30天）。没记住一瞬间打回 0 号盒重新高频巩固，记住了晋级。这能帮您把 90% 的精力集中在最难记的词上！", size=10, color=TEXT_SUB, max_lines=5),
                    padding=ft.padding.symmetric(horizontal=24)
                )
            )

            choice_box.controls.append(ft.ElevatedButton(f"🎯 科学复习今日到期词 ({len(due_words)}个)", width=320, height=42, color="#ffffff", bgcolor=PRIMARY_COLOR, on_click=lambda e: select_review_queue(due_words)))
            choice_box.controls.append(ft.ElevatedButton(f"🆕 复习待启蒙新词 ({len(new_words)}个)", width=320, height=42, color="#ffffff", bgcolor="#10B981", on_click=lambda e: select_review_queue(new_words)))
            choice_box.controls.append(ft.ElevatedButton(f"📖 温故知新：复习全部词 ({len(nb_data)}个)", width=320, height=42, color="#ffffff", bgcolor=HIGHLIGHT_COLOR, on_click=lambda e: select_review_queue(nb_data)))

            review_overlay.content = ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.IconButton(icon="arrow_back_ios_new", icon_color=PRIMARY_COLOR, icon_size=16, on_click=lambda e: close_review_flow()),
                        ft.Text("⚡ 莱特纳科学复习", size=16, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
                        ft.Container(width=16)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    bgcolor=BG_CARD,
                    height=52,
                    padding=ft.padding.symmetric(horizontal=12),
                    border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR))
                ),
                choice_box,
                ft.Container(
                    content=ft.Column([
                        ft.Container(content=lbl_rev_counter, alignment=ft.alignment.Alignment(0, 0), padding=ft.padding.only(top=16)),
                        ft.Container(
                            content=ft.Column([
                                ft.Container(content=lbl_rev_word, alignment=ft.alignment.Alignment(0, 0), on_click=lambda e: play_word_pronunciation(lbl_rev_word.value)),
                                ft.Container(content=lbl_rev_ph, alignment=ft.alignment.Alignment(0, 0), on_click=lambda e: play_word_pronunciation(lbl_rev_word.value)),
                                ft.Container(content=txt_rev_trans, bgcolor="#F8FAFC", border=ft.border.all(1, BORDER_COLOR), padding=15, border_radius=10, expand=True),
                                ft.Container(content=ft.ElevatedButton("🔊 播放发音", color=PRIMARY_COLOR, bgcolor="#F2F2F7", on_click=lambda e: play_word_pronunciation(lbl_rev_word.value)), alignment=ft.alignment.Alignment(0, 0), padding=ft.padding.only(bottom=15))
                            ], spacing=10),
                            bgcolor=BG_CARD,
                            border_radius=18,
                            border=ft.border.all(1, BORDER_COLOR),
                            padding=20,
                            margin=20,
                            expand=True
                        ),
                        ft.Container(content=btn_reveal_rev, alignment=ft.alignment.Alignment(0, 0), padding=ft.padding.only(bottom=15)),
                        ft.Container(content=grade_box_rev, alignment=ft.alignment.Alignment(0, 0), padding=ft.padding.only(bottom=15))
                    ], spacing=0, expand=True),
                    visible=False,
                    expand=True
                )
            ], spacing=0, expand=True)

            def select_review_queue(queue):
                nonlocal review_queue, review_index
                if not queue:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text("该复习队列目前为空哦~")))
                    return
                review_queue = queue
                review_index = 0
                
                review_overlay.content.controls[1].visible = False 
                review_overlay.content.controls[2].visible = True  
                load_review_card()

            review_overlay.content.controls[1].visible = True  
            review_overlay.content.controls[2].visible = False 
            review_overlay.visible = True
            page.update()

        tab_notebook = ft.Container(
            content=ft.Column(
                controls=[
                    # 顶部生词本 Header
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text("📓 我的生词", size=16, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
                                ft.Row([
                                    ft.FilledButton(content=ft.Text("⚡ 复习", color="#ffffff"), bgcolor=HIGHLIGHT_COLOR, height=28, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)), on_click=lambda e: start_review_flow()),
                                ])
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        bgcolor=BG_CARD,
                        height=52,
                        padding=ft.padding.symmetric(horizontal=16),
                        border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR))
                    ),
                    # 滚动展示生词卡片
                    ft.Container(
                        content=notebook_list_container,
                        expand=True
                    )
                ],
                spacing=0
            ),
            expand=True,
            visible=False 
        )

        # 首次渲染生词列表
        render_notebook_list()

        # =====================================================================
        # 📱 底部公共 Tab Bar 导航监听
        # =====================================================================
        def switch_tab(e):
            nonlocal current_tab
            hide_sheet()
            close_review_flow()
            if e.control.selected_index == 0:
                tab_read.visible = True
                tab_notebook.visible = False
                current_tab = "read"
            else:
                tab_read.visible = False
                tab_notebook.visible = True
                current_tab = "notebook"
                render_notebook_list()
            page.update()

        # 原生 iOS 常驻底栏 NavigationBar 控件
        nav_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationDestination(icon="book", label="阅读语音"),
                ft.NavigationDestination(icon="folder_special", label="我的生词"),
            ],
            on_change=switch_tab,
            height=65,
            bgcolor=BG_CARD,
        )

        # =====================================================================
        # 📱 页面整体挂载
        # =====================================================================
        # 用 Stack 叠层将 Bottom Sheet 和 Review Overlay 盖在最顶层
        main_layout = ft.Stack(
            controls=[
                ft.Column([
                    debug_console, # 💥 顶置常驻实时调试大看板 (只在开发调试阶段出现，出厂一键关闭)
                    ft.Container(content=tab_read, expand=True),
                    ft.Container(content=tab_notebook, expand=True),
                    nav_bar
                ], spacing=0, expand=True),
                bottom_sheet,     
                review_overlay    
            ],
            expand=True
        )

        page.add(main_layout)
        log_debug("[SUCCESS] 界面组装完美就绪！")

    except Exception as ex:
        # 💥 极客首屏冷启动安全盾
        import traceback
        err_str = traceback.format_exc()
        
        # 清空页面，强制显示报错看板
        page.controls.clear()
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Text("❌ OmniReader 启动异常反馈", size=20, weight="bold", color="#FF3B30"),
                    ft.Text("为了帮您 100% 极速消除白屏闪退，系统已为您自动抓取并高亮渲染了安卓底层的真实报错日志调用栈，请将此日志拍照或复制发送给我：", size=12, color=TEXT_SUB),
                    ft.Container(
                        content=ft.Text(err_str, size=11, font_family="monospace", color="#1C1C1E", selectable=True),
                        bgcolor="#FFF5F5",
                        border=ft.border.all(1, "#FEB2B2"),
                        padding=15,
                        border_radius=12,
                        expand=True
                    ),
                    ft.FilledButton(
                        content=ft.Text("✕ 关闭应用", color="#ffffff"),
                        bgcolor="#FF3B30",
                        height=40,
                        on_click=lambda e: page.window_close()
                    )
                ], spacing=12),
                padding=20,
                expand=True
            )
        )
        page.update()

if __name__ == "__main__":
    # 💥 极客秒开自愈：强制使用 WEB_BROWSER 视图
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)
