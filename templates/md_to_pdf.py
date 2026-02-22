#!/usr/bin/env python3
"""
Convert Markdown to PDF using markdown2 + WeasyPrint with professional styling.

Usage:
    python docs/md_to_pdf.py <markdown_file> [pdf_file]

Supports: headings, bold/italic, tables, code blocks, lists, checkboxes,
          horizontal rules, links, blockquotes, and full Unicode.
"""

import markdown2
import os
import sys

from weasyprint import HTML


# ---------------------------------------------------------------------------
# CSS — Professional document styling
# ---------------------------------------------------------------------------
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400;1,8..60,600&family=Inter:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Page layout ───────────────────────────────────────────────────────── */
@page {
    size: letter landscape;
    margin: 1.8cm 2cm 2cm 2cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-family: 'Inter', sans-serif;
        font-size: 7.5pt;
        color: #9ca3af;
        letter-spacing: 0.03em;
    }
}

/* ── Body ──────────────────────────────────────────────────────────────── */
body {
    font-family: 'Source Serif 4', 'Georgia', 'Times New Roman', serif;
    font-size: 11.5pt;
    line-height: 1.8;
    color: #111827;
    text-rendering: optimizeLegibility;
}

/* ── Headings (Inter — clean sans for contrast with serif body) ─────────── */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    line-height: 1.25;
    page-break-after: avoid;
}
h1 {
    font-size: 24pt;
    font-weight: 800;
    color: #0f2d5c;
    border-bottom: 3px solid #0f2d5c;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 20px;
    letter-spacing: -0.02em;
}
h2 {
    font-size: 16pt;
    font-weight: 700;
    color: #1e3a6e;
    border-bottom: 1.5px solid #d1d9e6;
    padding-bottom: 5px;
    margin-top: 28px;
    margin-bottom: 12px;
    letter-spacing: -0.01em;
}
h3 {
    font-size: 13pt;
    font-weight: 700;
    color: #1f2937;
    margin-top: 22px;
    margin-bottom: 8px;
}
h4, h5, h6 {
    font-size: 11.5pt;
    font-weight: 600;
    color: #374151;
    margin-top: 16px;
    margin-bottom: 5px;
}

/* ── Paragraphs ────────────────────────────────────────────────────────── */
p {
    margin: 0 0 14px 0;
    orphans: 3;
    widows: 3;
}

/* ── Bold & Italic ─────────────────────────────────────────────────────── */
strong {
    font-weight: 700;
    color: #0f172a;
}
em {
    font-style: italic;
    color: #374151;
}

/* ── Links ─────────────────────────────────────────────────────────────── */
a {
    color: #1d4ed8;
    text-decoration: none;
}

/* ── Horizontal Rule ───────────────────────────────────────────────────── */
hr {
    border: none;
    border-top: 1.5px solid #e5e7eb;
    margin: 24px 0;
}

/* ── Inline Code ───────────────────────────────────────────────────────── */
code {
    font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 9pt;
    background: #f1f5f9;
    color: #be185d;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
}

/* ── Code Blocks ───────────────────────────────────────────────────────── */
pre {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #1e3a6e;
    border-radius: 6px;
    padding: 13px 16px;
    margin: 12px 0 16px 0;
    overflow-x: auto;
    page-break-inside: avoid;
}
pre code {
    background: none;
    color: #1e293b;
    border: none;
    padding: 0;
    font-size: 8.5pt;
    line-height: 1.6;
}

/* ── Tables ─────────────────────────────────────────────────────────────── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0 20px 0;
    font-family: 'Inter', sans-serif;   /* tables stay crisp with sans-serif */
    font-size: 9pt;
    line-height: 1.45;
    table-layout: fixed;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
thead {
    background: #0f2d5c;
    color: #f0f4ff;
}
th {
    padding: 9px 10px;
    text-align: left;
    font-weight: 700;
    font-size: 8.5pt;
    letter-spacing: 0.01em;
    border: 1px solid #0f2d5c;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
td {
    padding: 7px 10px;
    border: 1px solid #d1d9e6;
    word-wrap: break-word;
    overflow-wrap: break-word;
    vertical-align: top;
}
tbody tr:nth-child(even) {
    background: #f8fafc;
}
tbody tr:hover {
    background: #eef2ff;
}

/* ── Lists ─────────────────────────────────────────────────────────────── */
ul, ol {
    margin: 8px 0 14px 0;
    padding-left: 26px;
}
li {
    margin-bottom: 6px;
    line-height: 1.7;
}

/* ── Blockquotes ───────────────────────────────────────────────────────── */
blockquote {
    border-left: 4px solid #1e3a6e;
    margin: 14px 0;
    padding: 10px 18px;
    background: #f0f4ff;
    color: #1f2937;
    border-radius: 0 6px 6px 0;
    font-style: italic;
}
blockquote p {
    margin: 0;
}
blockquote strong {
    font-style: normal;
}

/* ── Checkboxes ────────────────────────────────────────────────────────── */
li input[type="checkbox"] {
    margin-right: 7px;
}
"""


def convert_markdown_to_pdf(md_file, pdf_file):
    """Convert a Markdown file to a styled PDF."""
    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Convert Markdown → HTML with extras
    html_body = markdown2.markdown(
        md_content,
        extras=[
            "fenced-code-blocks",
            "tables",
            "header-ids",
            "strike",
            "task_list",
            "cuddled-lists",
            "code-friendly",
            "metadata",
        ],
    )

    # Wrap in a full HTML document with embedded CSS
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    # Render to PDF
    base_url = os.path.dirname(os.path.abspath(md_file))
    HTML(string=html_doc, base_url=base_url).write_pdf(pdf_file)
    print(f"PDF saved to {pdf_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python md_to_pdf.py <markdown_file> [pdf_file]")
        sys.exit(1)

    md_file = sys.argv[1]
    pdf_file = sys.argv[2] if len(sys.argv) > 2 else md_file.replace(".md", ".pdf")

    convert_markdown_to_pdf(md_file, pdf_file)
