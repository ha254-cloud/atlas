from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.events.handlers import register_all as register_event_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.observability.tracing import TracingMiddleware

register_event_handlers()

app = FastAPI(
    title="Atlas API",
    version="0.2.0",
    description="Healthcare claims recovery and denial management platform",
)

# Allow the Next.js frontend to call the API
origins = [
    "http://localhost:3000",
    "http://localhost:3001",  # Useful if Next.js switches ports during development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing middleware
app.add_middleware(TracingMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "application": "Atlas",
        "version": "0.2.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
