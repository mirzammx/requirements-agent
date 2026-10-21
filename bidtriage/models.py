from dataclasses import dataclass, field


@dataclass
class Attachment:
    filename: str
    data: bytes
    content_type: str
    # Set when the loader could not extract the file; it is then listed as not read.
    unreadable_reason: str = ""


@dataclass
class Bid:
    subject: str
    sender: str
    date: str
    body: str
    attachments: list[Attachment] = field(default_factory=list)
    source_path: str = ""
