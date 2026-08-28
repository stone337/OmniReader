import sys
import traceback
import flet as ft

# 💥 终极硬核最前端防线：在“导包加载期”部署安全显形盾！
# 即使是 edge-tts 或 aiohttp 在安卓端导入发生任何 ImportError，也 1 毫秒直接在屏幕上把日志打出来，拒绝任何白屏！
try:
    import mobile_app
    err_msg = None
except Exception as ex:
    err_msg = traceback.format_exc()

if err_msg:
    def err_app(page: ft.Page):
        page.title = "❌ App 导包阶段致命异常"
        page.bgcolor = "#F2F2F7"
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Text("❌ App 导包加载期致命崩溃", size=18, weight="bold", color="#FF3B30"),
                    ft.Text("这代表在最底层的 Python 模块载入阶段（Imports）发生了解析错误，错误调用栈如下，请将此日志截图发我，我们 1 秒锁定元凶：", size=11, color="#8E8E93"),
                    ft.Container(
                        content=ft.Text(err_msg, size=10, font_family="monospace", color="#1C1C1E", selectable=True),
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
    
    # 拉起原生报错看板并优雅退出
    ft.app(target=err_app)
else:
    # 💥 100% 导入无误，顺畅流入手机端主业务系统！
    if __name__ == "__main__":
        ft.app(target=mobile_app.main)
