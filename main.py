import asyncio
import logging
from src.config import Config
from src.telegram_bot.bot import create_bot
from src.api.server import start_api

logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_telegram_bot():
    app = create_bot()
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logger.info("Telegram bot started and polling for updates")
        stop_event = asyncio.Event()
        await stop_event.wait()


async def main():
    try:
        Config.validate()
        logger.info("Configuration validated successfully.")

        await asyncio.gather(
            run_telegram_bot(),
            start_api(),
        )
    except Exception as e:
        logger.exception("Failed while executing main function: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
