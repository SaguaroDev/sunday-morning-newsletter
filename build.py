#!/usr/bin/env python3
"""
Build script for the PUBLIC ESL Weekly Briefing site.
Fetches ESL briefing pages from Notion and generates static HTML.
Run with api_credentials=["external-tools"] for Notion access.

Usage:
  python build.py                                    # Rebuild all from manifest
  python build.py --add-issue ESL_PAGE_ID "Label"    # Add a new issue and rebuild
"""
import asyncio, json, os, re, sys
from pathlib import Path

SITE_DIR = Path(__file__).parent
ISSUES_DIR = SITE_DIR / "issues"
MANIFEST = ISSUES_DIR / "manifest.json"
ISSUES_DIR.mkdir(exist_ok=True)

async def call_tool(source_id, tool_name, arguments):
    proc = await asyncio.create_subprocess_exec(
        "external-tool", "call", json.dumps({"source_id": source_id, "tool_name": tool_name, "arguments": arguments}),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        print(f"Tool error: {stderr.decode()[:200]}", file=sys.stderr)
        return None
    return json.loads(stdout.decode())

async def fetch_page(page_id):
    result = await call_tool("notion_mcp", "notion-fetch", {"id": page_id})
    if not result: return None
    data = result.get("result", result)
    return data if isinstance(data, dict) and (data.get("title") or data.get("text")) else None

def extract_content(text):
    m = re.search(r'<content>\n?([\s\S]*?)\n?</content>', text or '')
    return m.group(1) if m else text or ''

def md_to_html(md):
    if not md: return ''
    html = md.replace('\\$', '$')
    # Tables
    def tbl(match):
        rows = re.findall(r'<tr>([\s\S]*?)</tr>', match.group(1))
        o = '<div class="data-table-wrap"><table class="data-table">'
        for i, row in enumerate(rows):
            cells = re.findall(r'<td>([\s\S]*?)</td>', row)
            if i == 0:
                o += '<thead><tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr></thead><tbody>'
            else:
                o += '<tr>' + ''.join(f'<td class="carrier-name">{c}</td>' if j==0 else f'<td>{c}</td>' for j,c in enumerate(cells)) + '</tr>'
        return o + '</tbody></table></div>'
    html = re.sub(r'<table header-row="true">([\s\S]*?)</table>', tbl, html)
    # Headers
    html = re.sub(r'^## (\d+)\) (.+)$', r'<h3 class="section-heading"><span class="section-num">\1</span>\2</h3>', html, flags=re.M)
    html = re.sub(r'^## (.+)$', r'<h3 class="section-heading">\1</h3>', html, flags=re.M)
    html = re.sub(r'^\*\*What [Cc]hanged[^*]*\*\*', '<h4 class="sub-label">What Changed</h4>', html, flags=re.M)
    html = re.sub(r'^\*\*Why [Ii]t [Mm]atters[^*]*\*\*', '<h4 class="sub-label">Why It Matters</h4>', html, flags=re.M)
    html = re.sub(r'^\*\*([^*]+)\*\*$', r'<h4 class="sub-label">\1</h4>', html, flags=re.M)
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', html)
    lines, result, in_list = html.split('\n'), [], False
    for line in lines:
        s = line.strip()
        if s.startswith('- '):
            if not in_list: result.append('<ul>'); in_list = True
            result.append(f'<li>{s[2:]}</li>')
        else:
            if in_list: result.append('</ul>'); in_list = False
            if s and not s.startswith('<'): result.append(f'<p>{s}</p>')
            elif s: result.append(s)
    if in_list: result.append('</ul>')
    return '\n'.join(result)

def build_page(esl_data, label, idx, total):
    title = (esl_data.get('title','ESL Weekly Briefing') if esl_data else 'ESL Weekly Briefing').lstrip('\U0001f4c8 ')
    content = md_to_html(extract_content(esl_data.get('text',''))) if esl_data else '<p>Not available.</p>'
    url = esl_data.get('url','#') if esl_data else '#'
    is_index = idx == 0
    css = '' if is_index else '../'
    home = '' if is_index else '../'
    prev = f'issues/{idx+1}.html' if idx < total-1 else ''
    nxt = f'issues/{idx-1}.html' if idx > 0 else ('' if is_index else '../index.html')
    if idx == 0: nxt = ''
    pd = ' nav-disabled' if not prev else ''
    nd = ' nav-disabled' if not nxt else ''

    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css}style.css">
</head>
<body>
<header class="site-header"><div class="header-inner">
<div class="logo"><a href="{home}index.html">
<svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-label="Logo"><rect x="2" y="4" width="24" height="18" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M2 7l12 8 12-8" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="22" cy="6" r="4" fill="var(--color-accent)" stroke="var(--color-bg)" stroke-width="1.5"/></svg>
<span>ESL Weekly Briefing</span></a></div>
<div class="header-meta"><div class="issue-nav">
<a class="nav-arrow{pd}" href="{prev or '#'}" title="Older"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg></a>
<span class="edition-date">{label}</span>
<a class="nav-arrow{nd}" href="{nxt or '#'}" title="Newer"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></a>
</div>
<button data-theme-toggle aria-label="Toggle theme"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg></button>
</div></div></header>

<nav class="toc"><div class="toc-inner">
<a href="#top" class="toc-link active">Briefing</a>
<a href="#watchlist" class="toc-link">Watchlist</a>
<a href="https://gemini.google.com/" target="_blank" rel="noopener noreferrer" class="toc-link toc-gemini">Ask Gemini ↗</a>
</div></nav>

<main>
<section id="top" class="issue-hero"><div class="container">
<div class="part-label">Employer Stop-Loss Market Intelligence</div>
<h1>{title}</h1>
<p class="subtitle">Weekly analysis of carrier activity, regulatory developments, and market structure</p>
</div></section>

<article class="briefing-section"><div class="container">
{content}
</div></article>
</main>

<footer class="site-footer"><div class="container">
<div class="gemini-bar">
<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="var(--color-accent)" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>
<span>Have follow-up questions about this briefing?</span>
<a href="https://gemini.google.com/" target="_blank" rel="noopener noreferrer">Open Gemini ↗</a>
</div>
<div class="footer-links"><a href="{url}" target="_blank" rel="noopener">View in Notion</a></div>
<p class="ai-disclosure">AI-assisted research. Data sourced from published carrier filings, industry reports, and regulatory documents. Not independently verified by a credentialed actuary.</p>
<p class="footer-sig">— Computer</p>
</div></footer>

<script>
(function(){{const t=document.querySelector('[data-theme-toggle]'),r=document.documentElement;let d=matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';r.setAttribute('data-theme',d);function u(){{t.innerHTML=d==='dark'?'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>':'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';}};u();t.addEventListener('click',()=>{{d=d==='dark'?'light':'dark';r.setAttribute('data-theme',d);u();}});}})();
</script>
</body></html>'''

def load_manifest():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []

def save_manifest(issues):
    MANIFEST.write_text(json.dumps(issues, indent=2))

async def main():
    args = sys.argv[1:]
    manifest = load_manifest()
    if args and args[0] == '--add-issue':
        eid, label = args[1], args[2] if len(args)>2 else "New Issue"
        if not any(i.get('esl_id')==eid for i in manifest):
            manifest.insert(0, {"esl_id": eid, "label": label})
            save_manifest(manifest)
            print(f"Added: {label}")
    if not manifest:
        manifest = [{"esl_id":"3326f25377ef8184b615d2a63b647298","label":"Mar 23\u201329, 2026"}]
        save_manifest(manifest)
    total = len(manifest)
    for i, issue in enumerate(manifest):
        print(f"Building {i}: {issue['label']}...")
        data = await fetch_page(issue['esl_id']) if issue.get('esl_id') else None
        html = build_page(data, issue['label'], i, total)
        if i == 0: (SITE_DIR/"index.html").write_text(html); print("  → index.html")
        (ISSUES_DIR/f"{i}.html").write_text(html); print(f"  → issues/{i}.html")
    print(f"\nBuilt {total} issue(s).")

if __name__ == "__main__":
    asyncio.run(main())
