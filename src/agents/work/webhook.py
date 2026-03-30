import base64
import json
import logging
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response, HTTPException
from langchain_core.messages import HumanMessage

from src.core.config import Config

logger = logging.getLogger(__name__)

# In-memory last-seen historyId — resets on restart (single instance, sufficient for Pi)
_last_history_id: Optional[str] = None


def register_webhook_routes(
    app: FastAPI,
    get_graph: Callable,
    plugins: list,
) -> None:

    @app.post("/webhooks/gmail")
    async def gmail_webhook(request: Request) -> Response:
        """
        Receive Google Cloud Pub/Sub push notifications for Gmail.

        Pub/Sub pushes:
          {"message": {"data": "<base64 JSON>", ...}, "subscription": "..."}

        Decoded data: {"emailAddress": "...", "historyId": "12345"}
        """
        global _last_history_id

        # Token verification
        token = request.query_params.get("token", "")
        if Config.GMAIL_PUBSUB_VERIFICATION_TOKEN and token != Config.GMAIL_PUBSUB_VERIFICATION_TOKEN:
            logger.warning("Gmail webhook: invalid verification token")
            raise HTTPException(status_code=403, detail="Invalid token")

        # Parse Pub/Sub envelope
        try:
            body = await request.json()
            encoded_data = body["message"]["data"]
            notification = json.loads(base64.b64decode(encoded_data).decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse Pub/Sub message: {e}")
            return Response(status_code=200)  # 200 prevents Pub/Sub retrying malformed msgs

        history_id = notification.get("historyId")
        if not history_id:
            return Response(status_code=200)

        logger.info(f"Gmail push notification — historyId={history_id}")

        # Find the WorkGmailPlugin
        from src.plugins.work_gmail import WorkGmailPlugin
        gmail_plugin = next(
            (p for p in plugins if isinstance(p, WorkGmailPlugin)), None
        )
        if not gmail_plugin or not gmail_plugin._service:
            logger.error("WorkGmailPlugin not available")
            return Response(status_code=200)

        svc = gmail_plugin._service
        start_id = _last_history_id or str(int(history_id) - 1)

        try:
            history_response = svc.list_history(
                start_history_id=start_id, max_results=20
            )
        except Exception as e:
            logger.error(f"Failed to fetch Gmail history: {e}", exc_info=True)
            return Response(status_code=200)

        _last_history_id = history_id

        # Collect new INBOX+UNREAD message IDs
        new_message_ids = []
        for record in history_response.get("history", []):
            for added in record.get("messagesAdded", []):
                msg = added.get("message", {})
                labels = msg.get("labelIds", [])
                if "INBOX" in labels and "UNREAD" in labels:
                    new_message_ids.append(msg["id"])

        if not new_message_ids:
            return Response(status_code=200)

        graph = get_graph()
        if graph is None:
            logger.error("Graph not initialized")
            return Response(status_code=200)

        for msg_id in new_message_ids:
            try:
                full_msg = svc.get_email_by_id(msg_id)
                from src.plugins.work_gmail.utils import parse_email
                email_text = parse_email(full_msg)
                thread_id = full_msg.get("threadId", "")

                prompt = (
                    f"A new email has arrived:\n\n{email_text}\n\n"
                    f"Thread ID: {thread_id}\n"
                    f"Message ID: {msg_id}\n\n"
                    "First, research the sender's company using search_web if you don't already know them. "
                    "Then, based on your instructions, determine if this is a business inquiry. "
                    "If it is, use that research to craft a personalized reply and send it using reply_to_email. "
                    "If it is not a business inquiry, do nothing."
                )

                await graph.ainvoke(
                    {
                        "user_id": "webhook_processor",
                        "messages": [HumanMessage(content=prompt)],
                    },
                    config={"configurable": {"thread_id": f"webhook_{msg_id}"}},
                )
                logger.info(f"Webhook: processed message {msg_id}")
            except Exception as e:
                logger.error(
                    f"Webhook: error processing message {msg_id}: {e}", exc_info=True
                )

        return Response(status_code=200)
