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
from app.workers.sync_worker import agent_fulfillment_worker
from ape import Contract, networks

SHOPS_INIT = open("deployed_shops.txt", "w")    # Init File

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("📡 Initializing Zero Degree Registry Listeners...")
    
    tasks = []
    
    # Use 'a+' or check existence to prevent FileNotFoundError
    if os.path.exists("deployed_shops.txt"):
        with open("deployed_shops.txt", "r") as f:
            # 1. Read ONCE
            raw_content = f.read().strip() 
            
            # 2. Check the variable, not the file stream again
            if raw_content:
                address = raw_content
                print(f"✅ Found Shop Address: {address}")
                
                with networks.parse_network_choice(settings.network_string):
                    shop_contract = Contract(address)
                    
                    # 3. Create the task and ADD IT TO THE LIST
                    # If you don't append it to 'tasks', the shutdown logic can't stop it
                    task = asyncio.create_task(
                        agent_fulfillment_worker(address, shop_contract.created_at_block())
                    )
                    tasks.append(task)
            else:
                print("⚠️ deployed_shops.txt is empty.")

    yield  # --- APP IS RUNNING ---

    print("🛑 Saving sync state and shutting down...")
    for task in tasks:
        task.cancel()
    
    print("✅ All listeners stopped.")




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

