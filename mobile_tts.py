import os
import time
import tempfile
import uuid
import threading
import asyncio
import edge_tts
import re
import flet as ft

def filter_english_only(text):
    """过滤掉文本中的所有中文字符与中文特殊标点，仅保留英文、数字、空格及正常英文断句标点。"""
    if not text:
        return ""
    t = re.sub(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', '', text)
    return t.strip()

def clean_text_for_tts(text, is_online=True):
    """清理英文文本中的特殊符号与噪点，防止 Edge-TTS 读出标点符号"""
    if not text:
        return ""
    if is_online:
        t = filter_english_only(text)
    else:
        t = text
        
    t = re.sub(r'\([^)]*\)', '', t)
    t = re.sub(r'\[[^]]*\]', '', t)
    t = re.sub(r'\{[^}]*\}', '', t)
    t = re.sub(r'[-_/*\\=+#~^|`<>""“”\'’`‘’]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

class MobileTTSEngine:
    """📱 手机端原生 Flet 音频发音控制中心 (Edge-TTS 在线双缓冲 + 手机原生 MediaPlayer)"""
    def __init__(self, page: ft.Page):
        self.page = page
        self.active_voice = "en-GB-SoniaNeural"  # 默认优雅英音女声
        self.speed_ratio = 1.0  # 默认 1.0x 语速
        self.is_online = True
        
        # 💥 核心：使用 Flet 原生音频播放控件（底层由 Android MediaPlayer 提供 100% 极速并发支持）
        # 传入非空占位符 https://empty，100% 完美绕过 Android 底层对空字符串音频源的安全校验，绝不红屏！
        self.audio_player = ft.Audio(src="https://empty", autoplay=True)
        # 将音频控件挂载在页面最顶层 Overlay
        self.page.overlay.append(self.audio_player)
        self.page.update()

        self._play_thread = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()

        self.current_sentence_index = -1
        self.sentences = []
        self.current_session_id = None
        
        self.buffer_lock = threading.Lock()
        self.audio_buffer = {}

    def set_voice(self, voice_name):
        self.active_voice = voice_name

    def set_speed(self, ratio):
        self.speed_ratio = ratio

    def pause(self):
        self._pause_event.clear()
        self.audio_player.pause()

    def resume(self):
        self._pause_event.set()
        self.audio_player.resume()

    def stop(self):
        self._stop_event.set()
        self._pause_event.set()
        self.current_session_id = None
        try:
            self.audio_player.pause()
        except:
            pass

    def speak_text_list(self, sentences, start_idx=0, on_sentence_start=None, on_finish=None):
        """开始播放一个句子列表。由后台线程连续推动"""
        self.stop()
        
        if self._play_thread and self._play_thread.is_alive():
            try:
                self._play_thread.join(timeout=0.3)
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
        
        with self.buffer_lock:
            self.audio_buffer.clear()

        self._play_thread = threading.Thread(
            target=self._playback_loop,
            args=(active_sess, on_sentence_start, on_finish),
            daemon=True
        )
        self._play_thread.start()

    def _playback_loop(self, session_id, on_sentence_start, on_finish):
        temp_dir = tempfile.gettempdir()
        
        # 启动后台预加载下载线程
        preload_thread = threading.Thread(
            target=self._preload_buffer_worker,
            args=(session_id, temp_dir),
            daemon=True
        )
        preload_thread.start()

        while not self._stop_event.is_set() and session_id == self.current_session_id and self.current_sentence_index < len(self.sentences):
            self._pause_event.wait()
            if self._stop_event.is_set() or session_id != self.current_session_id:
                break

            idx = self.current_sentence_index
            raw_text = self.sentences[idx]
            
            is_zh_voice = self.active_voice.startswith("zh-CN")
            has_zh = any('\u4e00' <= c <= '\u9fff' for c in raw_text)
            
            # 检测纯中文
            text_for_online = clean_text_for_tts(raw_text, is_online=True) if (not is_zh_voice and self.is_online) else raw_text
            if not is_zh_voice and has_zh and not text_for_online:
                # 纯中文且用英文声线在手机上，由于离线 SAPI5 不存在，我们静默跳过此纯中文句
                self.current_sentence_index += 1
                continue

            if not is_zh_voice and has_zh and not text_for_online and self.is_online:
                text = raw_text
            else:
                text = clean_text_for_tts(raw_text, is_online=(not is_zh_voice and self.is_online))
                
            if not text:
                self.current_sentence_index += 1
                continue

            # 触发当前句子开始的回调
            if on_sentence_start:
                on_sentence_start(idx, raw_text)

            # 获取预载好的 MP3 音频路径
            mp3_path = None
            for _ in range(100):  # 最多等 10 秒
                if self._stop_event.is_set() or session_id != self.current_session_id:
                    break
                with self.buffer_lock:
                    if idx in self.audio_buffer and self.audio_buffer[idx] is not None:
                        mp3_path = self.audio_buffer[idx]
                        break
                time.sleep(0.1)

            if self._stop_event.is_set() or session_id != self.current_session_id or not mp3_path or mp3_path == "FAILED":
                self.current_sentence_index += 1
                continue

            # 💥 Flet 原生音频播放逻辑，完美的毫秒级暂停自愈
            try:
                self.audio_player.src = mp3_path
                self.page.update()
                
                has_started = False
                if self._pause_event.is_set():
                    self.audio_player.play()
                    has_started = True

                # 简单延时等待音频播放完，或者用户按下了暂停/停止
                # 手机端可以通过估算句子字数的时间，实现 100% 极速流式切句
                words_cnt = len(text.split(" ")) if not is_zh_voice else len(text)
                duration_est = max(1.5, words_cnt * 0.45 / self.speed_ratio) # 估算时长
                
                step_ms = 0.1
                elapsed = 0
                while elapsed < duration_est and not self._stop_event.is_set() and session_id == self.current_session_id:
                    if not self._pause_event.is_set():
                        self.audio_player.pause()
                        time.sleep(0.1)
                        continue
                    else:
                        if not has_started:
                            self.audio_player.play()
                            has_started = True
                        else:
                            self.audio_player.resume()
                    
                    time.sleep(step_ms)
                    elapsed += step_ms
            except Exception as e:
                print(f"[手机版原生播放报错] {e}")

            if self._stop_event.is_set() or session_id != self.current_session_id:
                break

            self.current_sentence_index += 1

        if on_finish:
            on_finish()

    def _preload_buffer_worker(self, session_id, temp_dir):
        """手机后台多线程静默预下载 Edge-TTS 语音包到手机沙盒中"""
        async def dl_worker(idx, text, voice, rate_str, out_path):
            try:
                communicate = edge_tts.Communicate(text, voice, rate=rate_str)
                await communicate.save(out_path)
                with self.buffer_lock:
                    self.audio_buffer[idx] = out_path
            except Exception as ex:
                print(f"[手机版 Edge-TTS 异步下载报错] 句子 {idx}: {ex}")
                with self.buffer_lock:
                    self.audio_buffer[idx] = "FAILED"

        rate_val = int((self.speed_ratio - 1.0) * 100)
        rate_str = f"{'+' if rate_val >= 0 else ''}{rate_val}%"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        buffer_depth = 3

        while not self._stop_event.is_set() and session_id == self.current_session_id:
            curr_idx = self.current_sentence_index
            if curr_idx < 0:
                time.sleep(0.1)
                continue

            tasks = []
            for i in range(curr_idx, min(curr_idx + buffer_depth, len(self.sentences))):
                if self._stop_event.is_set() or session_id != self.current_session_id:
                    break
                
                with self.buffer_lock:
                    is_cached = i in self.audio_buffer

                if not is_cached:
                    out_mp3 = os.path.join(temp_dir, f"m_tts_{uuid.uuid4().hex[:12]}_{i}.mp3")
                    with self.buffer_lock:
                        self.audio_buffer[i] = None
                    
                    target_voice = self.active_voice
                    txt_to_check = self.sentences[i]
                    has_zh = any('\u4e00' <= c <= '\u9fff' for c in txt_to_check)
                    is_zh_voice = target_voice.startswith("zh-CN")
                    
                    if not is_zh_voice and has_zh and not clean_text_for_tts(txt_to_check, is_online=True):
                        # 纯中文在英文声线下，直接设为 FAILED，手机端不发声
                        with self.buffer_lock:
                            self.audio_buffer[i] = "FAILED"
                        continue

                    # 统一分配声线：如果是中文声线，保留中文；如果是英文声线，过滤掉中文
                    if not is_zh_voice and has_zh and self.is_online:
                        target_voice = "zh-CN-XiaoxiaoNeural"
                        clean_txt = clean_text_for_tts(txt_to_check, is_online=False)
                    else:
                        clean_txt = clean_text_for_tts(txt_to_check, is_online=(not is_zh_voice))
                    
                    if not clean_txt:
                        with self.buffer_lock:
                            self.audio_buffer[i] = "FAILED"
                        continue

                    tasks.append(dl_worker(i, clean_txt, target_voice, rate_str, out_mp3))

            if tasks and not self._stop_event.is_set() and session_id == self.current_session_id:
                try:
                    loop.run_until_complete(asyncio.gather(*tasks))
                except:
                    pass

            time.sleep(0.2)
        
        loop.close()
