# compat shim — real file is subsystems/mirror/scrcpy_server.py
import runpy, os, sys
if __name__ == '__main__':
    runpy.run_path(os.path.join(os.path.dirname(__file__),
        'subsystems', 'mirror', 'scrcpy_server.py'), run_name='__main__')
