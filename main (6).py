import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from handler import router as voice_router
from stripe_handler import router as payment_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Restaurant Voice AI",
    description="AI-powered voice ordering system for restaurants",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)
app.include_router(payment_router)


@app.get("/")
async def root():
    return {"service": "Restaurant Voice AI", "status": "online"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
