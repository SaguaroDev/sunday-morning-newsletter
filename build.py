#!/usr/bin/env python3
"""
Build script for Sunday Morning Newsletter static site.
Fetches pages from Notion and generates static HTML.
Run with api_credentials=["external-tools"] for Notion access.

Usage:
  python build.py                          # Rebuild index from issues/manifest.json
  python build.py --add-issue ESL_ID PAPER_ID "Label"  # Add a new issue and rebuild
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

SITE_DIR = Path(__file__).parent
ISSUES_DIR = SITE_DIR / "issues"
MANIFEST_PATH = ISSUES_DIR / "manifest.json"


async def call_tool(source_id, tool_name, arguments):
    proc = await asyncio.create_subprocess_exec(
        "external-tool", "call", json.dumps({
            "source_id": source_id, "tool_name": tool_name, "arguments": arguments,
        }),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        print(f"Tool error: {stderr.decode()[:200]}", file=sys.stderr)
        return None
    return json.loads(stdout.decode())


async def fetch_notion_page(page_id):
    """Fetch a Notion page and return {title, text, url}."""
    result = await call_tool("notion_mcp", "notion-fetch", {"id": page_id})
    if not result:
        return None
    data = result.get("result", result)
    if isinstance(data, dict) and (data.get("title") or data.get("text")):
        return data
    return None


def extract_content(text):
    """Extract the <content> block from Notion page text."""
    m = re.search(r'<content>\n?([\s\S]*?)\n?</content>', text or '')
    return m.group(1) if m else text or ''


def notion_md_to_html(md):
    """Convert Notion-flavored markdown to HTML."""
    if not md:
        return ''
    html = md

    # Fix escaped dollars
    html = html.replace('\\$', '$')

    # Notion tables → HTML tables
    def convert_table(match):
        inner = match.group(1)
        rows = re.findall(r'<tr>([\s\S]*?)</tr>', inner)
        out = '<div class="data-table-wrap"><table class="data-table">'
        for i, row in enumerate(rows):
            cells = re.findall(r'<td>([\s\S]*?)</td>', row)
            if i == 0:
                out += '<thead><tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr></thead><tbody>'
            else:
                out += '<tr>' + ''.join(
                    f'<td class="carrier-name">{c}</td>' if j == 0 else f'<td>{c}</td>'
                    for j, c in enumerate(cells)
                ) + '</tr>'
        out += '</tbody></table></div>'
        return out

    html = re.sub(r'<table header-row="true">([\s\S]*?)</table>', convert_table, html)

    # Section headers with numbers
    html = re.sub(r'^## (\d+)\) (.+)$', r'<h3 class="section-heading"><span class="section-num">\1</span>\2</h3>', html, flags=re.M)
    html = re.sub(r'^## (.+)$', r'<h3 class="section-heading">\1</h3>', html, flags=re.M)

    # Sub-labels
    html = re.sub(r'^\*\*What [Cc]hanged[^*]*\*\*', '<h4 class="sub-label">What Changed</h4>', html, flags=re.M)
    html = re.sub(r'^\*\*Why [Ii]t [Mm]atters[^*]*\*\*', '<h4 class="sub-label">Why It Matters</h4>', html, flags=re.M)
    html = re.sub(r'^\*\*([^*]+)\*\*$', r'<h4 class="sub-label">\1</h4>', html, flags=re.M)

    # Inline formatting
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', html)

    # Bullet lists
    lines = html.split('\n')
    result = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- '):
            if not in_list:
                result.append('<ul>')
                in_list = True
            result.append(f'<li>{stripped[2:]}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            if stripped and not stripped.startswith('<'):
                result.append(f'<p>{stripped}</p>')
            elif stripped:
                result.append(stripped)
    if in_list:
        result.append('</ul>')

    return '\n'.join(result)


def build_issue_html(esl_data, paper_data, issue_label, issue_index, total_issues):
    """Generate the full HTML page for one issue."""
    esl_title = (esl_data.get('title', 'ESL Weekly Briefing') if esl_data else 'ESL Weekly Briefing').lstrip('📈 ')
    esl_content = notion_md_to_html(extract_content(esl_data.get('text', ''))) if esl_data else '<p class="muted">Not available.</p>'
    esl_url = esl_data.get('url', '#') if esl_data else '#'

    paper_title = paper_data.get('title', 'Sunday Morning Paper') if paper_data else 'Sunday Morning Paper'
    paper_content = notion_md_to_html(extract_content(paper_data.get('text', ''))) if paper_data else '<p class="muted">Not available.</p>'
    paper_url = paper_data.get('url', '#') if paper_data else '#'

    # Navigation links
    prev_link = f'issues/{issue_index + 1}.html' if issue_index < total_issues - 1 else ''
    next_link = f'issues/{issue_index - 1}.html' if issue_index > 0 else ''
    if issue_index == 0:
        next_link = ''  # newest, no next
    # For the index page (issue 0), prev goes to issues/1.html
    # For issue pages, adjust relative paths
    is_index = issue_index == 0

    prev_disabled = 'disabled' if not prev_link else ''
    next_disabled = 'disabled' if not next_link else ''

    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sunday Morning Newsletter — {issue_label}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{"" if is_index else "../"}style.css">
</head>
<body>

<header class="site-header">
  <div class="header-inner">
    <div class="logo">
      <a href="{"" if is_index else "../"}index.html" style="display:flex;align-items:center;gap:10px;color:inherit;text-decoration:none;">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-label="Newsletter logo">
          <rect x="2" y="4" width="24" height="18" rx="3" stroke="currentColor" stroke-width="1.8"/>
          <path d="M2 7l12 8 12-8" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
          <circle cx="22" cy="6" r="4" fill="var(--color-accent)" stroke="var(--color-bg)" stroke-width="1.5"/>
        </svg>
        <span>Sunday Morning Newsletter</span>
      </a>
    </div>
    <div class="header-meta">
      <div class="issue-nav">
        <a class="nav-arrow{' nav-disabled' if prev_disabled else ''}" href="{prev_link or '#'}" title="Older issue">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
        </a>
        <span class="edition-date">{issue_label}</span>
        <a class="nav-arrow{' nav-disabled' if next_disabled else ''}" href="{next_link or '#'}" title="Newer issue">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </a>
      </div>
      <button data-theme-toggle aria-label="Switch to light mode">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
      </button>
    </div>
  </div>
</header>

<nav class="toc">
  <div class="toc-inner">
    <a href="#esl" class="toc-link active">ESL Briefing</a>
    <a href="#personal" class="toc-link">Weekly Review</a>
    <a href="#deadlines" class="toc-link">Deadlines</a>
    <a href="https://gemini.google.com/" target="_blank" rel="noopener noreferrer" class="toc-link toc-gemini">Ask Gemini ↗</a>
  </div>
</nav>

<main>
  <section id="esl" class="part-banner esl-banner">
    <div class="container">
      <span class="part-label">Part 1</span>
      <h2 class="part-title">{esl_title}</h2>
      <p class="part-subtitle">Employer Stop-Loss Market Intelligence</p>
    </div>
  </section>

  <article class="briefing-section">
    <div class="container">{esl_content}</div>
  </article>

  <section id="personal" class="part-banner personal-banner">
    <div class="container">
      <span class="part-label">Part 2</span>
      <h2 class="part-title">{paper_title}</h2>
      <p class="part-subtitle">Week at a Glance</p>
    </div>
  </section>

  <article class="briefing-section" id="deadlines">
    <div class="container">{paper_content}</div>
  </article>
</main>

<footer class="site-footer">
  <div class="container">
    <div class="gemini-bar">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="var(--color-accent)" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
      </svg>
      <span>Have follow-up questions about this briefing?</span>
      <a href="https://gemini.google.com/" target="_blank" rel="noopener noreferrer">Open Gemini ↗</a>
    </div>
    <div class="footer-links">
      <a href="{esl_url}" target="_blank" rel="noopener">ESL Briefing in Notion</a>
      <span class="footer-sep">·</span>
      <a href="{paper_url}" target="_blank" rel="noopener">Personal Paper in Notion</a>
    </div>
    <p class="ai-disclosure">AI-assisted research. Data sourced from published carrier filings, industry reports, and regulatory documents. Not independently verified by a credentialed actuary.</p>
    <p class="footer-sig">— Computer</p>
  </div>
</footer>

<script>
(function(){{
  const t=document.querySelector('[data-theme-toggle]'),r=document.documentElement;
  let d=matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';
  r.setAttribute('data-theme',d);
  function u(){{t.innerHTML=d==='dark'?'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>':'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';}}
  u();t.addEventListener('click',()=>{{d=d==='dark'?'light':'dark';r.setAttribute('data-theme',d);u();}});
}})();
const secs=document.querySelectorAll('[id]'),links=document.querySelectorAll('.toc-link:not(.toc-gemini)');
new IntersectionObserver(es=>{{es.forEach(e=>{{if(e.isIntersecting){{links.forEach(l=>l.classList.remove('active'));const l=document.querySelector(`.toc-link[href="#${{e.target.id}}"]`);if(l)l.classList.add('active');}}}});}},{{rootMargin:'-100px 0px -60% 0px'}}).observe(...secs);
</script>
</body>
</html>'''


def load_manifest():
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return []


def save_manifest(issues):
    MANIFEST_PATH.write_text(json.dumps(issues, indent=2))


async def main():
    args = sys.argv[1:]

    manifest = load_manifest()

    if args and args[0] == '--add-issue':
        esl_id = args[1] if len(args) > 1 else None
        paper_id = args[2] if len(args) > 2 else None
        label = args[3] if len(args) > 3 else "New Issue"

        # Check for duplicates
        for issue in manifest:
            if issue.get('esl_id') == esl_id and issue.get('paper_id') == paper_id:
                print(f"Issue already exists: {label}")
                return

        manifest.insert(0, {
            "esl_id": esl_id,
            "paper_id": paper_id,
            "label": label,
        })
        save_manifest(manifest)
        print(f"Added issue: {label}")

    # If manifest is empty, seed with the known first issue
    if not manifest:
        manifest = [{
            "esl_id": "3326f25377ef8184b615d2a63b647298",
            "paper_id": "3326f25377ef813abde2c9034046ad4c",
            "label": "Mar 23\u201329, 2026",
        }]
        save_manifest(manifest)

    # Build each issue
    total = len(manifest)
    for i, issue in enumerate(manifest):
        print(f"Building issue {i}: {issue['label']}...")

        esl_data = None
        paper_data = None

        if issue.get('esl_id'):
            esl_data = await fetch_notion_page(issue['esl_id'])
        if issue.get('paper_id'):
            paper_data = await fetch_notion_page(issue['paper_id'])

        html = build_issue_html(esl_data, paper_data, issue['label'], i, total)

        if i == 0:
            # Latest issue is index.html
            (SITE_DIR / "index.html").write_text(html)
            print(f"  → index.html")
        
        # Also save as issues/N.html
        (ISSUES_DIR / f"{i}.html").write_text(html)
        print(f"  → issues/{i}.html")

    print(f"\nBuilt {total} issue(s). Ready to push.")


if __name__ == "__main__":
    asyncio.run(main())
