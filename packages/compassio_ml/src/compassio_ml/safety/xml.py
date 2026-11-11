"""Streaming XML parsing with DTDs, entities and external references forbidden."""

from collections.abc import Iterator
from pathlib import Path
from xml.etree.ElementTree import Element, ParseError

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import iterparse


class InvalidXMLError(ValueError):
    """The XML is malformed or uses forbidden constructs (DTD, entities, external refs)."""


def iter_xml_elements(path: str | Path, tag: str) -> Iterator[Element]:
    """Yield each complete ``tag`` element, clearing it afterwards to bound memory.

    Callers must extract what they need before advancing the iterator.

    Raises:
        FileNotFoundError: ``path`` does not exist.
        InvalidXMLError: malformed XML or a DTD/entity/external reference.
    """
    xml_path = Path(path)
    if not xml_path.is_file():
        raise FileNotFoundError(f"XML file not found: {xml_path}")
    try:
        for _event, element in iterparse(
            str(xml_path),
            events=("end",),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        ):
            if element.tag == tag:
                yield element
                element.clear()
    except ParseError as exc:
        raise InvalidXMLError(f"Malformed XML in {xml_path}: {exc}") from exc
    except DefusedXmlException as exc:
        raise InvalidXMLError(f"Forbidden XML construct in {xml_path}: {exc!r}") from exc
