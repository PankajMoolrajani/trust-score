"""
Simple scheduler for running periodic tasks.
For prod, swap this for APScheduler or Celery beat.
"""

import logging
import signal
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self._tasks = {}
        self._running = False
    
    def add(self, name, fn, interval_sec, immediate=False):
        self._tasks[name] = {
            "fn": fn,
            "interval": interval_sec,
            "last": None if immediate else datetime.utcnow(),
        }
        log.info(f"task added: {name} every {interval_sec}s")
    
    def remove(self, name):
        self._tasks.pop(name, None)
    
    def _due(self, task):
        if task["last"] is None:
            return True
        return (datetime.utcnow() - task["last"]).total_seconds() >= task["interval"]
    
    def _exec(self, name, task):
        try:
            log.info(f"running: {name}")
            result = task["fn"]()
            task["last"] = datetime.utcnow()
            log.info(f"done: {name} -> {result}")
        except Exception as e:
            log.error(f"failed: {name} - {e}", exc_info=True)
    
    def run(self, tick=1.0):
        self._running = True
        log.info("scheduler started")
        
        def stop(sig, frame):
            log.info("stopping...")
            self._running = False
        
        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        
        while self._running:
            for name, task in self._tasks.items():
                if self._due(task):
                    self._exec(name, task)
            time.sleep(tick)
        
        log.info("scheduler stopped")
    
    def stop(self):
        self._running = False


def main():
    from src.pylibs import EventProcessor
    from src.cronjob.tasks import Tasks
    
    processor = EventProcessor()
    tasks = Tasks(processor)
    
    sched = Scheduler()
    sched.add("overdue", tasks.run_overdue_check, 3600, immediate=True)  # hourly
    sched.add("validation", tasks.run_validation, 86400)  # daily
    sched.add("cleanup", lambda: tasks.run_cleanup(90), 604800)  # weekly
    sched.add("report", tasks.run_daily_report, 86400, immediate=True)
    
    log.info("starting scheduler...")
    sched.run()


if __name__ == "__main__":
    main()
