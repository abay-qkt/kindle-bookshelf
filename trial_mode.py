import time
import sys
from threading import Thread

class TrialManager:
    def __init__(self, enabled=False, limit_minutes=10):
        self.enabled = enabled
        self.limit_minutes = limit_minutes
        if self.enabled:
            self._start_time = time.time()
            self._thread = Thread(target=self._watch)
            self._thread.daemon = True
            self._thread.start()

    def _watch(self):
        while True:
            if time.time() - self._start_time > self.limit_minutes * 60:
                print("試用時間が終了しました。アプリを終了します。")
                sys.exit()
            time.sleep(1)
