import asyncio
import logging
from src.config import Config
from src.api.server import start_api
from src.services.memory import purge_old_checkpoints

logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_telegram_bot():
    """DEPRECATED: Telegram bot — superseded by FastAPI API. Will be removed in a future release."""
    if not Config.TELEGRAM_BOT_TOKEN:
        logger.info("TELEGRAM_BOT_TOKEN not set — skipping deprecated Telegram bot.")
        return
    from src.telegram_bot.bot import create_bot

    logger.warning("Starting deprecated Telegram bot. Migrate to the FastAPI API.")
    app = create_bot()
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logger.info("Telegram bot started and polling for updates")
        stop_event = asyncio.Event()
        await stop_event.wait()


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

        await asyncio.gather(
            # run_telegram_bot(),  # DEPRECATED — superseded by FastAPI API
            start_api(),
            run_periodic_checkpoint_purge(),
        )
    except Exception as e:
        logger.exception("Failed while executing main function: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
