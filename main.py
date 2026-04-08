import asyncio
import logging
import os

import uvicorn

import src.plugins  # noqa: F401 — triggers plugin registration
from src.core.api import create_app
from src.core.config import Config
from src.core.memory import close_all_checkpointers, purge_old_checkpoints
from src.core.plugin import PLUGIN_REGISTRY
from src.core.registry import AgentRegistry

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_periodic_checkpoint_purge(registry: AgentRegistry):
    configs = registry.configs
    if not configs:
        return
    interval_seconds = max(c.CHECKPOINT_PURGE_INTERVAL_HOURS for c in configs.values()) * 60 * 60
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
        agent_name = os.getenv("AGENT_NAME", "personal")
        env_file = os.getenv("ENV_FILE")
        plugin_names = [p.strip() for p in os.getenv("PLUGINS", "calendar,gmail").split(",") if p.strip()]

        config = Config(agent_name, env_file=env_file)

        plugins = []
        for name in plugin_names:
            if name not in PLUGIN_REGISTRY:
                raise ValueError(f"Unknown plugin '{name}'. Available: {', '.join(PLUGIN_REGISTRY)}")
            plugins.append(PLUGIN_REGISTRY[name].from_config(config))

        logger.info(
            "Agent=%s plugins=%s provider=%s",
            agent_name,
            plugin_names,
            config.LLM_PROVIDER,
        )

        registry = AgentRegistry()
        await registry.register(agent_name, config, plugins)

        api_key = os.getenv("FASTAPI_KEY", config.FASTAPI_KEY)
        app = create_app(registry, api_key=api_key)

        host = config.FASTAPI_HOST
        port = config.FASTAPI_PORT

        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info"))

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
