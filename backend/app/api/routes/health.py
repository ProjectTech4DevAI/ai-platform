from fastapi import APIRouter, HTTPException
from typing import Any, Dict

router = APIRouter(tags=["health"])



@router.get("/health")
async def health_check():
    """Health check endpoint to verify API status"""
    try:
        return {"status": "ok"}
    except Exception as e:
        return str(e)