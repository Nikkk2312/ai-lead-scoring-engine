"""
Features 35, 50: Slack/email run notifications, score-change alerts.
"""
import json
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SLACK_WEBHOOK_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_EMAIL_TO


def notify_run_complete(run_summary: dict):
    """Feature 35: Send notification when a run finishes."""
    message = format_run_summary(run_summary)

    sent_to = []
    if SLACK_WEBHOOK_URL:
        if send_slack(message):
            sent_to.append("slack")
    if SMTP_HOST and NOTIFY_EMAIL_TO:
        if send_email("Lead Scoring Run Complete", message):
            sent_to.append("email")

    if not sent_to:
        print("[NOTIFY] No notification channels configured (set SLACK_WEBHOOK_URL or SMTP_* in .env)")
    else:
        print(f"[NOTIFY] Sent to: {', '.join(sent_to)}")


def notify_score_change(changes: list[dict]):
    """Feature 50: Alert when companies cross tier thresholds."""
    if not changes:
        return

    became_hot = [c for c in changes if c.get("became_hot")]
    if not became_hot:
        return

    lines = ["Score Change Alert - New Hot Leads!", ""]
    for c in became_hot:
        lines.append(f"  {c['company_name']} ({c['domain']}): {c.get('prev_tier', '?')} -> Hot (score: {c.get('score', '?')})")

    message = "\n".join(lines)
    if SLACK_WEBHOOK_URL:
        send_slack(message)
    if SMTP_HOST and NOTIFY_EMAIL_TO:
        send_email("New Hot Lead Alert", message)


def format_run_summary(summary: dict) -> str:
    """Format a run summary for notifications."""
    lines = [
        "Lead Scoring Pipeline - Run Complete",
        f"Run ID: {summary.get('run_id', 'N/A')}",
        f"Total Leads: {summary.get('total', 0)}",
        f"Hot: {summary.get('hot', 0)} | Warm: {summary.get('warm', 0)} | Cold: {summary.get('cold', 0)}",
        f"Errors: {summary.get('errors', 0)}",
        f"Duration: {summary.get('duration', 'N/A')}",
    ]

    if summary.get("new_hot"):
        lines.append("")
        lines.append("New Hot Leads:")
        for lead in summary["new_hot"][:5]:
            lines.append(f"  - {lead['company_name']} ({lead['domain']}): {lead.get('total_score', 0)}/100")

    return "\n".join(lines)


def send_slack(message: str) -> bool:
    """Send a message to Slack via webhook."""
    if not SLACK_WEBHOOK_URL:
        return False
    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            json={"text": f"```\n{message}\n```"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[NOTIFY] Slack error: {e}")
        return False


def send_email(subject: str, body: str) -> bool:
    """Send an email notification."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, NOTIFY_EMAIL_TO]):
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = NOTIFY_EMAIL_TO
        msg["Subject"] = f"[Lead Scorer] {subject}"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[NOTIFY] Email error: {e}")
        return False
