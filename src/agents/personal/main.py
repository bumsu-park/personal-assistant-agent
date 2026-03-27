import uvicorn
from src.core.config import Config
from src.core.graph import create_agent
from src.core.api import create_app
from src.plugins.calendar import CalendarPlugin
from src.plugins.gmail import GmailPlugin

PLUGINS = [
    CalendarPlugin(
        username=Config.ICLOUD_EMAIL,
        password=Config.ICLOUD_APP_PASSWORD,
    ),
    GmailPlugin(
        credentials_path=Config.GMAIL_CREDENTIALS_PATH,
    ),
]


async def get_graph():
    return await create_agent(plugins=PLUGINS)


app = create_app(get_graph, title="Wendy API")


async def start():
    config = uvicorn.Config(
        app,
        host=Config.FASTAPI_HOST,
        port=Config.FASTAPI_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
