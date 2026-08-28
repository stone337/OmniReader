import flet as ft
import traceback
import sys
import time

def main(page: ft.Page):
    page.title = "📱 OmniReader 渐进式启动器"
    page.bgcolor = "#F2F2F7"
    
    # 顶部 iOS 大标题
    header = ft.Container(
        content=ft.Text("📖 OmniReader 移动研习端", size=18, weight="bold", color="#1C1C1E"),
        padding=ft.padding.only(bottom=20)
    )
    
    # 动态加载进度文字
    status_text = ft.Text("⏳ 正在初始化手机 Python 解释器...", size=13, color="#8E8E93")
    
    # 进度条
    progress_bar = ft.ProgressBar(width=320, color="#007AFF", bgcolor="#E5E5EA")
    
    page.add(
        ft.Container(
            content=ft.Column([
                header,
                status_text,
                progress_bar,
                ft.Container(height=20),
                ft.Text("💡 提示：天眼加载器正在逐步校验 SQLite 和 TTS 底层环境，如果发生任何兼容性错误，下方将一瞬间打出精准的 Traceback 排错日记，拒绝一切白屏闪退！", size=10, color="#8E8E93")
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            padding=30,
            expand=True
        )
    )
    page.update()

    def show_error(title, details):
        page.controls.clear()
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Text(f"❌ {title}", size=18, weight="bold", color="#FF3B30"),
                    ft.Text("我们在渐进式加载期间为您成功抓取到了底层的真实报错，请将此日志拍照/复制发送给我，我们 1 秒物理消杀：", size=11, color="#8E8E93"),
                    ft.Container(
                        content=ft.Text(details, size=10, font_family="monospace", color="#1C1C1E", selectable=True),
                        bgcolor="#FFF5F5",
                        border=ft.border.all(1, "#FEB2B2"),
                        padding=12,
                        border_radius=10,
                        expand=True
                    ),
                    ft.FilledButton(
                        content=ft.Text("✕ 关闭应用", color="#ffffff"),
                        bgcolor="#FF3B30",
                        height=36,
                        on_click=lambda e: page.window_close()
                    )
                ], spacing=10),
                padding=20,
                expand=True
            )
        )
        page.update()

    # ==================== Step 1: 测试导入 SQLite 数据库中枢 ====================
    try:
        status_text.value = "⏳ Step 1/3: 正在测试加载 SQLite 数据库中枢 (english_db)..."
        page.update()
        time.sleep(0.1) # 给界面渲染的时间
        
        from english_db import DatabaseManager
        status_text.value = "✅ Step 1/3 成功！已成功加载 DatabaseManager 模块。"
        page.update()
    except Exception as ex:
        show_error("Step 1 数据库加载失败", traceback.format_exc())
        return

    # ==================== Step 2: 测试导入 Mock 原生发音中枢 ====================
    try:
        status_text.value = "⏳ Step 2/3: 正在测试加载 Mock 原生发音中枢 (mobile_tts)..."
        page.update()
        time.sleep(0.1)
        
        from mobile_tts import MobileTTSEngine
        status_text.value = "✅ Step 2/3 成功！已成功加载 MobileTTSEngine 模块。"
        page.update()
    except Exception as ex:
        show_error("Step 2 发音中枢加载失败", traceback.format_exc())
        return

    # ==================== Step 3: 测试导入手机主业务程序 ====================
    try:
        status_text.value = "⏳ Step 3/3: 正在测试加载手机主业务程序 (mobile_app)..."
        page.update()
        time.sleep(0.1)
        
        import mobile_app
        status_text.value = "🎉 恭喜！手机端所有底层中枢 100% 完美通过校验！"
        page.update()
        time.sleep(0.2)
    except Exception as ex:
        show_error("Step 3 主程序加载失败", traceback.format_exc())
        return

    # ==================== 100% 全绿成功：顺畅流入手机端主业务系统 ====================
    try:
        # 清除加载条，唤醒最惊艳、最奢华的手机主界面
        page.controls.clear()
        mobile_app.main(page)
    except Exception as ex:
        show_error("主界面渲染崩溃", traceback.format_exc())

if __name__ == "__main__":
    ft.app(target=main)
