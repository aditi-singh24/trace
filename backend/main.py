"""TRACE backend entry point (shared, rarely touched).

Run from the backend/ folder:  uvicorn main:app --reload
Disha adds her routers (module2_core, module3_reports) in the marked spot.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from module4_auth.router import router as auth_router
from module5_engine.router import router as engine_router
from shared.config import get_settings

app = FastAPI(title="TRACE Clinical Trial Management System", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return JSONResponse({"error": str(exc.detail), "code": exc.status_code},
                        status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    msg = f"{where}: {first.get('msg', 'invalid request')}" if where else first.get("msg", "invalid request")
    return JSONResponse({"error": msg, "code": 422}, status_code=422)


app.include_router(auth_router)      # Module 4
app.include_router(engine_router)    # Module 5
# --- Disha: include module2_core / module3_reports routers here ---
