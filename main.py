import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, quiz, websocket
from app.core.config import settings

app = FastAPI(title="Elsa API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(quiz.router, prefix="/api", tags=["quiz"])
app.include_router(websocket.router, tags=["websocket"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        workers=1,
        ws_ping_interval=None,  # Disable ping/pong to prevent connection issues
        ws_ping_timeout=None
    )
