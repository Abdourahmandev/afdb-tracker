"""
function_app.py — Azure Functions v2 entry point.

Wraps the FastAPI app as an ASGI Azure Function.
All routes defined in api/main.py are exposed under /api/*.

Local dev (no Azure Functions runtime needed):
    uvicorn api.main:app --reload --port 7071
    Then: GET http://localhost:7071/api/health

Azure Functions local dev:
    func start
    Then: GET http://localhost:7071/api/health
"""
import azure.functions as func
from api.main import app as fastapi_app

# Expose all FastAPI routes as a single Azure Function HTTP trigger
app = func.AsgiFunctionApp(
    app=fastapi_app,
    http_auth_level=func.AuthLevel.ANONYMOUS,  # Auth handled by FastAPI middleware
)
