"""PyInstaller 启动入口。"""

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    from app.main import serve

    serve()
