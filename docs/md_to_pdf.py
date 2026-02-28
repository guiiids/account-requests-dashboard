#!/usr/bin/env python3
"""
Markdown → PDF Converter (Preview-Faithful Edition)
====================================================
Produces a PDF that matches the VS Code / GitHub markdown preview as closely
as possible: same font sizes, bold weight, table density, spacing, margins,
page breaks before H2, and full support for GitHub-style alerts.

Usage:
    python docs/md_to_pdf.py docs/onboarding_guide.md

Dependencies (install once):
    pip install markdown2 weasyprint

Supports: headings, bold/italic, tables, fenced code blocks, lists,
          checkboxes, horizontal rules, links, blockquotes, GitHub alerts
          (NOTE/TIP/IMPORTANT/WARNING/CAUTION), embedded images, and emoji.
"""

import markdown2
import os
import re
import sys

from weasyprint import HTML


# ---------------------------------------------------------------------------
# Post-processing: GitHub-style alerts  (> [!NOTE], > [!TIP], etc.)
# ---------------------------------------------------------------------------
# markdown2 renders these as plain <blockquote> with literal [!TYPE] text.
# We transform them into styled alert boxes after HTML conversion.

ALERT_META = {
    "NOTE":      {"icon": "ℹ️",  "color": "#1d76db", "bg": "#dbeafe", "border": "#3b82f6", "title_color": "#1e40af"},
    "TIP":       {"icon": "💡", "color": "#1a7f37", "bg": "#dcfce7", "border": "#22c55e", "title_color": "#166534"},
    "IMPORTANT": {"icon": "❗", "color": "#8250df", "bg": "#f3e8ff", "border": "#a855f7", "title_color": "#6b21a8"},
    "WARNING":   {"icon": "⚠️",  "color": "#9a6700", "bg": "#fef9c3", "border": "#eab308", "title_color": "#854d0e"},
    "CAUTION":   {"icon": "🔴", "color": "#cf222e", "bg": "#fee2e2", "border": "#ef4444", "title_color": "#991b1b"},
}

ALERT_PATTERN = re.compile(
    r'<blockquote>\s*<p>\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*<br\s*/?>\s*',
    re.IGNORECASE,
)

def _replace_alert(match):
    """Replace a matched GitHub alert blockquote opening with styled HTML."""
    kind = match.group(1).upper()
    meta = ALERT_META[kind]
    return (
        f'<div class="gh-alert gh-alert-{kind.lower()}" '
        f'style="border-left:4px solid {meta["border"]}; background:{meta["bg"]}; '
        f'border-radius:0 8px 8px 0; padding:12px 16px; margin:14px 0;">'
        f'<div style="font-weight:700; font-size:9pt; color:{meta["title_color"]}; '
        f'margin-bottom:4px; display:flex; align-items:center; gap:6px;">'
        f'{meta["icon"]} {kind.capitalize()}</div>'
        f'<div style="font-size:9.5pt; color:#1f2937; line-height:1.55;">'
    )


def transform_github_alerts(html: str) -> str:
    """Convert GitHub-style alert blockquotes to styled divs."""
    # First pass: convert the opening pattern
    html = ALERT_PATTERN.sub(_replace_alert, html)
    # Close the divs where the blockquote closes
    # We need to handle the closing </p></blockquote> for alerts
    # Match remaining </p>\n</blockquote> that follow an alert opening
    html = re.sub(
        r'(class="gh-alert[^"]*"[^>]*>.*?)</p>\s*</blockquote>',
        r'\1</div></div>',
        html,
        flags=re.DOTALL,
    )
    return html


# ---------------------------------------------------------------------------
# Post-processing: Mermaid code blocks → descriptive fallback
# ---------------------------------------------------------------------------
def transform_mermaid_blocks(html: str) -> str:
    """Replace mermaid code blocks with a styled placeholder box."""
    def _mermaid_fallback(match):
        code = match.group(1).strip()
        # Extract readable text from the mermaid syntax
        labels = re.findall(r'\["([^"]+)"\]', code)
        if not labels:
            labels = re.findall(r'"([^"]+)"', code)
        
        # Build a simple text description from the mermaid content
        desc_lines = []
        for label in labels:
            clean = label.replace("\\n", " · ")
            desc_lines.append(f"<li>{clean}</li>")
        
        items_html = "\n".join(desc_lines) if desc_lines else "<li>(Diagram)</li>"
        
        return (
            '<div style="background:linear-gradient(135deg, #f0f4ff, #e8eeff); '
            'border:1.5px solid #c7d2fe; border-radius:10px; padding:16px 20px; '
            'margin:14px 0; page-break-inside:avoid;">'
            '<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">'
            '<span style="font-size:14pt;">📊</span>'
            '<span style="font-family:Inter,sans-serif; font-size:9pt; font-weight:700; '
            'color:#4338ca; text-transform:uppercase; letter-spacing:0.05em;">Diagram</span>'
            '</div>'
            f'<ul style="font-family:Inter,sans-serif; font-size:9pt; color:#374151; '
            f'line-height:1.7; margin:0; padding-left:20px;">{items_html}</ul>'
            '</div>'
        )
    
    # Match ```mermaid ... ``` blocks (already converted to <pre><code>)
    html = re.sub(
        r'<pre><code\s+class="mermaid">(.*?)</code></pre>',
        _mermaid_fallback,
        html,
        flags=re.DOTALL,
    )
    # Also catch plain mermaid fenced blocks that markdown2 may render differently
    html = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        _mermaid_fallback,
        html,
        flags=re.DOTALL,
    )
    return html


# ---------------------------------------------------------------------------
# CSS — Faithful to VS Code / GitHub markdown preview
# ---------------------------------------------------------------------------
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Page layout ───────────────────────────────────────────────────────── */
@page {
    size: letter portrait;
    margin: 2cm 2.2cm 2.4cm 2.2cm;

    @bottom-center {
        content: "iLab Account Requests Dashboard — Onboarding Guide";
        font-family: 'Inter', sans-serif;
        font-size: 7pt;
        color: #9ca3af;
        letter-spacing: 0.04em;
    }
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: 'Inter', sans-serif;
        font-size: 7pt;
        color: #9ca3af;
    }
}

/* ── Body ──────────────────────────────────────────────────────────────── */
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 10pt;
    line-height: 1.7;
    color: #1f2937;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
}

/* ── Headings ──────────────────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif;
    line-height: 1.3;
    page-break-after: avoid;
}

h1 {
    font-size: 22pt;
    font-weight: 800;
    color: #0f172a;
    border-bottom: 2.5px solid #0f172a;
    padding-bottom: 10px;
    margin-top: 0;
    margin-bottom: 6px;
    letter-spacing: -0.03em;
}

h2 {
    font-size: 15pt;
    font-weight: 700;
    color: #1e293b;
    border-bottom: 1.5px solid #e2e8f0;
    padding-bottom: 6px;
    margin-top: 30px;
    margin-bottom: 12px;
    letter-spacing: -0.01em;
    page-break-before: always;
}

/* Don't page-break before the first H2 (Table of Contents) */
h2:first-of-type {
    page-break-before: avoid;
}

h3 {
    font-size: 12pt;
    font-weight: 700;
    color: #334155;
    margin-top: 22px;
    margin-bottom: 8px;
}

h4, h5, h6 {
    font-size: 10.5pt;
    font-weight: 600;
    color: #475569;
    margin-top: 16px;
    margin-bottom: 6px;
}

/* ── Paragraphs ────────────────────────────────────────────────────────── */
p {
    margin: 0 0 12px 0;
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
    color: #2563eb;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}

/* ── Horizontal Rule ───────────────────────────────────────────────────── */
hr {
    border: none;
    border-top: 1.5px solid #e5e7eb;
    margin: 24px 0;
}

/* ── Inline Code ───────────────────────────────────────────────────────── */
code {
    font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
    font-size: 8.5pt;
    background: #f1f5f9;
    color: #be185d;
    padding: 1.5px 5px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
}

/* ── Code Blocks ───────────────────────────────────────────────────────── */
pre {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #334155;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 10px 0 16px 0;
    overflow-x: auto;
    page-break-inside: avoid;
}
pre code {
    background: none;
    color: #1e293b;
    border: none;
    padding: 0;
    font-size: 8pt;
    line-height: 1.6;
}

/* ── Tables (high-density, matching preview) ───────────────────────────── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 18px 0;
    font-size: 9pt;
    line-height: 1.5;
    table-layout: fixed;
    word-wrap: break-word;
    overflow-wrap: break-word;
    page-break-inside: auto;
}
thead {
    background: #1e293b;
    color: #f8fafc;
}
th {
    padding: 8px 10px;
    text-align: left;
    font-weight: 700;
    font-size: 8pt;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    border: 1px solid #1e293b;
}
td {
    padding: 7px 10px;
    border: 1px solid #e2e8f0;
    vertical-align: top;
}
tbody tr:nth-child(even) {
    background: #f8fafc;
}

/* ── Lists ─────────────────────────────────────────────────────────────── */
ul, ol {
    margin: 6px 0 12px 0;
    padding-left: 24px;
}
li {
    margin-bottom: 4px;
    line-height: 1.65;
}
li > ul, li > ol {
    margin: 2px 0 2px 0;
}

/* ── Blockquotes ───────────────────────────────────────────────────────── */
blockquote {
    border-left: 4px solid #6366f1;
    margin: 12px 0;
    padding: 10px 16px;
    background: #f5f3ff;
    color: #1f2937;
    border-radius: 0 6px 6px 0;
    font-size: 9.5pt;
}
blockquote p {
    margin: 0 0 4px 0;
}
blockquote strong {
    font-style: normal;
}
blockquote em {
    font-style: italic;
}

/* ── Images ─────────────────────────────────────────────────────────────── */
img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    margin: 10px auto;
    display: block;
}

/* ── Checkboxes ────────────────────────────────────────────────────────── */
li input[type="checkbox"] {
    margin-right: 6px;
}

/* ── TOC links ─────────────────────────────────────────────────────────── */
ol a {
    color: #2563eb;
}
"""


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------
def convert_markdown_to_pdf(md_file: str, pdf_file: str) -> None:
    """Convert a Markdown file to a styled PDF."""
    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Convert Markdown → HTML
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
            "break-on-newline",
        ],
    )

    # Post-processing passes
    html_body = transform_github_alerts(html_body)
    html_body = transform_mermaid_blocks(html_body)

    # Wrap in full HTML document
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

    # Render to PDF — base_url allows resolving relative image paths
    base_url = os.path.dirname(os.path.abspath(md_file))
    HTML(string=html_doc, base_url=base_url).write_pdf(pdf_file)
    
    size_kb = os.path.getsize(pdf_file) / 1024
    print(f"✅  PDF saved → {pdf_file}  ({size_kb:.0f} KB)")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python docs/md_to_pdf.py <markdown_file> [pdf_file]")
        print()
        print("Example:")
        print("  python docs/md_to_pdf.py docs/onboarding_guide.md")
        print("  python docs/md_to_pdf.py docs/onboarding_guide.md output.pdf")
        sys.exit(1)

    md_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else md_path.replace(".md", ".pdf")

    if not os.path.isfile(md_path):
        print(f"❌  File not found: {md_path}")
        sys.exit(1)

    convert_markdown_to_pdf(md_path, pdf_path)
