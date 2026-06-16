"""Scout backend — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import legal, lists, reviews, spots, users
from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.firebase import init_firebase


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Firebase on startup."""
    init_firebase()
    yield


app = FastAPI(
    title="Scout API",
    description="Photo spot discovery backend",
    version="0.1.0",
    lifespan=lifespan,
)

# --- CORS ---
# iOS doesn't care about CORS. This is for the eventual web client and /docs Swagger UI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,  # wildcard origin requires credentials=False
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception handlers ---


@app.exception_handler(DomainError)
async def domain_error_handler(req, exc: DomainError):
    """Consistent {detail, code} JSON for all domain errors."""
    content = {"detail": exc.detail, "code": exc.code}
    if exc.payload:
        content.update(exc.payload)
    return JSONResponse(content, status_code=exc.status, headers=exc.headers or None)


@app.exception_handler(RequestValidationError)
async def validation_handler(req, exc: RequestValidationError):
    """Override FastAPI's default 422 → 400 with our error shape."""
    return JSONResponse(
        {
            "detail": "Invalid request",
            "code": "INVALID_ENUM_VALUE",
            "errors": exc.errors(),
        },
        status_code=400,
    )


# --- Health check ---


@app.get("/")
def root():
    return {"status": "Scout backend is running 🚀"}


@app.get("/health")
async def health():
    """Liveness probe for Cloud Run."""
    return {"status": "ok", "env": settings.ENV}


# --- Routers ---
app.include_router(spots.router)
app.include_router(reviews.router)
app.include_router(users.router)
app.include_router(lists.router)
app.include_router(legal.router)
