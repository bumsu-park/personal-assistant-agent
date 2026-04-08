import base64


def get_email_body(payload) -> str:
    """Recursively extract body from email payload."""
    body = ""

    if "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")

    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                if part["body"].get("data"):
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                    break
            elif "parts" in part:
                body = get_email_body(part)
                if body:
                    break

    return body


def parse_email(email):
    headers = email["payload"]["headers"]

    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
    sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
    date = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown")

    body = get_email_body(email["payload"]) or email.get("snippet", "")

    return f"From: {sender}\nSubject: {subject}\nDate: {date}\nBody: {body}"
