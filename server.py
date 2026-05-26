import os
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from BACKEND.config.db import connect_db, get_db
from BACKEND.routes.auth import router as auth_router
from BACKEND.routes.posts import router as posts_router
from BACKEND.routes.users import router as users_router
from BACKEND.routes.chat import router as chat_router
from BACKEND.socket_handler import sio

import socketio

# Log environment check
mongo_uri = os.getenv("MONGO_URI", "")
masked_uri = mongo_uri[:25] + "..." if mongo_uri else "NOT SET"
print(f"[i] MONGO_URI is: {'SET (' + masked_uri + ')' if mongo_uri else 'NOT SET'}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB
    await connect_db()
    yield

app = FastAPI(lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers to match Node.js JSON error output style
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "message" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"message": str(exc.detail)})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"message": f"Validation error: {exc.errors()}"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": str(exc)}
    )

# Health Check Route
@app.get("/api/health")
async def health_check():
    db = get_db()
    db_state = "disconnected"
    if db is not None:
        try:
            await db.command("ping")
            db_state = "connected"
        except Exception:
            db_state = "disconnected"
            
    return {
        "server": "running",
        "database": db_state,
        "mongoUri": "set" if os.getenv("MONGO_URI") else "NOT SET",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    }

# Serve root path explicitly
@app.get("/")
async def read_root():
    return FileResponse(os.path.join("FRONTEND", "index.html"))

# Mount API Routers
app.include_router(auth_router, prefix="/api/auth")
app.include_router(posts_router, prefix="/api/posts")
app.include_router(users_router, prefix="/api/users")
app.include_router(chat_router, prefix="/api/chat")

# Mount Uploads directory
app.mount("/uploads", StaticFiles(directory=os.path.join("BACKEND", "uploads")), name="uploads")

# Mount Frontend static files
app.mount("/", StaticFiles(directory="FRONTEND", html=True), name="frontend")

# Wrap FastAPI with Socket.IO ASGI application
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    print(f"\n---------------------------------------")
    print(f"   Artisan Hub Python Server Running")
    print(f"   http://localhost:{port}")
    print(f"---------------------------------------\n")
    uvicorn.run(socket_app, host="0.0.0.0", port=port)
