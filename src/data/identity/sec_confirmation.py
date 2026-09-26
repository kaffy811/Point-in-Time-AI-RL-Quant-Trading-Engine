"""Offline accession-index confirmation; submissions membership alone is insufficient."""
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
import re
from typing import Any
from zoneinfo import ZoneInfo


@dataclass
class Node:
    tag: str
    attrs: dict[str, str | None]
    children: list[Any] = field(default_factory=list)

    def text(self) -> str:
        return " ".join(child.text() if isinstance(child, Node) else child
                        for child in self.children).strip()


class IndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = Node("root", {})
        self.stack = [self.root]
        self.nodes: list[Node] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        self.nodes.append(node)
        if tag not in {"meta", "link", "br", "hr", "img", "input", "wbr", "source"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def accepted_instant(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Acceptance metadata requires an explicit timezone")
    return stamp


def verify_index(content: bytes, metadata: dict[str, Any]) -> datetime:
    parser = IndexParser()
    parser.feed(content.decode("utf-8"))
    text = parser.root.text()
    accessions = set(re.findall(r"SEC\s+Accession\s+No\.\s*(\d{10}-\d{2}-\d{6})", text))
    if accessions != {metadata["accessionNumber"]}:
        raise ValueError("ARCHIVE_ACCESSION_MISMATCH")
    filers: set[str] = set()
    for node in parser.nodes:
        if "companyInfo" not in (node.attrs.get("class") or "").split():
            continue
        block = node.text()
        if "(Filer)" in block:
            filers.update(value.zfill(10) for value in re.findall(r"CIK\s*:\s*(\d+)", block))
    if filers != {metadata["cik"]}:
        raise ValueError("ARCHIVE_FILER_CIK_MISMATCH_OR_AMBIGUOUS")
    fields = {}
    pending = None
    for node in parser.nodes:
        classes = (node.attrs.get("class") or "").split()
        if "infoHead" in classes:
            pending = node.text()
        elif "info" in classes and pending:
            if pending in fields:
                raise ValueError("DUPLICATE_ARCHIVE_METADATA")
            fields[pending] = node.text()
            pending = None
    if fields.get("Filing Date") != metadata["filingDate"]:
        raise ValueError("ARCHIVE_FILING_DATE_MISMATCH")
    if fields.get("Period of Report", "") != metadata["reportDate"]:
        raise ValueError("ARCHIVE_REPORT_DATE_MISMATCH")
    primary = metadata["primaryDocument"]
    if not any((node.attrs.get("href") or "").split("/")[-1] == primary
               for node in parser.nodes if node.tag == "a"):
        raise ValueError("ARCHIVE_PRIMARY_DOCUMENT_MISMATCH")
    form_names = [node.text() for node in parser.nodes if node.attrs.get("id") == "formName"]
    if not any(re.match(r"Form\s+" + re.escape(metadata["form"]) + r"(?:\s|$)", name)
               for name in form_names):
        raise ValueError("ARCHIVE_FORM_MISMATCH")
    naive = datetime.strptime(fields["Accepted"], "%Y-%m-%d %H:%M:%S")
    zone = ZoneInfo("America/New_York")
    if naive.replace(tzinfo=zone, fold=0).utcoffset() != naive.replace(tzinfo=zone, fold=1).utcoffset():
        raise ValueError("AMBIGUOUS_ARCHIVE_ACCEPTANCE_TIME")
    accepted = naive.replace(tzinfo=zone)
    # This is only a comparison under the existing SEC local-time convention.
    # P1-02's SGML-header convention does not authorize silently overriding a
    # contradictory explicitly-zoned API timestamp with an unzoned HTML index.
    if accepted != accepted_instant(metadata["acceptanceDateTime"]):
        raise ValueError("ACCEPTANCE_TIME_SOURCE_CONFLICT_OWNER_DECISION_REQUIRED")
    return accepted
