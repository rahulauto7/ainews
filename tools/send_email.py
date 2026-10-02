"""
Send the daily AI news PDF via Gmail API (OAuth).
Uses credentials.json for OAuth and saves token.json after first auth.
Reads recipient from .env RECIPIENT_EMAIL.
"""

import base64
import json
import os
import sys
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

TMP_DIR = os.path.join(PROJECT_ROOT, ".tmp")
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_FILE = os.path.join(PROJECT_ROOT, "token.json")

RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

TODAY = datetime.now().strftime("%Y-%m-%d")
NICE_DATE = datetime.now().strftime("%A, %B %d, %Y")


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            try:
                creds.refresh(Request())
                refreshed = True
            except Exception as e:
                # A revoked or expired refresh token needs a human at a browser,
                # so say which one it is instead of dying on a raw OAuth trace.
                print(f"Token refresh failed ({type(e).__name__}: {str(e)[:120]}).")
                print("Falling back to browser authorization.")
        if not refreshed:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: {CREDENTIALS_FILE} not found.")
                print("Download it from Google Cloud Console -> APIs -> Credentials -> OAuth 2.0 Client IDs")
                sys.exit(1)
            # Imported here, not at module scope: the daily send only ever needs
            # the refresh path, and google-auth-oauthlib went uninstalled from
            # 2026-04 to 2026-09-17, which made this module un-importable and
            # silently took the whole delivery step out of the pipeline.
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
            except ImportError:
                print("ERROR: google-auth-oauthlib is not installed and the saved token "
                      "cannot be refreshed.\n  pip install google-auth-oauthlib")
                sys.exit(1)
            print("Opening browser for Gmail authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("Token saved.")

    return build("gmail", "v1", credentials=creds)


def edition_summary(analyzed_file=None):
    """What today's PDF actually contains, read from the file the PDF renders.

    Returns {"sections": [(label, count)], "section_count": n, "total_stories": n}
    in render order, with empty sections left out - Quantum + AI is weekly, so it
    carries no stories on six days in seven.
    """
    from generate_pdf import SECTION_CONFIG, SECTION_ORDER

    if analyzed_file is None:
        analyzed_file = os.path.join(TMP_DIR, "analyzed_content.json")
    try:
        with open(analyzed_file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"sections": [], "section_count": 0, "total_stories": 0}

    sections = data.get("sections", {})
    labels = data.get("section_labels", {})
    out = []
    for key in SECTION_ORDER:
        stories = sections.get(key) or []
        if stories:
            label = labels.get(key) or SECTION_CONFIG.get(key, {}).get("label", key)
            out.append((label, len(stories)))
    return {
        "sections": out,
        "section_count": len(out),
        "total_stories": sum(n for _, n in out),
    }


def build_body(summary, nice_date):
    """The HTML body, describing the edition attached rather than a fixed blurb."""
    if summary["sections"]:
        rows = "".join(
            f'<tr><td style="padding:3px 10px 3px 0;color:#333;font-size:13px;">{label}</td>'
            f'<td style="padding:3px 0;color:#888;font-size:13px;">{n}</td></tr>'
            for label, n in summary["sections"]
        )
        contents = (
            f'<p style="color:#333;font-size:14px;">Today\'s edition runs '
            f'<strong>{summary["section_count"]} sections</strong> and '
            f'<strong>{summary["total_stories"]} stories</strong>:</p>'
            f'<table style="border-collapse:collapse;margin:0 0 10px 0;">{rows}</table>'
        )
    else:
        contents = ('<p style="color:#333;font-size:14px;">'
                    "The section breakdown was unavailable when this mail was built.</p>")

    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #1a1a2e; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">GLOBAL AI NEWS</h1>
            <p style="color: #b4c8ff; margin: 5px 0 0 0;">Daily Intelligence Briefing</p>
        </div>
        <div style="padding: 20px; background-color: #f8f9fa;">
            <p style="color: #333; font-size: 14px;">Good morning!</p>
            <p style="color: #333; font-size: 14px;">
                Your <strong>Global AI News</strong> briefing for <strong>{nice_date}</strong> is attached.
            </p>
            {contents}
            <p style="color: #888; font-size: 12px; margin-top: 30px;">
                This briefing was automatically generated by the Global AI News pipeline.
            </p>
        </div>
    </div>
    """


def find_pdf():
    """Find today's PDF in .tmp/"""
    pdf_name = f"ai_news_daily_{TODAY}.pdf"
    pdf_path = os.path.join(TMP_DIR, pdf_name)

    if os.path.exists(pdf_path):
        return pdf_path

    # Fallback: find the most recent PDF
    pdfs = [f for f in os.listdir(TMP_DIR) if f.startswith("ai_news_daily_") and f.endswith(".pdf")]
    if pdfs:
        pdfs.sort(reverse=True)
        return os.path.join(TMP_DIR, pdfs[0])

    return None


def build_email(sender, recipient, pdf_path):
    """Build the email with PDF attachment."""
    msg = MIMEMultipart()
    msg["To"] = recipient
    msg["From"] = sender
    msg["Subject"] = f"Global AI News Briefing - {NICE_DATE}"

    html_body = build_body(edition_summary(), NICE_DATE)

    msg.attach(MIMEText(html_body, "html"))

    # Attach PDF
    pdf_name = os.path.basename(pdf_path)
    with open(pdf_path, "rb") as f:
        pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=pdf_name)
    msg.attach(pdf_attachment)

    return msg


def send_email():
    """Main function: find PDF, build email, send via Gmail API."""
    if not RECIPIENT_EMAIL:
        print("ERROR: RECIPIENT_EMAIL not set in .env")
        sys.exit(1)

    pdf_path = find_pdf()
    if not pdf_path:
        print("ERROR: No PDF found in .tmp/. Run generate_pdf.py first.")
        sys.exit(1)

    pdf_size = os.path.getsize(pdf_path) / 1024
    print(f"PDF: {os.path.basename(pdf_path)} ({pdf_size:.0f} KB)")

    # Get Gmail service
    service = get_gmail_service()

    # Sender is the authenticated user
    sender = RECIPIENT_EMAIL  # Gmail sends from authenticated account
    print(f"Sending to: {RECIPIENT_EMAIL}")

    # Build and send
    msg = build_email(sender, RECIPIENT_EMAIL, pdf_path)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": raw}
    ).execute()

    print(f"\nEmail sent successfully!")
    print(f"  Subject: Global AI News Briefing - {NICE_DATE}")
    return True


if __name__ == "__main__":
    send_email()
