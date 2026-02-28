"""
RTH Cortex API Module

This module contains the API endpoints for the RTH Cortex Knowledge Synthesis System.
"""

# Import the API router
from .api_v1.api import api_router as api_v1_router

# List of all API routers
__all__ = [
    'api_v1_router',
]
