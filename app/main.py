from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import wish

app = FastAPI(
    title="Wishes API",
    description="API for wishes management",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def read_root():
    return {"status": "running"}

# include routes
app.include_router(wish.router) 