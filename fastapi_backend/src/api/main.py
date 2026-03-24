from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.api.routes.auth import router as auth_router
from src.api.routes.tags import router as tags_router
from src.api.routes.tasks import router as tasks_router
from src.api.routes.realtime import router as realtime_router

openapi_tags = [
    {"name": "Health", "description": "Service health and basic diagnostics."},
    {"name": "Auth", "description": "User registration and JWT authentication."},
    {"name": "Tasks", "description": "Task CRUD + search/filter/sort + notes/attachments/reminders."},
    {"name": "Tags", "description": "Tag CRUD and task tagging support."},
    {"name": "Realtime", "description": "WebSocket endpoint and realtime usage help."},
]

app = FastAPI(
    title=settings.app_name,
    description=(
        "Unified Task Planner backend API.\n\n"
        "Notes:\n"
        "- DB connection URL is read from `DATABASE_URL` env var or from "
        "`postgresql_database/db_connection.txt` when the DB container starts.\n"
        "- Realtime events are available via WebSocket at `/ws`.\n"
    ),
    version=settings.app_version,
    openapi_tags=openapi_tags,
)

# CORS
allow_origins = [o.strip() for o in settings.cors_allow_origins.split(",")] if settings.cors_allow_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins if allow_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"], summary="Health Check", description="Simple health check endpoint.")
def health_check():
    return {"message": "Healthy"}


app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(tags_router)
app.include_router(realtime_router)
