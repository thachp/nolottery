from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

import pdfplumber
from bs4 import BeautifulSoup

from nolottery.fetch_models import ParsedDraw

_DRAW_DATE_FORMAT = "%a, %b %d, %Y"


@dataclass(frozen=True)
class SourceSnapshot:
    source_url: str
    raw_content: str
    draws: tuple[ParsedDraw, ...]


@dataclass(frozen=True)
class AdapterFetch:
    source_url: str
    draws: tuple[ParsedDraw, ...]
    snapshots: tuple[SourceSnapshot, ...]
    page_count: int = 1


class SourceReader(Protocol):
    def __call__(
        self,
        source_url: str,
        source_dir: Path | None,
        source_name: str,
        *,
        suffix: str = ".html",
    ) -> tuple[str, str]: ...


def _page_lines(soup: BeautifulSoup) -> list[str]:
    return [
        line.strip()
        for line in soup.get_text("\n", strip=True).splitlines()
        if line.strip()
    ]


def _int_value(raw_value: object) -> int | None:
    if isinstance(raw_value, bool) or raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _float_value(raw_value: object) -> float:
    if isinstance(raw_value, bool) or raw_value is None:
        return 0.0
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.0


def _extract_pdf_text(raw_pdf: bytes) -> str:
    with pdfplumber.open(BytesIO(raw_pdf)) as pdf:
        return "\n".join(
            page.extract_text(layout=True, x_tolerance=1, y_tolerance=3) or ""
            for page in pdf.pages
        )


def _money_to_float(value: str) -> float:
    return float("".join(ch for ch in value if ch.isdigit() or ch == ".") or 0)


def _int_from_text(value: str) -> int:
    return int("".join(ch for ch in value if ch.isdigit()) or 0)
