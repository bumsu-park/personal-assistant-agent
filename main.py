import asyncio
import importlib
import logging
import os
from src.core.config import Config
from src.core.memory import purge_old_checkpoints

logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_periodic_checkpoint_purge():
    interval_seconds = max(1, Config.CHECKPOINT_PURGE_INTERVAL_HOURS) * 60 * 60
    while True:
        try:
            await purge_old_checkpoints()
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Periodic checkpoint purge task cancelled.")
            raise
        except Exception as e:
            logger.exception("Periodic checkpoint purge failed: %s", e)
            await asyncio.sleep(interval_seconds)


async def main():
    try:
        Config.validate()
        logger.info("Configuration validated successfully.")

        agent_name = os.getenv("AGENT", "personal")
        agent_module = importlib.import_module(f"src.agents.{agent_name}.main")

        await asyncio.gather(
            agent_module.start(),
            run_periodic_checkpoint_purge(),
        )
    except Exception as e:
        logger.exception("Failed while executing main function: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
