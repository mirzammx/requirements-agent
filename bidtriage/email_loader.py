"""Load a bid (email + attachments) from an .eml file, an Outlook .msg file, or a folder."""

import email
import email.policy
import mimetypes
from pathlib import Path

from bidtriage.models import Attachment, Bid

EMAIL_TXT = "email.txt"


def load_bid(path: str | Path) -> Bid:
    path = Path(path)
    if path.is_dir():
        return _load_folder(path)
    suffix = path.suffix.lower()
    if suffix == ".eml":
        return _load_eml(path)
    if suffix == ".msg":
        return _load_msg(path)
    raise ValueError(f"unsupported bid input {path} (expected a .msg, .eml or a folder)")


def _load_eml(path: Path) -> Bid:
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    body_part = msg.get_body(preferencelist=("plain", "html"))
    attachments = [
        Attachment(
            filename=part.get_filename() or "unnamed",
            data=part.get_payload(decode=True) or b"",
            content_type=part.get_content_type(),
        )
        for part in msg.iter_attachments()
    ]
    return Bid(
        subject=str(msg.get("Subject", "")),
        sender=str(msg.get("From", "")),
        date=str(msg.get("Date", "")),
        body=body_part.get_content() if body_part is not None else "",
        attachments=attachments,
        source_path=str(path),
    )


def _load_msg(path: Path) -> Bid:
    import extract_msg
    from extract_msg.enums import AttachmentType, ErrorBehavior

    # Tolerate attachment kinds extract_msg can't handle; they are listed as not read.
    msg = extract_msg.Message(str(path), errorBehavior=ErrorBehavior.ATTACH_SUPPRESS_ALL)
    try:
        attachments = [_msg_attachment(att, AttachmentType) for att in msg.attachments]
        return Bid(
            subject=msg.subject or "",
            sender=msg.sender or "",
            date=str(msg.date or ""),
            body=msg.body or "",
            attachments=attachments,
            source_path=str(path),
        )
    finally:
        msg.close()


def _msg_attachment(att, AttachmentType) -> Attachment:
    name = att.longFilename or att.shortFilename or "unnamed"
    if att.type == AttachmentType.WEB:
        return Attachment(name, b"", "", "cloud/linked attachment (OneDrive/SharePoint link), not downloaded")
    if att.type in (AttachmentType.MSG, AttachmentType.SIGNED_EMBEDDED):
        return Attachment(name, b"", "message/rfc822", "forwarded email inside the message, not read")
    try:
        data = att.data
    except Exception as exc:
        return Attachment(name, b"", "", f"could not extract attachment: {exc}")
    if not isinstance(data, bytes):
        return Attachment(name, b"", "", "could not extract attachment from the email")
    return Attachment(name, data, mimetypes.guess_type(name)[0] or "")


def _load_folder(path: Path) -> Bid:
    headers: dict[str, str] = {}
    body = ""
    email_txt = path / EMAIL_TXT
    if email_txt.is_file():
        headers, body = _split_headers(email_txt.read_text(encoding="utf-8", errors="replace"))
    attachments = [
        Attachment(f.name, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "")
        for f in sorted(path.iterdir())
        if f.is_file() and f.name != EMAIL_TXT
    ]
    return Bid(
        subject=headers.get("subject", path.name),
        sender=headers.get("from", ""),
        date=headers.get("sent", headers.get("date", "")),
        body=body,
        attachments=attachments,
        source_path=str(path),
    )


def _split_headers(text: str) -> tuple[dict[str, str], str]:
    """Parse leading 'Header: value' lines up to the first blank line."""
    headers: dict[str, str] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            return headers, "\n".join(lines[i + 1 :]).strip()
        name, sep, value = line.partition(":")
        if not sep or " " in name.strip():
            return headers, "\n".join(lines[i:]).strip()
        headers[name.strip().lower()] = value.strip()
    return headers, ""
