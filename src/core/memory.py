from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

if TYPE_CHECKING:
    from src.core.config import Config

logger = logging.getLogger(__name__)

_saver_contexts: dict[Path, object] = {}
_checkpointers: dict[Path, AsyncSqliteSaver] = {}


async def get_checkpointer(config: Config) -> AsyncSqliteSaver:
    checkpoint_path = config.CHECKPOINTS_DIR / "checkpoints.db"

    if checkpoint_path in _checkpointers:
        return _checkpointers[checkpoint_path]

    logger.info(f"Using checkpoint database at: {checkpoint_path}")

    ctx = AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
    saver = await ctx.__aenter__()

    _saver_contexts[checkpoint_path] = ctx
    _checkpointers[checkpoint_path] = saver

    logger.info("Checkpoint database initialized successfully.")
    return saver


async def close_all_checkpointers():
    for path, ctx in list(_saver_contexts.items()):
        try:
            await ctx.__aexit__(None, None, None)
            logger.info(f"Closed checkpointer for {path}")
        except Exception as e:
            logger.error(f"Error closing checkpointer for {path}: {e}", exc_info=True)
    _saver_contexts.clear()
    _checkpointers.clear()


async def purge_old_checkpoints(config: Config):
    checkpoint_path = config.CHECKPOINTS_DIR / "checkpoints.db"
    if not checkpoint_path.exists():
        logger.info(f"No checkpoint DB found at {checkpoint_path}, skipping purge.")
        return

    cutoff_date = (
        datetime.now(ZoneInfo("America/New_York"))
        - timedelta(days=config.CHECKPOINT_PURGE_DAYS)
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
