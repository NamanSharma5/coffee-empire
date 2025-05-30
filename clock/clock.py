from typing import Callable, List, Optional
import threading
import time
from enum import Enum

class ClockMode(Enum):
    MANUAL = "manual"
    AUTO = "auto"

class SimulationClock:
    def __init__(self, start_time: int = 0):
        self._time = start_time
        self._subscribers: List[Callable[[int], None]] = []
        self._mode = ClockMode.MANUAL
        self._auto_thread: Optional[threading.Thread] = None
        self._auto_interval = 1.0  # seconds
        self._auto_delta = 1  # time units per tick
        self._running = False
        
    def now(self) -> int:
        """Pull primitive - get current simulation time"""
        return self._time
    
    def advance(self, to_time: int) -> None:
        """Advance to specific time"""
        if to_time <= self._time:
            raise ValueError(f"Cannot advance to {to_time}, current time is {self._time}")
        old_time = self._time
        self._time = to_time
        self._notify_subscribers(old_time, self._time)
    
    def tick(self, delta: Optional[int] = 1) -> Optional[RuntimeError]:
        """Advance by delta time units"""
        self.advance(self._time + delta)
    
    def subscribe(self, callback: Callable[[int], None]) -> None:
        """Subscribe to time updates"""
        if callback not in self._subscribers:
            self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[int], None]) -> None:
        """Unsubscribe from time updates"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    def reset(self, time: int = 0) -> None:
        """Reset clock - useful for server endpoints"""
        self.stop_auto()
        old_time = self._time
        self._time = time
        self._notify_subscribers(old_time, self._time)
    
    def start_auto(self, interval_seconds: float = 1.0, delta: int = 1) -> None:
        """Start auto-advancing the clock"""
        if self._running:
            return
        
        self._auto_interval = interval_seconds
        self._auto_delta = delta
        self._running = True
        self._mode = ClockMode.AUTO
        
        def _auto_advance():
            while self._running:
                time.sleep(self._auto_interval)
                if self._running:  # Check again after sleep
                    self.tick(self._auto_delta)
        
        self._auto_thread = threading.Thread(target=_auto_advance, daemon=True)
        self._auto_thread.start()
    
    def stop_auto(self) -> None:
        """Stop auto-advancing"""
        self._running = False
        self._mode = ClockMode.MANUAL
        if self._auto_thread:
            self._auto_thread.join(timeout=2.0)
    
    def get_status(self) -> dict:
        """Get clock status - useful for server endpoints"""
        return {
            "current_time": self._time,
            "mode": self._mode.value,
            "running": self._running,
            "subscribers": len(self._subscribers),
            "auto_interval": self._auto_interval if self._mode == ClockMode.AUTO else None
        }
    
    def _notify_subscribers(self, old_time: int, new_time: int) -> None:
        """Notify subscribers with error handling"""
        failed_callbacks = []
        for callback in self._subscribers:
            try:
                callback(new_time)
            except Exception as e:
                print(f"Subscriber callback failed: {e}")
                failed_callbacks.append(callback)
        
        # Remove failed callbacks to prevent repeated errors
        for failed_cb in failed_callbacks:
            self.unsubscribe(failed_cb)