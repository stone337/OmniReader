import os
import time
import tempfile
import uuid
import threading
import re
import flet as ft

def filter_english_only(text):
    if not text:
        return ""
    t = re.sub(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', '', text)
    return t.strip()

def clean_text_for_tts(text, is_online=True):
    if not text:
        return ""
    t = filter_english_only(text) if is_online else text
    t = re.sub(r'\([^)]*\)', '', t)
    t = re.sub(r'\[[^]]*\]', '', t)
    t = re.sub(r'\{[^}]*\}', '', t)
    t = re.sub(r'[-_/*\\=+#~^|`<>""“”\'’`‘’]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

class MobileTTSEngine:
    """📱 手机端 100% 纯 Python 安全 Mock 发音控制器 (无任何 C 扩展模块，免疫任何 Android 段错误！)"""
    def __init__(self, page: ft.Page):
        self.page = page
        self.active_voice = "en-GB-SoniaNeural"
        self.speed_ratio = 1.0
        self.is_online = False
        
        # 💥 使用 Flet 占位内置原生音频控件
        self.audio_player = ft.Audio(src="https://empty", autoplay=True)
        self.page.overlay.append(self.audio_player)
        self.page.update()

        self._play_thread = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()

        self.current_sentence_index = -1
        self.sentences = []
        self.current_session_id = None

    def set_voice(self, voice_name):
        self.active_voice = voice_name

    def set_speed(self, ratio):
        self.speed_ratio = ratio

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def stop(self):
        self._stop_event.set()
        self._pause_event.set()
        self.current_session_id = None

    def speak_text_list(self, sentences, start_idx=0, on_sentence_start=None, on_finish=None):
        """开始模拟播放一个句子列表（纯 Python，由后台线程连续推动并向控制台打日志）"""
        self.stop()
        
        if self._play_thread and self._play_thread.is_alive():
            try:
                self._play_thread.join(timeout=0.2)
            except:
                pass

        self.sentences = [s.strip() for s in sentences if s.strip()]
        if not self.sentences:
            if on_finish:
                on_finish()
            return

        self._stop_event.clear()
        self._pause_event.set()
        self.current_sentence_index = start_idx
        
        self.current_session_id = uuid.uuid4().hex
        active_sess = self.current_session_id

        self._play_thread = threading.Thread(
            target=self._mock_playback_loop,
            args=(active_sess, on_sentence_start, on_finish),
            daemon=True
        )
        self._play_thread.start()

    def _mock_playback_loop(self, session_id, on_sentence_start, on_finish):
        while not self._stop_event.is_set() and session_id == self.current_session_id and self.current_sentence_index < len(self.sentences):
            self._pause_event.wait()
            if self._stop_event.is_set() or session_id != self.current_session_id:
                break

            idx = self.current_sentence_index
            raw_text = self.sentences[idx]
            
            # 触发当前句子模拟开始
            if on_sentence_start:
                on_sentence_start(idx, raw_text)

            # 在手机控制台上显示模拟朗读进度
            try:
                # 动态获取 mobile_app 中定义的 log_debug 记录器
                import sys
                main_mod = sys.modules.get("mobile_app")
                if main_mod and hasattr(main_mod, "log_debug"):
                    # 调出系统的调试日志面板
                    getattr(main_mod, "log_debug")(f"🔊 [Mock 原声] 模拟朗读: {raw_text[:35]}...")
            except:
                pass

            # 模拟语音播放的时间跨度（1.5 秒 ~ 根据单词字数估算）
            words_cnt = len(raw_text.split(" "))
            duration_est = max(1.5, words_cnt * 0.4 / self.speed_ratio)
            
            step_ms = 0.1
            elapsed = 0
            while elapsed < duration_est and not self._stop_event.is_set() and session_id == self.current_session_id:
                if not self._pause_event.is_set():
                    time.sleep(0.1)
                    continue
                time.sleep(step_ms)
                elapsed += step_ms

            if self._stop_event.is_set() or session_id != self.current_session_id:
                break

            self.current_sentence_index += 1

        if on_finish:
            on_finish()
