"""ad-cli entry point — delegates to src/main.py"""
import os
import sys

def main():
    # 把 src/ 加入 path，让所有 import 找到正确模块
    _src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _src not in sys.path:
        sys.path.insert(0, _src)
    from main import main as _main
    _main()

if __name__ == "__main__":
    main()
