from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, quiz
from app.core.config import settings
import uvicorn

app = FastAPI(title="Elsa API")

# CORS middleware configuration
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

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        workers=1
    )
