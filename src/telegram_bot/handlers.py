"""
DEPRECATED: Telegram bot handlers.
Superseded by the FastAPI-based API (src/api/). Kept for backward compatibility
but no longer actively maintained. Will be removed in a future release.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage
from src.agent.state import AgentState
from src.agent.graph import get_agent_state_graph
from src.utils.web_scraper import scrape_and_chunk
from src.services.rag import get_rag_service

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: 
    user = update.effective_user
    logger.info(f"User {user.id} started the bot.")
    await update.message.reply_text(f"Hello, {user.first_name}! Welcome to the bot. How can I assist you today?")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:    
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help message
/ingest <URL> - Ingest content from the provided URL
Just send me any message and I'll respond!
    """
    await update.message.reply_text(help_text)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Nice image! However, I can only process text messages at the moment.")
    
async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Sorry, I didn't understand that command. Type /help to see available commands.")
        
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: 
    user = update.effective_user
    user_message = update.message.text
    logger.info(f"Received message from {user.id}: {user_message}")
    
    try: 
        state = AgentState(
            user_id=str(user.id),
            messages=[HumanMessage(content=user_message)]
        )
        graph_state = await get_agent_state_graph()
        today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        result = await graph_state.ainvoke(
            state,
            config={"configurable": {"thread_id": f"{user.id}_{today}"}} 
        )
        
        ai_response = result["messages"][-1].content
        await update.message.reply_text(ai_response)
    except Exception as e:
        logger.error(f"Error processing message from {user.id}: {e}")
        await update.message.reply_text("Sorry, something went wrong while processing your message.")    
        
async def ingest_url_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text("Please provide a URL to ingest. Usage: /ingest_url <URL>")
        return
    
    url = context.args[0]
    logger.info(f"User {user.id} requested URL ingestion: {url}")
    
    await update.message.reply_text(f"Starting ingestion of the URL: {url}")
    
    try: 
        chunks, metadata = await scrape_and_chunk(url)
        
        rag_service = get_rag_service()
        
        if rag_service is None:
            await update.message.reply_text("❌ URL ingestion feature is not available (RAG dependencies not installed)")
            return 
        
        rag_service.add_documents(
            chunks, 
            metadata,
            user_id=str(user.id)
        )
        
        await update.message.reply_text(
            f"Successfully ingested content from {url}."
            f"You can now ask questions related to this content."
        )
    except Exception as e:
        logger.error(f"Error ingesting URL for user {user.id}: {e}")
        await update.message.reply_text("Sorry, there was an error ingesting the provided URL.")