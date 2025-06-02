from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from clock import SimulationClock

app = FastAPI()
clock = SimulationClock(start_time=0)

class AdvanceRequest(BaseModel):
    to_time: int

class TickRequest(BaseModel):
    delta: int = 1

class ResetRequest(BaseModel):
    time: int = 0

class AutoRequest(BaseModel):
    interval_seconds: float = 1.0
    delta: int = 1

@app.get("/time")
def get_time():
    return {"current_time": clock.now()}

@app.post("/advance")
def advance(req: AdvanceRequest):
    try:
        clock.advance(req.to_time)
        return {"current_time": clock.now()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/tick")
def tick(req: TickRequest = None):
    try:
        delta = req.delta if req is not None else 1
        clock.tick(delta)
        return {"current_time": clock.now()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/reset")
def reset(req: ResetRequest):
    clock.reset(req.time)
    return {"current_time": clock.now()}

@app.post("/start_auto")
def start_auto(req: AutoRequest):
    clock.start_auto(interval_seconds=req.interval_seconds, delta=req.delta)
    return {"status": "auto started", "interval_seconds": req.interval_seconds, "delta": req.delta}

@app.post("/stop_auto")
def stop_auto():
    clock.stop_auto()
    return {"status": "auto stopped"}

@app.get("/status")
def status():
    return clock.get_status()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)