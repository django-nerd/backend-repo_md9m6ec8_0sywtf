import os
import json
import time
import random
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Generator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI(title="Hyper Trading Automation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        from database import db  # type: ignore

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = getattr(db, "name", "✅ Connected")
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:  # noqa: BLE001
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:  # noqa: BLE001
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


def sign_payload(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def market_stream(symbol: str = "BTC-USD") -> Generator[str, None, None]:
    secret = os.getenv("SIGNING_SECRET", "demo-secret")
    base_price = 68000.0
    last_close = base_price
    latency_ms = 50

    while True:
        # simulate latency and jitter
        jitter = random.randint(-20, 20)
        latency_ms = max(20, min(250, latency_ms + jitter))

        # simulate ohlc bar (1s)
        open_price = last_close
        high = open_price * (1 + random.uniform(0.0001, 0.0015))
        low = open_price * (1 - random.uniform(0.0001, 0.0015))
        close = random.uniform(low, high)
        last_close = close

        now = datetime.now(timezone.utc).isoformat()
        data = {
            "ts": now,
            "symbol": symbol,
            "latency_ms": latency_ms,
            "venue_count": 18,
            "control_checks": 42,
            "bar": {
                "t": int(time.time()),
                "o": round(open_price, 2),
                "h": round(high, 2),
                "l": round(low, 2),
                "c": round(close, 2),
            },
        }
        payload = json.dumps(data)
        sig = sign_payload(secret, payload)
        event = f"data: {json.dumps({"payload": data, "sig": sig})}\n\n"
        yield event
        time.sleep(1)


@app.get("/sse/market")
async def sse_market(request: Request, symbol: str = "BTC-USD"):
    async def event_generator():
        for event in market_stream(symbol):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
def health():
    return JSONResponse({
        "status": "ok",
        "latency_p95_ms": 150,
        "integrations": 18,
        "control_checks": 42,
    })


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
