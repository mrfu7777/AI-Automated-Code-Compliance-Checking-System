from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware


def create_application() -> FastAPI:
    settings = get_settings()
    if settings.app_env == "production":
        if settings.demo_mode_enabled:
            raise RuntimeError("Production requires DEMO_MODE_ENABLED=false")
        if settings.auth_mode != "api_key":
            raise RuntimeError("Production requires AUTH_MODE=api_key")
        if (
            len(settings.bootstrap_api_key) < 32
            or len(settings.api_key_pepper) < 32
            or settings.api_key_pepper.startswith("change-me")
        ):
            raise RuntimeError("Production API key secrets must be configured")
    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "Evidence-backed API foundation for automated building code compliance review."
        ),
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(v1_router, prefix=settings.api_v1_prefix)
    register_error_handlers(application)
    return application


app = create_application()
