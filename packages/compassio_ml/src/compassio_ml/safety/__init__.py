"""Defensive readers for untrusted source files (ZIP archives, XML, spreadsheets).

Nothing in this package extracts archives to disk, executes embedded content,
resolves XML entities, follows spreadsheet external links or contacts URLs.
"""

from compassio_ml.safety.archive import (
    ArchiveLimits,
    ArchiveMember,
    CorruptArchiveError,
    UnsafeArchiveError,
    inspect_zip,
    read_zip_member,
)
from compassio_ml.safety.spreadsheet import (
    MacroEnabledWorkbookError,
    SheetTable,
    list_sheets,
    read_sheet,
)
from compassio_ml.safety.xml import InvalidXMLError, iter_xml_elements

__all__ = [
    "ArchiveLimits",
    "ArchiveMember",
    "CorruptArchiveError",
    "InvalidXMLError",
    "MacroEnabledWorkbookError",
    "SheetTable",
    "UnsafeArchiveError",
    "inspect_zip",
    "iter_xml_elements",
    "list_sheets",
    "read_sheet",
    "read_zip_member",
]
