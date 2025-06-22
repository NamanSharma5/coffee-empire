import requests
from typing import Optional
import os

BEARER_TOKEN = os.environ.get("FOUNDRY_TOKEN")

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


class FoundryClockAdapter:
    def __init__(self):
        pass

    def now(self) -> int:
        url = "https://devcon.palantirfoundry.com/api/v2/ontologies/ontology-50dc5f2e-81e4-46b6-91a1-b2644e11da56/queries/currentTime/execute"
        headers = {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {}
        response = requests.post(url, headers=headers, json={"parameters": data})
        response.raise_for_status()
        result = response.json()
        return result["value"]


if __name__ == "__main__":
    # url = " http://127.0.0.1:8000"
    # clock = ClockAdapter(base_url=url)
    # print(clock.now())
    # print(clock.tick())
    # print(clock.now())

    clock = FoundryClockAdapter()
    print(clock.now())
