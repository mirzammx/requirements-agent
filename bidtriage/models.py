from dataclasses import dataclass, field


@dataclass
class Attachment:
    filename: str
    data: bytes
    content_type: str


@dataclass
class Bid:
    subject: str
    sender: str
    date: str
    body: str
    attachments: list[Attachment] = field(default_factory=list)
    source_path: str = ""
