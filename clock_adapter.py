import requests
from typing import Optional


class ClockAdapter:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def now(self) -> int:
        r = requests.get(f"{self.base}/time")
        r.raise_for_status()
        return r.json()["current_time"]

    def tick(self):
        r = requests.post(f"{self.base}/tick")
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    url = " http://127.0.0.1:8000"
    clock = ClockAdapter(base_url=url)
    print(clock.now())
    print(clock.tick())
    print(clock.now())
