"""Green Climate Fund: Open Data Library project list + public project pages.

Unit of observation: one GCF approved project (FP/SAP reference).
Label category C: GCF ``Theme`` (Mitigation / Adaptation / Cross-cutting), assigned by GCF.
Every GCF project is climate-dedicated, so GCF provides **no negative class** and is not an
independent label source for the negative-versus-positive benchmark.

The page "Overview" is a GCF-written portfolio summary with no publication date on the page;
its timing is ``portfolio_summary_undated``. Dates of the approved funding proposal and the
pre-approval timeline (concept note / funding proposal received) are recorded separately as
evidence of when contemporaneous proposal text existed. Contact persons on the page are never
extracted.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from compassio_ml.external.records import CandidateRecord, SectorFamily, TextTiming
from compassio_ml.external.registry import RetrievalRun, read_retrieval_manifest

SOURCE_ID = "gcf_project_pages"
PUBLISHER = "Green Climate Fund"
ODL_URL = "https://data.greenclimate.fund/public/data/projects"
PAGE_URL = "https://www.greenclimate.fund/project/{ref}"
TERMS_URL = "https://www.greenclimate.fund/terms-and-conditions"
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
_SPACE = re.compile(r"\s+")
VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)
_WB_CODE = re.compile(r"\bP\d{6}\b")
_GCF_CODE = re.compile(r"\b(FP|SAP)(\d{3})\b")


def parse_odl(html_text: str) -> list[dict[str, Any]]:
    match = _NEXT_DATA.search(html_text)
    if match is None:
        raise ValueError("GCF ODL page has no __NEXT_DATA__ block")
    data = json.loads(match.group(1))["props"]["pageProps"]["data"]["data"]
    if not isinstance(data, list):
        raise ValueError("Unexpected ODL data structure")
    return data


def acquire(run: RetrievalRun, *, limit: int | None = None) -> list[str]:
    notes: list[str] = []
    run.fetch(TERMS_URL, "terms_and_conditions.html", max_bytes=5 * 1024 * 1024, role="terms")
    odl = run.fetch(ODL_URL, "odl_projects.html", max_bytes=10 * 1024 * 1024, role="index")
    if odl is None:
        notes.append("ODL project list failed; no project pages fetched")
        return notes
    projects = parse_odl(odl.path.read_text(encoding="utf-8"))
    refs = sorted({str(p["ApprovedRef"]) for p in projects if p.get("ApprovedRef")})
    if limit is not None:
        refs = refs[:limit]
    run.parameters = {"odl_projects": len(projects), "pages_requested": len(refs), "limit": limit}
    for ref in refs:
        run.fetch(
            PAGE_URL.format(ref=ref.lower()),
            f"pages/{ref}.html",
            max_bytes=3 * 1024 * 1024,
            role="data",
        )
    notes.append(f"ODL listed {len(projects)} projects; requested {len(refs)} pages")
    return notes


@dataclass
class _Doc:
    href: str
    title: str = ""
    type: str = ""
    date: str = ""


@dataclass
class PageFields:
    title: str = ""
    meta: dict[str, str] = field(default_factory=dict)
    overview: str = ""
    timeline: list[tuple[str, str]] = field(default_factory=list)
    documents: list[_Doc] = field(default_factory=list)


class _PageParser(HTMLParser):
    """Collects only: <h1>, <dt>/<dd> pairs, the prose (``primitives:wysiwyg``) blocks of
    section#overview - never its meta/theme/timeline widgets, which would leak the GCF label and
    post-approval status into model text - timeline <h5>+<time>,
    and /document/ links with aria-labelled Title/Type/Date. Never fetches anything."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out = PageFields()
        self._stack: list[str] = []
        self._capture: str | None = None
        self._buf: list[str] = []
        self._dt: str | None = None
        self._overview_depth: int | None = None
        self._prose_depth: int | None = None
        self._overview_parts: list[str] = []
        self._h5: str | None = None
        self._doc: _Doc | None = None
        self._doc_depth: int | None = None
        self._doc_label: str | None = None
        self._skip = 0

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" and self._prose_depth is not None:
            self._overview_parts.append(" ")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag in VOID_ELEMENTS:
            self.handle_startendtag(tag, attrs)
            return
        if tag in ("script", "style", "svg"):
            self._skip += 1
        self._stack.append(tag)
        depth = len(self._stack)
        if tag == "section" and a.get("id") == "overview" and self._overview_depth is None:
            self._overview_depth = depth
        in_overview = self._overview_depth is not None and self._overview_depth > 0
        if (
            in_overview
            and self._prose_depth is None
            and tag == "div"
            and a.get("data-component") == "primitives:wysiwyg"
        ):
            self._prose_depth = depth
        if tag in ("p", "li", "br", "h2", "h3", "h4") and self._prose_depth is not None:
            self._overview_parts.append(" ")
        href = a.get("href") or ""
        if tag == "a" and href.startswith("/document/"):
            self._doc, self._doc_depth = _Doc(href=href), depth
        if self._doc is not None and a.get("aria-label") in ("Title", "Type", "Date"):
            self._start_capture(f"doc:{a['aria-label']}")
        if tag in ("h1", "dt", "dd", "h5") and self._doc is None:
            self._start_capture(tag)
        if tag == "time" and self._h5 is not None:
            self.out.timeline.append((self._h5, a.get("datetime") or ""))
            self._h5 = None

    def _start_capture(self, kind: str) -> None:
        self._capture, self._buf = kind, []

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_ELEMENTS or tag not in self._stack:
            return  # void or stray end tag: nothing to close
        position = len(self._stack) - 1 - self._stack[::-1].index(tag)
        depth = position + 1
        if tag in ("script", "style", "svg") and self._skip:
            self._skip -= 1
        if self._capture is not None and (
            (self._capture.startswith("doc:") and tag in ("strong", "span")) or self._capture == tag
        ):
            self._finish_capture()
        if self._doc is not None and tag == "a" and depth == self._doc_depth:
            self.out.documents.append(self._doc)
            self._doc = self._doc_depth = None
        if self._prose_depth is not None and depth <= self._prose_depth:
            self._prose_depth = None
            self._overview_parts.append(" ")
            self.out.overview = _SPACE.sub(" ", "".join(self._overview_parts)).strip()
        if (
            self._overview_depth is not None
            and self._overview_depth > 0
            and depth <= self._overview_depth
        ):
            self._overview_depth = -1  # overview section closed; never reopen
        del self._stack[position:]

    def _finish_capture(self) -> None:
        text = _SPACE.sub(" ", "".join(self._buf)).strip()
        kind, self._capture = self._capture, None
        if kind == "h1" and not self.out.title:
            self.out.title = text
        elif kind == "dt":
            self._dt = text
        elif kind == "dd" and self._dt is not None:
            self.out.meta.setdefault(self._dt, text)
            self._dt = None
        elif kind == "h5":
            self._h5 = text
        elif kind is not None and kind.startswith("doc:") and self._doc is not None:
            setattr(self._doc, kind[4:].lower(), text)

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._capture is not None:
            self._buf.append(data)
        if self._prose_depth is not None:
            self._overview_parts.append(data)


def parse_page(html_text: str) -> PageFields:
    parser = _PageParser()
    parser.feed(html_text)
    parser.close()
    return parser.out


def _iso(value: str) -> str | None:
    for fmt in ("%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_retrieval(directory: Path) -> list[CandidateRecord]:
    manifest = read_retrieval_manifest(directory)
    retrieval_id = str(manifest["retrieval_id"])
    index = next((f for f in manifest["files"] if f.get("role") == "index"), None)
    if index is None:
        raise FileNotFoundError(f"No ODL index file in {directory}")
    odl = {
        str(p["ApprovedRef"]): p
        for p in parse_odl((directory / str(index["file"])).read_text(encoding="utf-8"))
    }
    records: list[CandidateRecord] = []
    for entry in manifest["files"]:
        if entry.get("role") != "data":
            continue
        ref = Path(str(entry["file"])).stem
        page = parse_page((directory / str(entry["file"])).read_text(encoding="utf-8"))
        meta = odl.get(ref, {})
        countries = sorted(
            {str(c.get("ISO3")) for c in meta.get("Countries") or [] if c.get("ISO3")}
        )
        proposals = [d for d in page.documents if d.type == "Approved funding proposal"]
        proposal_dates = [iso for d in proposals if (iso := _iso(d.date)) is not None]
        proposal_date = min(proposal_dates, default=None)
        timeline = {name: _iso(value) for name, value in page.timeline}
        text = f"{page.title} {page.overview}"
        refs = sorted(
            {f"worldbank_projects:{c}" for c in _WB_CODE.findall(text)}
            | {
                f"{SOURCE_ID}:{m.group(1)}{m.group(2)}"
                for m in _GCF_CODE.finditer(text)
                if f"{m.group(1)}{m.group(2)}" != ref
            }
        )
        records.append(
            CandidateRecord(
                source_id=SOURCE_ID,
                publisher=PUBLISHER,
                source_record_id=ref,
                retrieval_id=retrieval_id,
                raw_file=str(entry["file"]),
                raw_file_sha256=str(entry["sha256"]),
                document_url=PAGE_URL.format(ref=ref.lower()),
                title=page.title or meta.get("ProjectName"),
                description=page.overview or None,
                text_type="gcf_page_overview",
                country_iso3=countries,
                sector_codes=[],
                sector_families=[],
                sector_family=SectorFamily.UNKNOWN.value,
                approval_date=meta.get("BMDate") or _iso(page.meta.get("Date approved", "")),
                last_updated=meta.get("ProjectLastModifiedOn"),
                text_date=None,
                text_date_basis="GCF page overview has no publication date; captured at "
                f"retrieval {entry['retrieved_at']}",
                text_timing=TextTiming.PORTFOLIO_SUMMARY_UNDATED.value,
                status=page.meta.get("Status"),
                cross_references=refs,
                label_category="C_gcf_classification",
                gcf_theme=meta.get("Theme") or page.meta.get("Theme"),
                extra={
                    "approved_funding_proposal_date": proposal_date,
                    "approved_funding_proposal_links": [d.href for d in proposals],
                    "concept_note_received": timeline.get("Concept note received"),
                    "funding_proposal_received": timeline.get("Funding proposal received"),
                    "entity": meta.get("Entity"),
                    "odl_sector": meta.get("Sector"),
                    "odl_type": meta.get("Type"),
                    "board_meeting": meta.get("BM"),
                    "document_count": len(page.documents),
                },
            )
        )
    return records
