import asyncio
import importlib
import logging
import os

import uvicorn

from src.core.api import create_app
from src.core.memory import purge_old_checkpoints, close_all_checkpointers
from src.core.registry import AgentRegistry

AGENT_MODULES = os.getenv("AGENTS", "personal").split(",")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_periodic_checkpoint_purge(registry: AgentRegistry):
    configs = registry.configs
    if not configs:
        return
    interval_seconds = (
        max(c.CHECKPOINT_PURGE_INTERVAL_HOURS for c in configs.values()) * 60 * 60
    )
    interval_seconds = max(3600, interval_seconds)
    while True:
        try:
            for name, cfg in configs.items():
                logger.info(f"Purging checkpoints for agent: {name}")
                await purge_old_checkpoints(cfg)
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Periodic checkpoint purge task cancelled.")
            raise
        except Exception as e:
            logger.exception("Periodic checkpoint purge failed: %s", e)
            await asyncio.sleep(interval_seconds)


async def main():
    try:
        registry = AgentRegistry()

        for module_name in AGENT_MODULES:
            module_name = module_name.strip()
            logger.info(f"Loading agent module: {module_name}")
            agent_module = importlib.import_module(f"src.agents.{module_name}.main")
            await agent_module.register(registry)

        logger.info(f"Registered agents: {registry.agent_names}")

        first_config = next(iter(registry.configs.values()))
        api_key = os.getenv("API_KEY", first_config.API_KEY)
        app = create_app(registry, api_key=api_key)

        host = os.getenv("FASTAPI_HOST", "0.0.0.0")
        port = int(os.getenv("FASTAPI_PORT", "8000"))

        server = uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_level="info")
        )

        await asyncio.gather(
            server.serve(),
            run_periodic_checkpoint_purge(registry),
        )
    except Exception as e:
        logger.exception("Failed while executing main function: %s", e)
        raise
    finally:
        await close_all_checkpointers()


if __name__ == "__main__":
    asyncio.run(main())
