#!/usr/bin/env python3
"""
report_common.py — Shared page shell (CSS + header + nav + footer) for every
generate_*_report.py script. Five generators render into the same report/
directory and cross-link each other; keeping the shell in one place means the
nav links can't drift out of sync page-by-page.
"""

# (href, label) for every page in report/, in the order they should appear
# in the nav bar and on the index.html landing page.
NAV_PAGES = [
    ("index.html", "Overview"),
    ("regridding.html", "Regridding"),
    ("crocodash.html", "CrocoDash"),
    ("mom6_forge.html", "mom6_forge"),
    ("health.html", "Data access health"),
    ("mom6_scaling.html", "MOM6 scaling"),
]

BASE_CSS = """
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 0; background: #f5f6fa; color: #222; }
  header { background: #1a3a5c; color: #fff; padding: 1.5rem 2rem; }
  header h1 { margin: 0 0 0.25rem; font-size: 1.6rem; }
  header p { margin: 0 0 0.5rem; }
  header nav { font-size: 0.82rem; }
  header nav a { color: #9fc3e8; margin-right: 0.9rem; }
  section { padding: 1.5rem 2rem 0.5rem; }
  section h2 { font-size: 1.2rem; border-bottom: 2px solid #c8d6e5;
                padding-bottom: 0.4rem; margin-bottom: 1rem; color: #1a3a5c; }
  .card { background: #fff; border-radius: 8px; padding: 1rem 1.25rem;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 1.25rem; overflow-x: auto; }
  .card h3 { margin: 0 0 0.6rem; font-size: 0.95rem; color: #333;
              font-family: 'SFMono-Regular', Consolas, monospace; }
  .card p { margin: 0; color: #555; font-size: 0.88rem; }
  table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
  th, td { text-align: right; padding: 0.3rem 0.6rem; }
  th:first-child, td:first-child { text-align: left; }
  thead th { border-bottom: 2px solid #c8d6e5; color: #555; }
  tbody tr:nth-child(even) { background: #f7f9fc; }
  .ok { color: #1a7a3e; font-weight: 600; }
  .fail { color: #b30000; font-weight: 600; }
  footer { padding: 1.5rem 2rem; font-size: 0.8rem; color: #888; }
"""

HEATMAP_CSS = """
  #regrid-cost { background: #fff; border-bottom: 1px solid #dde4ee; }
  .hm-legend-label { display: flex; align-items: center; gap: 0.5rem;
                       font-size: 0.78rem; color: #555; margin: 0 0 1.25rem; }
  .hm-legend-bar { display: inline-block; width: 140px; height: 10px;
                     border-radius: 5px; }
  .hm-group { margin-bottom: 1.5rem; }
  .hm-group h3 { font-size: 0.95rem; color: #333; margin: 0 0 0.15rem; }
  .hm-group-sub { font-size: 0.75rem; color: #777; margin: 0 0 0.75rem; }
  .hm-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
              gap: 1.25rem; }
  .hm-panel { background: #fff; border-radius: 8px; padding: 0.9rem 1rem;
               box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
  .hm-panel h4 { margin: 0 0 0.6rem; font-size: 0.82rem; color: #333;
                  font-family: 'SFMono-Regular', Consolas, monospace; font-weight: 600; }
  table.heatmap { border-collapse: separate; border-spacing: 3px; width: 100%; }
  table.heatmap th { font-size: 0.68rem; font-weight: 500; color: #777;
                      text-align: center; padding: 0.15rem; }
  table.heatmap td.hm-cell { text-align: center; font-variant-numeric: tabular-nums;
                              font-size: 0.7rem; padding: 0.5rem 0.3rem; border-radius: 4px; }
  table.heatmap td.hm-empty { color: #bbb; text-align: center; }
"""

LINECHART_CSS = """
  .linechart { width: 100%; max-width: 480px; height: auto; display: block; }
  .lc-sub { font-size: 0.75rem; color: #777; margin: -0.4rem 0 0.75rem; }
  .lc-axis { font-size: 9px; fill: #898781; font-family: -apple-system, sans-serif; }
  .lc-value { font-size: 10px; fill: #333; font-variant-numeric: tabular-nums;
               font-family: -apple-system, sans-serif; }
"""


def render_nav(current):
    """Nav links to every report page except the one being rendered."""
    links = [
        f'<a href="{href}">{label}</a>' for href, label in NAV_PAGES if href != current
    ]
    return "".join(links)


def page_shell(current, title, subtitle_html, body_html, footer_text, extra_css=""):
    """Wrap body_html in the common doctype/head/header/footer. `current` is
    the page's own filename (e.g. "regridding.html"), used to build the nav
    bar and to exclude the self-link."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{BASE_CSS}{extra_css}</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p>{subtitle_html}</p>
  <nav>{render_nav(current)}</nav>
</header>
{body_html}
<footer>{footer_text}</footer>
</body>
</html>
"""
