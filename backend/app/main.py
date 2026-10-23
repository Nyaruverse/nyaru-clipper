from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.db import init_db
from app.paths import ensure_data_dir
from app.settings import get_settings
from app.services.runtime_capabilities import get_runtime_capability_summary
from app.services.unified_database import DatabaseSafetyError

runtime_logger = logging.getLogger("app.runtime")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    (ensure_data_dir() / "tasks").mkdir(parents=True, exist_ok=True)
    init_db()
    runtime_summary = get_runtime_capability_summary()
    runtime_logger.info(
        json.dumps(
            {
                "event": "runtime_capabilities_startup",
                "profile": runtime_summary["detected_profile"],
                "status": runtime_summary["status"],
                "accelerator": runtime_summary["accelerator"],
                "warnings": runtime_summary["warnings"],
                "issue_codes": runtime_summary["issue_codes"],
            }
        )
    )
    yield


app = FastAPI(title="Bilibili VTuber Suite API", lifespan=lifespan)
from app.api.body_limit import OperationsBodyLimit
app.add_middleware(OperationsBodyLimit)


@app.exception_handler(DatabaseSafetyError)
def database_safety_error(_request: Request, error: DatabaseSafetyError) -> JSONResponse:
    return JSONResponse(status_code=503, content={'detail': str(error)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=settings.cors_allowed_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "service": "bilibili-vtuber-suite"}
