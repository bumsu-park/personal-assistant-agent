import logging
import uvicorn
from src.config import Config

logger = logging.getLogger(__name__)


async def start_api():
    """Run the FastAPI server using uvicorn's async serve API."""
    from src.api.routes import app

    config = uvicorn.Config(
        app,
        host=Config.FASTAPI_HOST,
        port=Config.FASTAPI_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info(f"Starting FastAPI on {Config.FASTAPI_HOST}:{Config.FASTAPI_PORT}")
    await server.serve()
