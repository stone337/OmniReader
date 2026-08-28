import flet as ft
import mobile_app

# 💥 手机原生入口中枢：
# 避开电脑网页版的 WEB_BROWSER 模式，强制在安卓手机中启动 100% 纯原生 Flutter 视窗！
if __name__ == "__main__":
    ft.app(target=mobile_app.main)
