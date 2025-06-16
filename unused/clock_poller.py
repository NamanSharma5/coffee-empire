import threading
import time
from bus import Bus
from clock_adapter import ClockAdapter


class ClockPoller:
    def __init__(self, clock: ClockAdapter, bus: Bus, poll_interval: float = 1.0):
        self.clock = clock
        self.bus = bus
        self.poll_interval = poll_interval
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False
        self._last_time: Optional[int] = None

    def start(self):
        if not self._running:
            # initialize last_time
            status = self.clock.status()
            self._last_time = status["current_time"]
            self._running = True
            self._thread.start()

    def stop(self):
        self._running = False
        self._thread.join(timeout=2.0)

    def _run(self):
        while self._running:
            time.sleep(self.poll_interval)
            status = self.clock.status()
            t = status["current_time"]
            if self._last_time is None:
                self._last_time = t
            elif t > self._last_time:
                # emit one or more ticks
                for new_t in range(self._last_time + 1, t + 1):
                    self.bus.publish("time.tick", new_t)
                self._last_time = t
            # else: no change
