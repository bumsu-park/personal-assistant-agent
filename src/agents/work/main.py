import asyncio
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn
from langchain_core.messages import HumanMessage

from src.core.config import Config
from src.core.graph import create_agent
from src.core.api import create_app
from src.plugins.work_gmail import WorkGmailPlugin
from src.plugins.web_research import WebResearchPlugin
from src.plugins.instructions import InstructionsPlugin

logger = logging.getLogger(__name__)

INSTRUCTIONS_PATH = Path(__file__).parent / "instructions.md"

PLUGINS = [
    WorkGmailPlugin(credentials_path=Config.GMAIL_CREDENTIALS_PATH),
    WebResearchPlugin(),
    InstructionsPlugin(instructions_path=INSTRUCTIONS_PATH),
]

# Shared graph reference — also used by the webhook handler
_graph = None


async def get_graph():
    global _graph
    if _graph is None:
        def system_prompt_builder():
            now = datetime.now(ZoneInfo("America/New_York")).strftime(
                "%A, %Y-%m-%d %H:%M:%S"
            )
            return (
                f"You are a work assistant. Current date and time: {now} EST/EDT.\n"
                "You handle business email, market research, and lead finding."
            )

        _graph = await create_agent(
            plugins=PLUGINS,
            system_prompt_builder=system_prompt_builder,
        )
    return _graph


from src.agents.work.webhook import register_webhook_routes  # noqa: E402

app = create_app(get_graph, title="Work Agent API")
register_webhook_routes(app, lambda: _graph, PLUGINS)


async def _renew_gmail_watch():
    """Re-register Gmail Watch every 6 days (watch expires after 7)."""
    if not Config.GOOGLE_PUBSUB_PROJECT_ID:
        logger.info("GOOGLE_PUBSUB_PROJECT_ID not set — skipping watch renewal.")
        return

    gmail_plugin = next((p for p in PLUGINS if isinstance(p, WorkGmailPlugin)), None)
    if not gmail_plugin or not gmail_plugin._service:
        logger.warning("WorkGmailPlugin not ready for watch renewal.")
        return

    interval = 6 * 24 * 60 * 60  # 6 days
    while True:
        try:
            result = gmail_plugin._service.setup_gmail_watch(
                project_id=Config.GOOGLE_PUBSUB_PROJECT_ID,
                topic_name=Config.GOOGLE_PUBSUB_TOPIC_NAME,
            )
            logger.info(f"Gmail watch renewed: {result}")
        except Exception as e:
            logger.error(f"Gmail watch renewal failed: {e}", exc_info=True)
        await asyncio.sleep(interval)


async def _fallback_poll():
    """Poll for new emails when Pub/Sub is not configured."""
    if Config.GOOGLE_PUBSUB_PROJECT_ID:
        logger.info("Pub/Sub configured — skipping fallback polling.")
        return

    interval = Config.WORK_EMAIL_POLL_FALLBACK_MINUTES * 60
    logger.info(
        f"Starting fallback email poll every {Config.WORK_EMAIL_POLL_FALLBACK_MINUTES} minutes."
    )
    while True:
        await asyncio.sleep(interval)
        try:
            graph = await get_graph()
            prompt = (
                f"Check for any new unread business inquiry emails received in the last "
                f"{Config.WORK_EMAIL_POLL_FALLBACK_MINUTES} minutes. "
                "For each genuine business inquiry, draft and send an appropriate reply "
                "using the reply_to_email tool, informed by your instructions."
            )
            await graph.ainvoke(
                {"user_id": "poll_processor", "messages": [HumanMessage(content=prompt)]},
                config={"configurable": {"thread_id": "fallback_poll"}},
            )
        except Exception as e:
            logger.error(f"Fallback poll error: {e}", exc_info=True)


async def start():
    # Initialize graph (and plugins) before anything else
    await get_graph()

    # Set up initial Gmail watch if Pub/Sub is configured
    if Config.GOOGLE_PUBSUB_PROJECT_ID:
        gmail_plugin = next((p for p in PLUGINS if isinstance(p, WorkGmailPlugin)), None)
        if gmail_plugin and gmail_plugin._service:
            try:
                gmail_plugin._service.setup_gmail_watch(
                    project_id=Config.GOOGLE_PUBSUB_PROJECT_ID,
                    topic_name=Config.GOOGLE_PUBSUB_TOPIC_NAME,
                )
                logger.info("Initial Gmail watch registered.")
            except Exception as e:
                logger.warning(f"Initial Gmail watch setup failed: {e}")

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=Config.FASTAPI_HOST,
            port=Config.FASTAPI_PORT,
            log_level="info",
        )
    )
    await asyncio.gather(
        server.serve(),
        _renew_gmail_watch(),
        _fallback_poll(),
    )
