"""
Entry point for the Legal Communications Backend
"""

import sys
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import the FastAPI application
from src.app import app
from src.config.settings import PORT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Legal Communications Backend on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)