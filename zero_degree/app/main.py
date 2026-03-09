import os, asyncio
from fastapi import Depends, Depends, FastAPI, Request
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import HTMLResponse, RedirectResponse
from app.helpers import require_contract
from app.settings import settings
from app.routes import merchants
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.core.blockchain import init_blockchain, close_blockchain
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    
    await init_blockchain(app)
     
    yield
    
    # SHUTDOWN
    close_blockchain(app)


app = FastAPI(lifespan=lifespan, debug=settings.debug)
if os.path.exists("static"):
    app.mount("/ui", StaticFiles(directory="static"), name="static")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print("Validation error:", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )
    
@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    import traceback
    error_html = f"""
    <h1>500 Error</h1>
    <pre>{traceback.format_exc()}</pre>
    """
    return HTMLResponse(content=error_html, status_code=500)



# Set up Jinja2 templates for any server-rendered pages
templates = Jinja2Templates(directory="app/templates")

# Include your mission routes
app.include_router(merchants.router, prefix="/merchants")


# Basic route to serve the homepage, other pages will be handld in their routes with HTMX then FastAPI later)
@app.get("/")
def index(request: Request):
    return RedirectResponse(url="/merchants/")

@app.get("/health")
async def health():
    return {"status": "ok", "network": settings.network_string}

# Usage in routes:
@app.get("/snow/status")
async def snow_status(snowgate=Depends(require_contract("snowgate"))):
    return {"active": snowgate.is_active()}