from typing import Any

from bs4 import BeautifulSoup


def extract_text_with_trafilatura(html: str, url: str | None = None) -> str:
    try:
        import trafilatura
    except ImportError:
        return ""
    downloaded = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    return " ".join((downloaded or "").split())


def extract_tables_as_text(html: str, *, max_tables: int = 3, max_rows: int = 20) -> str:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[str] = []
    for table_index, table in enumerate(soup.find_all("table")[:max_tables]):
        rows: list[str] = []
        for row in table.find_all("tr")[:max_rows]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            blocks.append(f"Table {table_index + 1}:\n" + "\n".join(rows))
    return "\n\n".join(blocks)


def clean_html_to_text(html: str, url: str | None = None) -> dict[str, Any]:
    trafilatura_text = extract_text_with_trafilatura(html, url=url)
    table_data = extract_tables_as_text(html)
    if trafilatura_text:
        text = trafilatura_text
        content_type = "trafilatura"
    else:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        content_type = "html"
    return {
        "text": text,
        "table_data": table_data,
        "content_type": content_type,
    }
