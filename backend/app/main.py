from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes_chat

app = FastAPI(title="Intelligent Agri-QA System", version="1.0")

# CORS setup (for React frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your frontend domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(routes_chat.router, prefix="/api/chat", tags=["Chat"])

@app.get("/")
def read_root():
    return {"message": "Backend is running 🚀"}
