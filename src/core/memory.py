import logging
import aiosqlite
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from src.core.config import Config

logger = logging.getLogger(__name__)

_saver_context = None
_checkpointer = None


async def get_checkpointer() -> AsyncSqliteSaver:
    global _saver_context, _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    checkpoint_path = Config.CHECKPOINTS_DIR / "checkpoints.db"

    logger.info(f"Using checkpoint database at: {checkpoint_path}")

    _saver_context = AsyncSqliteSaver.from_conn_string(str(checkpoint_path))

    _checkpointer = await _saver_context.__aenter__()

    logger.info("Checkpoint database initialized successfully.")

    return _checkpointer


async def close_checkpointer():
    global _saver_context, _checkpointer

    if _saver_context is not None and _checkpointer is not None:
        await _saver_context.__aexit__(None, None, None)
        _saver_context = None
        _checkpointer = None
        logger.info("Checkpoint database connection closed.")


async def purge_old_checkpoints():
    checkpoint_path = Config.CHECKPOINTS_DIR / "checkpoints.db"
    if not checkpoint_path.exists():
        logger.info("No checkpoint DB found, skipping purge.")
        return

    cutoff_date = (
        datetime.now(ZoneInfo("America/New_York"))
        - timedelta(days=Config.CHECKPOINT_PURGE_DAYS)
    ).strftime("%Y-%m-%d")

    try:
        async with aiosqlite.connect(str(checkpoint_path)) as db:
            for table in ("checkpoints", "writes"):
                result = await db.execute(
                    f"DELETE FROM {table} WHERE substr(thread_id, -10) < ?",
                    (cutoff_date,),
                )
                logger.info(f"Purged {result.rowcount} rows from {table}")
            await db.commit()
        logger.info(f"Checkpoint purge complete (cutoff: {cutoff_date})")
    except Exception as e:
        logger.error(f"Error purging old checkpoints: {e}", exc_info=True)
