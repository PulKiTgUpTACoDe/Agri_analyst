"""Vercel serverless function entry point for FastAPI app."""
from app.main import app

# Export the FastAPI app as the handler for Vercel
handler = app
