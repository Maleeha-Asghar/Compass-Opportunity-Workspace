from tools.content_extractor import clean_html_to_text, extract_tables_as_text


SAMPLE_HTML = """
<html>
  <body>
    <nav>Skip this</nav>
    <main>
      <h1>DAAD Scholarship</h1>
      <p>Application deadline: 2026-08-15. Fully funded for international students.</p>
      <table>
        <tr><th>Program</th><th>Deadline</th></tr>
        <tr><td>STEM Fellowship</td><td>2026-09-01</td></tr>
      </table>
    </main>
  </body>
</html>
"""


def test_extract_tables_as_text() -> None:
    table_data = extract_tables_as_text(SAMPLE_HTML)
    assert "STEM Fellowship" in table_data
    assert "2026-09-01" in table_data


def test_clean_html_to_text_prefers_readable_content() -> None:
    cleaned = clean_html_to_text(SAMPLE_HTML, url="https://www.daad.de/example")
    assert "DAAD Scholarship" in cleaned["text"]
    assert "2026-08-15" in cleaned["text"]
    assert cleaned["table_data"]
    assert cleaned["content_type"] in {"trafilatura", "html"}
