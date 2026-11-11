"""iCloud mail over IMAP: read-only, never marks messages as read."""
import html, imaplib, re
from datetime import date, timedelta
from email import message_from_bytes, policy
from email.utils import parsedate_to_datetime

from ..rules import score_email

HOST = "imap.mail.me.com"


def _preview(msg):
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        text = part.get_content() if part else ""
        if part and part.get_content_subtype() == "html":
            text = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", " ", text)
            text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    except Exception:  # truncated or malformed MIME: no preview rather than no email
        text = ""
    return " ".join(text.split())[:300]


def parse_message(raw, flags, cfg):
    msg = message_from_bytes(raw, policy=policy.default)
    sender, subject = str(msg["From"] or ""), str(msg["Subject"] or "(no subject)")
    preview, unread = _preview(msg), b"\\Seen" not in flags
    score, reasons = score_email(sender, subject, preview, unread, msg["List-Unsubscribe"] is not None, cfg)
    if score < cfg["mail"]["min_score"]:
        return None
    try:
        when = parsedate_to_datetime(str(msg["Date"])).isoformat()
    except Exception:
        when = ""
    return {"from": sender, "subject": subject, "date": when, "preview": preview,
            "unread": unread, "score": score, "reasons": reasons}


def fetch(cfg, user, pw):
    since = (date.today() - timedelta(days=cfg["mail"]["days"])).strftime("%d-%b-%Y")
    imap = imaplib.IMAP4_SSL(HOST, 993)
    try:
        imap.login(user, pw)
        imap.select("INBOX", readonly=True)
        _, data = imap.search(None, "SINCE", since)
        ids = data[0].split()
        out = []
        if ids:
            # first 30 KB holds headers + opening text; enough for a preview
            _, resp = imap.fetch(b",".join(ids), "(FLAGS BODY.PEEK[]<0.30000>)")
            for i, item in enumerate(resp):
                if isinstance(item, tuple):
                    tail = resp[i + 1] if i + 1 < len(resp) and isinstance(resp[i + 1], bytes) else b""
                    m = parse_message(item[1], item[0] + tail, cfg)  # FLAGS may arrive after the literal
                    if m:
                        out.append(m)
        out.sort(key=lambda m: (m["score"], m["date"]), reverse=True)
        return out[: cfg["mail"]["max"]]
    finally:
        try:
            imap.logout()
        except Exception:
            pass
