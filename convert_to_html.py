import json, re, html as h

with open("/Users/nbaxter/Downloads/neil-fs-hol/scripts/risk_hol_workbook.ipynb") as f:
    nb = json.load(f)

def md_to_html(md):
    text = h.escape(md)
    text = re.sub(r'^---\s*$', '<hr>', text, flags=re.MULTILINE)
    text = re.sub(r'^######\s+(.+)$', r'<h6>\1</h6>', text, flags=re.MULTILINE)
    text = re.sub(r'^#####\s+(.+)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
    text = re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'^\|(.+)$', lambda m: m.group(0), text, flags=re.MULTILINE)
    lines = text.split('\n')
    result = []
    in_table = False
    in_list = False
    table_rows = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            if not in_table:
                if in_list:
                    result.append('</ul>')
                    in_list = False
                in_table = True
                table_rows = []
            table_rows.append(stripped)
            continue
        else:
            if in_table:
                result.append(render_table(table_rows))
                in_table = False
                table_rows = []
        if re.match(r'^(\d+)\.\s+', stripped):
            if in_list:
                result.append('</ul>')
                in_list = False
            content = re.sub(r'^(\d+)\.\s+', '', stripped)
            result.append(f'<p style="margin-left:1.5rem;">{content}</p>')
        elif stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                result.append('<ul>')
                in_list = True
            result.append(f'<li>{stripped[2:]}</li>')
        elif stripped.startswith('<h') or stripped == '<hr>' or stripped.startswith('&gt;'):
            if in_list:
                result.append('</ul>')
                in_list = False
            if stripped.startswith('&gt;'):
                result.append(f'<blockquote>{stripped[5:]}</blockquote>')
            else:
                result.append(stripped)
        elif stripped == '':
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append('')
        else:
            if in_list:
                result.append(f'<li>{stripped}</li>')
            else:
                result.append(f'<p>{stripped}</p>')
    if in_list:
        result.append('</ul>')
    if in_table:
        result.append(render_table(table_rows))
    return '\n'.join(result)

def render_table(rows):
    if len(rows) < 2:
        return ''
    parts = ['<div class="table-wrapper"><table class="data-table">']
    headers = [c.strip() for c in rows[0].strip('|').split('|')]
    parts.append('<thead><tr>')
    for hdr in headers:
        parts.append(f'<th>{hdr}</th>')
    parts.append('</tr></thead><tbody>')
    for row in rows[2:]:
        cols = [c.strip() for c in row.strip('|').split('|')]
        parts.append('<tr>')
        for col in cols:
            parts.append(f'<td>{col}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')
    return '\n'.join(parts)

sections = []
current_section = None
section_num = 0

for cell in nb['cells']:
    src = ''.join(cell['source'])
    name = cell.get('metadata', {}).get('name', '')

    if cell['cell_type'] == 'markdown':
        if re.match(r'^---\s*\n##\s+', src) or (name and re.match(r'^\d+\s+·', name)):
            if current_section:
                sections.append(current_section)
            section_num += 1
            title_match = re.search(r'^##\s+(.+)$', src, re.MULTILINE)
            title = title_match.group(1) if title_match else name
            current_section = {'num': section_num, 'title': title, 'cells': []}
        if current_section is None:
            current_section = {'num': 0, 'title': 'Introduction', 'cells': []}
        current_section['cells'].append({'type': 'markdown', 'source': src, 'name': name})
    else:
        if current_section is None:
            current_section = {'num': 0, 'title': 'Introduction', 'cells': []}
        lang = cell.get('metadata', {}).get('language', 'sql')
        current_section['cells'].append({'type': 'code', 'source': src, 'name': name, 'language': lang})

if current_section:
    sections.append(current_section)

nav_items = []
for sec in sections:
    if sec['num'] > 0:
        nav_items.append(f'<a class="step-nav-item" href="#section-{sec["num"]}"><span class="step-indicator">{sec["num"]}</span>{h.escape(sec["title"][:30])}</a>')

cell_html_parts = []
for sec in sections:
    if sec['num'] > 0:
        cell_html_parts.append(f'<div class="section-divider" id="section-{sec["num"]}"></div>')
    for cell in sec['cells']:
        if cell['type'] == 'markdown':
            cell_html_parts.append(f'<div class="nb-cell nb-markdown">{md_to_html(cell["source"])}</div>')
        else:
            escaped = h.escape(cell['source'])
            label = cell.get('language', 'sql').upper()
            cell_html_parts.append(f'''<div class="nb-cell nb-code">
<div class="code-block"><div class="code-header"><span class="code-language">{label}</span><div class="code-actions"><button onclick="copyCode(this)" title="Copy"><svg viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg></button></div></div>
<pre><code>{escaped}</code></pre></div></div>''')

body_content = '\n'.join(cell_html_parts)
sidebar_nav = '\n'.join(nav_items)

html_out = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Zero to Snowflake: Financial Services Risk Management | Hands-On Lab</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="https://www.logo.wine/a/logo/Snowflake_Inc./Snowflake_Inc.-Logo.wine.svg">
<style>
:root {{
    --sf-blue-primary: #29B5E8;
    --sf-blue-dark: #1565C0;
    --sf-blue-light: #E3F2FD;
    --sf-green: #51cf66;
    --sf-red: #ff6b6b;
    --sf-yellow: #ffd43b;
    --sf-orange: #ff922b;
    --gray-50: #f8fafc;
    --gray-100: #f1f5f9;
    --gray-200: #e2e8f0;
    --gray-300: #cbd5e1;
    --gray-400: #94a3b8;
    --gray-500: #64748b;
    --gray-600: #475569;
    --gray-700: #334155;
    --gray-800: #1e293b;
    --gray-900: #0f172a;
    --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    --header-height: 64px;
    --sidebar-width: 260px;
    --content-max-width: 900px;
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-full: 9999px;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1);
    --transition-fast: 150ms ease;
    --transition-normal: 250ms ease;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; scroll-padding-top: calc(var(--header-height) + 1.5rem); }}
body {{ font-family: var(--font-family); font-size: 16px; line-height: 1.6; color: var(--gray-800); background: var(--gray-50); -webkit-font-smoothing: antialiased; }}
a {{ color: var(--sf-blue-primary); text-decoration: none; }}
a:hover {{ color: var(--sf-blue-dark); }}

.hol-header {{ position: fixed; top: 0; left: 0; right: 0; height: var(--header-height); background: white; border-bottom: 1px solid var(--gray-200); z-index: 100; box-shadow: var(--shadow-sm); }}
.header-container {{ max-width: 1400px; margin: 0 auto; height: 100%; display: flex; align-items: center; padding: 0 2rem; gap: 1rem; }}
.snowflake-logo {{ height: 40px; width: auto; }}
.logo-divider {{ width: 1px; height: 24px; background: var(--gray-300); }}
.hol-badge {{ background: linear-gradient(135deg, var(--sf-blue-primary), var(--sf-blue-dark)); color: white; padding: 0.25rem 0.5rem; border-radius: var(--radius-sm); font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}

.sidebar {{ position: fixed; left: 0; top: var(--header-height); bottom: 0; width: var(--sidebar-width); background: white; border-right: 1px solid var(--gray-200); padding: 1.5rem 1rem; overflow-y: auto; z-index: 50; }}
.sidebar h3 {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; color: var(--gray-400); margin-bottom: 1rem; }}
.steps-nav {{ display: flex; flex-direction: column; gap: 0.25rem; }}
.step-nav-item {{ display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.75rem; border-radius: var(--radius-md); color: var(--gray-600); font-size: 0.8rem; text-decoration: none; transition: all var(--transition-fast); }}
.step-nav-item:hover {{ background: var(--gray-100); color: var(--gray-800); }}
.step-nav-item .step-indicator {{ width: 22px; height: 22px; border-radius: 50%; border: 2px solid currentColor; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; font-weight: 600; flex-shrink: 0; }}

.main-content {{ margin-left: var(--sidebar-width); margin-top: var(--header-height); padding: 2rem 3rem; max-width: calc(var(--content-max-width) + var(--sidebar-width) + 6rem); }}

.nb-cell {{ margin-bottom: 1.5rem; }}
.nb-markdown h1 {{ font-size: 2rem; font-weight: 700; color: var(--gray-900); margin: 2rem 0 1rem; }}
.nb-markdown h2 {{ font-size: 1.5rem; font-weight: 700; color: var(--sf-blue-dark); margin: 2.5rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 3px solid var(--sf-blue-primary); }}
.nb-markdown h3 {{ font-size: 1.2rem; font-weight: 600; color: var(--gray-800); margin: 1.5rem 0 0.75rem; }}
.nb-markdown h4 {{ font-size: 1.05rem; font-weight: 600; color: var(--gray-700); margin: 1rem 0 0.5rem; }}
.nb-markdown p {{ color: var(--gray-700); margin-bottom: 0.75rem; line-height: 1.7; }}
.nb-markdown strong {{ color: var(--gray-900); }}
.nb-markdown code {{ background: var(--gray-100); padding: 2px 6px; border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 0.85rem; color: var(--sf-blue-dark); }}
.nb-markdown ul {{ padding-left: 1.5rem; margin-bottom: 1rem; }}
.nb-markdown li {{ color: var(--gray-700); margin-bottom: 0.25rem; }}
.nb-markdown hr {{ border: none; border-top: 2px solid var(--gray-200); margin: 2rem 0; }}
.nb-markdown blockquote {{ border-left: 4px solid var(--sf-blue-primary); background: var(--sf-blue-light); padding: 1rem 1.5rem; border-radius: 0 var(--radius-md) var(--radius-md) 0; margin: 1rem 0; }}

.table-wrapper {{ overflow-x: auto; margin: 1rem 0; border-radius: var(--radius-md); border: 1px solid var(--gray-200); }}
.data-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
.data-table th {{ background: var(--gray-100); padding: 0.75rem 1rem; text-align: left; font-weight: 600; color: var(--gray-700); border-bottom: 2px solid var(--gray-300); }}
.data-table td {{ padding: 0.75rem 1rem; border-bottom: 1px solid var(--gray-200); color: var(--gray-600); }}
.data-table tbody tr:hover {{ background: var(--gray-50); }}

.code-block {{ background: var(--gray-900); border-radius: var(--radius-md); overflow: hidden; }}
.code-header {{ display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 1rem; background: var(--gray-800); border-bottom: 1px solid var(--gray-700); }}
.code-language {{ color: var(--gray-400); font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }}
.code-actions {{ display: flex; gap: 0.25rem; }}
.code-actions button {{ background: transparent; border: none; padding: 0.25rem; cursor: pointer; color: var(--gray-400); border-radius: var(--radius-sm); transition: all var(--transition-fast); }}
.code-actions button:hover {{ background: var(--gray-700); color: var(--sf-blue-primary); }}
.code-actions button svg {{ width: 18px; height: 18px; fill: currentColor; }}
.code-block pre {{ margin: 0; padding: 1.25rem; overflow-x: auto; }}
.code-block code {{ font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.6; color: var(--gray-100); }}

.section-divider {{ height: 0; margin: 0; }}

@media (max-width: 992px) {{
    .sidebar {{ display: none; }}
    .main-content {{ margin-left: 0; }}
}}
@media print {{
    .sidebar, .code-actions {{ display: none !important; }}
    .main-content {{ margin-left: 0; }}
    .code-block {{ background: white !important; border: 1px solid #ccc; }}
    .code-block code {{ color: black !important; }}
}}
</style>
</head>
<body>

<header class="hol-header">
<div class="header-container">
    <img src="https://www.logo.wine/a/logo/Snowflake_Inc./Snowflake_Inc.-Logo.wine.svg" alt="Snowflake" class="snowflake-logo">
    <span class="logo-divider"></span>
    <span class="hol-badge">Hands-On Lab</span>
</div>
</header>

<aside class="sidebar">
<h3>Sections</h3>
<nav class="steps-nav">
{sidebar_nav}
</nav>
</aside>

<main class="main-content">
{body_content}
</main>

<script>
function copyCode(button) {{
    const block = button.closest('.code-block');
    const code = block.querySelector('code');
    navigator.clipboard.writeText(code.textContent).then(() => {{
        const orig = button.innerHTML;
        button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/></svg>';
        button.style.color = 'var(--sf-green)';
        setTimeout(() => {{ button.innerHTML = orig; button.style.color = ''; }}, 2000);
    }});
}}
</script>
</body>
</html>'''

with open("/Users/nbaxter/Downloads/neil-fs-hol/docs/Snowflake_FinServ_Risk_HOL.html", "w") as f:
    f.write(html_out)

print(f"Written {len(html_out):,} bytes, {len(sections)} sections")
