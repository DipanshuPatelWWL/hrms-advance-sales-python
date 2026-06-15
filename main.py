from fastapi import FastAPI, Request, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader, APIKey
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
import sys
import traceback
from starlette.status import HTTP_403_FORBIDDEN

# Force UTF-8 encoding for console output to handle emojis and international characters
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Load .env from the same directory as this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

from utils.db import close_db
from routers import leads, scoring, email_gen, website, proposal

# ── API KEY SECURITY ─────────────────────────────────────────────────────────
API_KEY = os.getenv("PYTHON_ENGINE_API_KEY", "dev-secret-key-12345")
print("=== PYTHON AUTH ===")
print("ENV KEY EXISTS:", bool(os.getenv("PYTHON_ENGINE_API_KEY")))
print("API KEY PREFIX:", API_KEY[:6] if API_KEY else "NONE")
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(header_key: str = Security(api_key_header)):
    if header_key == API_KEY:
        print("✅ AUTH SUCCESS")
        return header_key

    print("❌ AUTH FAILED")
    print("Received Key:", header_key)
    print("Expected Key:", API_KEY)

    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN,
        detail="Could not validate credentials"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # No blocking I/O here — the MongoDB client is initialised lazily on
    # first use so the app is ready to accept requests immediately.
    yield
    await close_db()

app = FastAPI(
    title="Sales Intelligence Engine",
    lifespan=lifespan,
)

# Exception handler must be registered AFTER app is created
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"--- [GLOBAL CRASH] ---\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__}
    )

# Restrict CORS to approved domains
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5000,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    """Public health check for monitoring/load balancers"""
    return {"status": "ok"}

# Protected API Routes
api_deps = [Depends(get_api_key)] if os.getenv("NODE_ENV") != "test" else []

app.include_router(leads.router,     prefix="/api", tags=["Lead Finder"], dependencies=api_deps)
app.include_router(scoring.router,   prefix="/api", tags=["Lead Scoring"], dependencies=api_deps)
app.include_router(email_gen.router, prefix="/api", tags=["Email Generator"], dependencies=api_deps)
app.include_router(website.router,   prefix="/api", tags=["Website Analyzer"], dependencies=api_deps)
app.include_router(proposal.router,  prefix="/api", tags=["Proposal Generator"], dependencies=api_deps)
