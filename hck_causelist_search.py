# ==============================================================================
# FILE: hck_causelist_search.py
# DESCRIPTION: Core Scraper & Parser Engine
# ------------------------------------------------------------------------------
# Extracts and analyzes the High Court of Karnataka consolidated cause list.
# Downloads the live daily PDF using 'curl_cffi' to bypass anti-bot scrapers,
# processes the text via 'pdfplumber', maps cross-referenced legal targets
# defined in your local watchlist text matrix, and compiles match analytics
# into a clean HTML layout report.
# ==============================================================================

# Uncomment the line below if running in Google Colab or a clean notebook environment
# !pip install -q curl_cffi pdfplumber

import os
import re
from curl_cffi import requests
import pdfplumber

CONFIG_FILE = "hck_causelist_config.txt"

def load_config(path=CONFIG_FILE):
    """Parses a simple KEY = VALUE config file.
    Values may be quoted or unquoted. Lines beginning with # are ignored.
    Integer values (e.g. SMTP_PORT) are returned as int automatically."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file '{path}' not found.")
    cfg = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, raw = line.partition('=')
            key = key.strip()
            val = raw.strip().strip('"').strip("'")
            # Convert bare integers (e.g. SMTP_PORT = 587)
            try:
                cfg[key] = int(val)
            except ValueError:
                cfg[key] = val
    return cfg

_cfg = load_config()
PDF_URL          = _cfg.get('PDF_URL',       'https://judiciary.karnataka.gov.in/pdfs/consolidatedCauselist/blrconsolidation.pdf')
LOCAL_PDF_PATH   = _cfg.get('LOCAL_PDF_PATH','./blrconsolidation.pdf')
WATCHLIST_PATH   = _cfg.get('WATCHLIST_PATH','./watchlist.txt')
HTML_OUTPUT_PATH = _cfg.get('HTML_OUTPUT_PATH','./causelist_search.html')

def download_causelist(url, output_path):
    if os.path.exists(output_path):
        print(f"Found local copy of '{output_path}'. Skipping network download.")
        return

    print(f"Initializing connection to: {url}")
    print("Masquerading network handshake as Chrome 120...")
    
    try:
        response = requests.get(url, impersonate="chrome120", timeout=30, stream=True)
        if response.status_code == 200:
            print(f"Connection successful. Saving to '{output_path}'...")
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=131072):
                    if chunk:
                        f.write(chunk)
            print("Download fully complete.")
        else:
            raise Exception(f"Server returned non-200 status code: {response.status_code}")
    except Exception as e:
        print("Network request failed. Please check your link or download manually.")
        raise e

def load_watchlist(watchlist_path):
    print(f"Checking for watchlist file at: {watchlist_path}")
    if not os.path.exists(watchlist_path):
        with open(watchlist_path, 'w', encoding='utf-8') as f:
            f.write("# Add watch terms below (one per line)\nBipin Hegde\nState of Karnataka\n")
        print(f"Watchlist file '{watchlist_path}' was missing. Created sample.")
        return ["Bipin Hegde", "State of Karnataka"]
    
    with open(watchlist_path, 'r', encoding='utf-8') as f:
        items = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    print(f"Loaded {len(items)} active search term(s) from watchlist.")
    return items

def clean_classification(case_str, class_str):
    """Cleans up classification codes, preventing formatting loops and punctuation bugs."""
    case_str = case_str.strip()
    class_str = class_str.strip()

    # classification_captured is extracted as left_text[paren_idx:], so it already
    # carries the opening '(' from the source text. Strip exactly one outer '(' from
    # the start and one ')' from the end before we rewrap -- removing at most one
    # character from each side so nested parens inside compound classifications like
    # '(439(Cr.PC) / 483(BNSS),)' are completely unaffected.
    if class_str.startswith('('):
        class_str = class_str[1:]
    if class_str.endswith(')'):
        class_str = class_str[:-1]
    class_str = class_str.strip()

    # Strip remaining leading noise (commas, spaces, stray FOR/REG/A/W prefixes).
    class_str = re.sub(r'^[\s,]+', '', class_str).strip()
    class_str = re.sub(r'^(FOR|REG|OLD|A/W|WITH)[\s,]*', '', class_str, flags=re.IGNORECASE).strip()

    if class_str and class_str not in case_str:
        return f"{case_str} ({class_str})"
    return case_str

def parse_sort_key(match_dict):
    """Generates a strict numerical sorting tuple to sequence outputs by Court Hall room."""
    try:
        ch = int(match_dict['court_hall'])
    except ValueError:
        ch = 999  
    try:
        cl = int(match_dict['cause_list'])
    except ValueError:
        cl = 1
    try:
        sl = float(match_dict['sl_no'])
    except ValueError:
        sl = 999.0
    return (ch, cl, sl)

def find_page_gutters(words, page_width, min_gutter_width=8):
    """Scans the page horizontally to locate vertical whitespace gaps separating columns.
    Narrow gaps (less than min_gutter_width) are discarded as noise -- a few px of
    natural spacing between two words in the SAME column (e.g. "(GM," and "RES)")
    should never be mistaken for a real column boundary."""
    horizontal_profile = [0] * int(page_width + 1)
    for w in words:
        if w['top'] < 90:  
            continue
        x0 = max(0, int(w['x0']))
        x1 = min(int(page_width), int(w['x1']))
        for x in range(x0, x1 + 1):
            horizontal_profile[x] += 1

    gutters = []
    in_gutter = False
    start_x = 0
    for x in range(0, len(horizontal_profile)):
        if horizontal_profile[x] <= 1: 
            if not in_gutter:
                start_x = x
                in_gutter = True
            if x == len(horizontal_profile) - 1 and in_gutter:
                if (x - start_x) >= min_gutter_width:
                    gutters.append((start_x, x))
        else:
            if in_gutter:
                if (x - 1 - start_x) >= min_gutter_width:
                    gutters.append((start_x, x - 1))
                in_gutter = False
    return gutters

def split_words_by_detected_gutters(line_words, gutters, learned_party_divider=None):
    """Slices a text row line into its true constituent column blocks using dynamic gutters.
    Returns (col1, col2, col3, col4, col5, party_divider_used) -- the caller should
    capture party_divider_used (set only when a RES: marker was found on this row)
    and pass it back in as learned_party_divider for subsequent continuation rows of
    the SAME case block. The page-wide gutter histogram is too unreliable for the
    PET/RES split specifically (it blends word-end positions from many unrelated
    rows on the page), so an explicit marker position -- which is exact -- takes
    priority whenever one is available."""
    c2_boundary = 160
    c3_boundary = 240
    party_divider = learned_party_divider if learned_party_divider is not None else 435
    
    for g_start, g_end in gutters:
        mid = (g_start + g_end) / 2
        if 140 < mid < 180:
            c2_boundary = mid
        elif 220 < mid < 265:
            c3_boundary = mid
        elif learned_party_divider is None and 410 < mid < 460:
            party_divider = mid

    col1 = [w for w in line_words if w['x0'] < 60]
    col2 = [w for w in line_words if 60 <= w['x0'] < c2_boundary]
    col3 = [w for w in line_words if c2_boundary <= w['x0'] < c3_boundary]
    
    party_words = [w for w in line_words if w['x0'] >= c3_boundary]
    col4, col5 = [], []
    party_divider_used = None
    
    party_str = " ".join([w['text'] for w in party_words])
    res_markers = [w for w in party_words if "RES:" in w['text'] or "RESPONDENT:" in w['text']]
    if res_markers:
        cutoff = res_markers[0]['x0']
        col4 = [w for w in party_words if w['x0'] < cutoff]
        col5 = [w for w in party_words if w['x0'] >= cutoff]
        party_divider_used = cutoff
    else:
        col4 = [w for w in party_words if w['x0'] < party_divider]
        col5 = [w for w in party_words if w['x0'] >= party_divider]

    return col1, col2, col3, col4, col5, party_divider_used

def bold_watchlist_text(text, term, mode="markdown"):
    """Wraps target match terms in either Markdown format (for stdout) or HTML tags."""
    pattern = re.compile(f"({re.escape(term)})", re.IGNORECASE)
    if mode == "html":
        return pattern.sub(r"<b class='highlight'>\1</b>", text)
    return pattern.sub(r"**\1**", text)

def generate_html_report(grouped_data, output_path, total_pages):
    """Compiles matching case profiles into an HTML reporting sheet."""
    total_matches = sum(len(records) for records in grouped_data.values())
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Causelist Search Report</title>
    <style>
        :root {{
            --bg-gradient: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            --panel-bg: #ffffff;
            --text-main: #1a202c;
            --text-muted: #4a5568;
            --accent-blue: #2c5282;
            --accent-badge: #ebf8ff;
            --badge-text: #2b6cb0;
            --border-color: #e2e8f0;
            --highlight-bg: #fff5f5;
            --highlight-text: #c53030;
            --pet-bg: #eef2f7;
            --pet-text: #2d4a6e;
            --res-bg: #f0f4ee;
            --res-text: #2d4a2d;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-gradient);
            color: var(--text-main);
            margin: 0;
            padding: 40px 20px;
            min-height: 100vh;
            font-size: 16px;
        }}
        .container {{
            max-width: 1040px;
            margin: 0 auto;
        }}
        .header {{
            background: var(--panel-bg);
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            margin-bottom: 30px;
            border-left: 6px solid var(--accent-blue);
        }}
        h1 {{ margin: 0 0 10px 0; font-size: 30px; letter-spacing: -0.5px; }}
        .meta-summary {{ color: var(--text-muted); font-size: 15px; }}
        .term-section {{
            background: var(--panel-bg);
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            margin-bottom: 35px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}
        .term-header {{
            background: #edf2f7;
            padding: 18px 25px;
            font-size: 19px;
            font-weight: 700;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 1;
        }}
        .match-count {{
            background: var(--accent-badge);
            color: var(--badge-text);
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            white-space: nowrap;
        }}
        .case-card {{
            padding: 26px 28px;
            border-bottom: 1px solid var(--border-color);
        }}
        .case-card:nth-child(even) {{ background: #fbfcfe; }}
        .case-card:last-child {{ border-bottom: none; }}
        .court-meta {{
            font-size: 13.5px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: var(--accent-blue);
            margin-bottom: 10px;
        }}
        .case-no {{
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 8px;
            color: #1a202c;
            line-height: 1.4;
        }}
        .judges {{
            font-size: 15.5px;
            color: var(--text-muted);
            margin-bottom: 18px;
            font-weight: 500;
            line-height: 1.5;
        }}
        .entry-box {{
            background: #f7fafc;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 18px 20px;
            font-size: 15.5px;
            line-height: 1.75;
        }}
        .entry-row {{
            display: table;
            width: 100%;
            margin-bottom: 10px;
        }}
        .entry-row + .entry-row {{ margin-top: 4px; }}
        .party {{
            display: table-cell;
            white-space: nowrap;
            vertical-align: top;
            font-weight: 700;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 4px 10px 0 0;
            width: 1%;
        }}
        .party-label {{
            display: inline-block;
            white-space: nowrap;
            padding: 3px 10px;
            border-radius: 20px;
        }}
        .party-label.pet {{ background: var(--pet-bg); color: var(--pet-text); }}
        .party-label.res {{ background: var(--res-bg); color: var(--res-text); }}
        .party-text {{
            display: table-cell;
            vertical-align: top;
            word-break: break-word;
            overflow-wrap: anywhere;
            padding-top: 3px;
        }}
        .highlight {{
            color: var(--highlight-text);
            font-weight: 700;
            text-decoration: underline;
            text-decoration-thickness: 1.5px;
            text-underline-offset: 2px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Causelist Search Report</h1>
            <div class="meta-summary">
                Processed pages: <b>{total_pages}</b> &nbsp;|&nbsp; Total active matches found: <b>{total_matches}</b>
            </div>
        </div>
"""
    
    for term, records in grouped_data.items():
        if not records:
            continue  
            
        html_content += f"""
        <div class="term-section">
            <div class="term-header">
                <span>Watchlist Target: "{term}"</span>
                <span class="match-count">{len(records)} Matches</span>
            </div>
        """
        for m in records:
            c_no = bold_watchlist_text(m['case_no'], term, mode="html")
            p_txt = bold_watchlist_text(m['pet_text'], term, mode="html")
            r_txt = bold_watchlist_text(m['res_text'], term, mode="html")
            
            html_content += f"""
            <div class="case-card">
                <div class="court-meta">Court Hall {m['court_hall']} &bull; Cause List No. {m['cause_list']} &bull; Sl. No. {m['sl_no']}</div>
                <div class="case-no">Case No: {c_no}</div>
                <div class="judges">Before: {m['judges']}</div>
                <div class="entry-box">
                    <div class="entry-row"><span class="party"><span class="party-label pet">PET</span></span><span class="party-text">{p_txt}</span></div>
                    <div class="entry-row"><span class="party"><span class="party-label res">RES</span></span><span class="party-text">{r_txt if r_txt else '<span style="color:#a0aec0">None Listed</span>'}</span></div>
                </div>
            </div>
            """
        html_content += "</div>"
        
    html_content += """
    </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def parse_and_search_pdf(pdf_path, watchlist):
    print("Opening PDF with Parsing Engine...")
    
    current_court_hall = "UNKNOWN"
    current_cause_list_no = "1"
    current_judges = "UNKNOWN"
    
    ch_pattern = re.compile(r'COURT\s+HALL\s+NO\s*:?\s*(\d+[A-Z]?|CHIEF\s+JUSTICE)', re.IGNORECASE)
    cl_pattern = re.compile(r'Cause\s+List\s+No\s*.\s*(\d+)', re.IGNORECASE)
    judge_pattern = re.compile(
        r"(THE\s+HON['\u2019]?BLE\s+.*?JUSTICE.*?|(?:JOINT\s+)?REGISTRAR\s+\w+)"
        r"($|\n)", re.IGNORECASE
    )
    sl_pattern = re.compile(r'^\s*(\d+(?:\.\d+)?)')

    grouped_matches = {term: [] for term in watchlist}

    footer_pattern = re.compile(r'^(Website:|judiciary\.karnataka|\d{6,}\.\d+)$', re.IGNORECASE)

    active_sl_no = "UNKNOWN"
    case_no_captured = ""
    classification_captured = ""
    pet_elements = []
    res_elements = []
    block_party_divider = None
    block_left_boundary = None
    block_classification_left = None
    # Persists across blocks: once we've seen a RES: column at a given x-position
    # on this page layout, that position is stable for the whole document. Used as
    # a fallback divider when a new block's opening row has no RES: token (e.g.
    # connected-with sub-cases, or cases where the RES column is genuinely blank
    # but other rows have already taught us where the column boundary sits).
    last_known_party_divider = None
    # Snapshotted at block-start so multi-page blocks carry the right court/judges
    # even after the page header has been overwritten by a new section on the next page.
    block_court_hall = ""
    block_cause_list = ""
    block_judges = ""

    def flush_current_block():
        """Processes and captures structured cell contexts when records shift indices."""
        nonlocal active_sl_no, case_no_captured, classification_captured, block_court_hall, block_cause_list, block_judges
        if active_sl_no == "UNKNOWN":
            return

        full_case_info = clean_classification(case_no_captured, classification_captured)

        p_words = sorted(pet_elements, key=lambda x: (x.get('_page', 0), x['top'], x['x0']))
        r_words = sorted(res_elements, key=lambda x: (x.get('_page', 0), x['top'], x['x0']))

        pet_str = re.sub(r'\s+', ' ', " ".join([w['text'] for w in p_words])).strip()
        res_str = re.sub(r'\s+', ' ', " ".join([w['text'] for w in r_words])).strip()

        pet_str = re.sub(r'^(PETITIONER\s*:|PET\s*:)\s*', '', pet_str, flags=re.IGNORECASE).strip()
        res_str = re.sub(r'^(RESPONDENT\s*:|RES\s*:)\s*', '', res_str, flags=re.IGNORECASE).strip()

        # Strip embedded column-label markers that pdfplumber merged into party names
        # (e.g. "SAVITHRAMMARES:" → "SAVITHRAMMA"). \B ensures we only strip when
        # the label is glued to the preceding word (non-word-boundary), leaving any
        # standalone "RES:" or "PET:" that somehow survived into the text untouched.
        pet_str = re.sub(r'\B(RESPONDENT|RES)\s*:', '', pet_str, flags=re.IGNORECASE).strip()
        res_str = re.sub(r'\B(PETITIONER|PET)\s*:', '', res_str, flags=re.IGNORECASE).strip()
        pet_str = re.sub(r'\s*(RESPONDENT|RES)\s*:\s*$', '', pet_str, flags=re.IGNORECASE).strip()
        res_str = re.sub(r'\s*(PETITIONER|PET)\s*:\s*$', '', res_str, flags=re.IGNORECASE).strip()

        pet_str = re.sub(r'^[\s\)\,\.\-]+', '', pet_str).strip()
        res_str = re.sub(r'^[\s\)\,\.\-]+', '', res_str).strip()

        combined_text = f"{full_case_info} {pet_str} {res_str}".lower()
        # For parenthetical classification terms like '(GW, )' the PDF token join
        # may produce a different spacing than what the user typed in the watchlist.
        # Build a compact variant with whitespace stripped just before ')' so that
        # '(GW, )' and '(GW,)' both match against '(gw,)' in combined_text.
        combined_compact = re.sub(r'\s+\)', ')', combined_text)
        matched_terms_for_block = set()
        for t in watchlist:
            t_lower = t.lower()
            t_compact = re.sub(r'\s+\)', ')', t_lower)
            if t_lower in combined_text or t_compact in combined_compact:
                matched_terms_for_block.add(t)
        if not matched_terms_for_block:
            return

        match_record = {
            'court_hall': block_court_hall,
            'cause_list': block_cause_list,
            'sl_no': active_sl_no,
            'judges': block_judges,
            'case_no': full_case_info,
            'pet_text': pet_str,
            'res_text': res_str
        }

        for term in matched_terms_for_block:
            grouped_matches[term].append(match_record)

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"PDF successfully opened. Total pages to scan: {total_pages}\n")
        
        for page_num, page in enumerate(pdf.pages, start=1):
            if page_num == 1 or page_num % 50 == 0 or page_num == total_pages:
                print(f"Scanning progress: Page {page_num}/{total_pages}...")

            # Extract words first so they're available as a fallback for judge
            # detection when page.extract_text() misses or misformats the header.
            words = page.extract_words()
            if not words: continue

            header_text = page.extract_text() or ""
            ch_match = ch_pattern.search(header_text)
            if ch_match:
                new_hall = ch_match.group(1).strip()
                if new_hall != current_court_hall:
                    # Column layout (PET/RES x-positions) differs per court hall.
                    # Discard the previous hall's learned divider so the new hall
                    # calibrates from its own first RES: occurrence.
                    last_known_party_divider = None
                current_court_hall = new_hall
            cl_match = cl_pattern.search(header_text)
            if cl_match: current_cause_list_no = cl_match.group(1).strip()
            judge_matches = judge_pattern.findall(header_text)

            if not judge_matches:
                # Fallback: reconstruct from the top-of-page word tokens directly.
                # extract_text() occasionally misses or misjoin lines in the header
                # band (especially for new bench compositions or visiting judges),
                # while extract_words() gives reliable individual tokens.
                top_words = sorted(
                    [w for w in words if w['top'] < 180],
                    key=lambda w: (w['top'], w['x0'])
                )
                top_text = ' '.join(w['text'] for w in top_words)
                judge_matches = judge_pattern.findall(top_text)

            if judge_matches:
                current_judges = " & ".join([m[0].strip() for m in judge_matches]).replace('\n', ' ')
                # Retroactively fix a block that started before we saw this court
                # hall's judge info (e.g. when the bench header was on the previous
                # page and the first SL was snapshotted before that page was processed).
                if active_sl_no != "UNKNOWN" and block_judges == "UNKNOWN" and block_court_hall == current_court_hall:
                    block_judges = current_judges

            # Drop the page footer band entirely (website URL, "Page X of 15",
            # the trailing timestamp digits) before any column logic runs. Left
            # in place, these words land inside whichever column their x-position
            # happens to fall under and get appended onto the last open record's
            # PET/RES text -- which is what produced the "Page 4 of 15" and
            # "290620261.3619" fragments showing up inside party names.
            footer_cutoff = page.height - 40
            words = [w for w in words if w['top'] < footer_cutoff and not footer_pattern.match(w['text'])]
            if not words: continue

            lines_dict = {}
            for w in words:
                top_coord = round(w['top'] / 3) * 3
                lines_dict.setdefault(top_coord, []).append(w)
            
            sorted_tops = sorted(lines_dict.keys())

            for top in sorted_tops:
                line_words = sorted(lines_dict[top], key=lambda x: x['x0'])
                if not line_words: continue

                # pdfplumber occasionally splits a multi-digit serial number into
                # separate single-digit word tokens (e.g. "3" and "7" instead of
                # "37"). Merge all leading col1 tokens (x0 < 60) on this row before
                # testing for a new serial number, so "37" isn't misread as "3"
                # with a stray "7" silently dropped.
                col1_tokens = [w for w in line_words if w['x0'] < 60]
                if col1_tokens:
                    merged_sl_text = "".join(w['text'] for w in col1_tokens).strip()
                    sl_match = sl_pattern.match(merged_sl_text)
                    if sl_match:
                        flush_current_block()
                        
                        active_sl_no = sl_match.group(1)
                        # Snapshot court metadata at block-start (issue 1 fix: see below)
                        block_court_hall = current_court_hall
                        block_cause_list = current_cause_list_no
                        block_judges = current_judges
                        case_no_captured = ""
                        classification_captured = ""
                        pet_elements = []
                        res_elements = []
                        block_party_divider = None
                        block_left_boundary = None
                        block_classification_left = None
                        
                        # Use id() for exclusion -- dict equality could accidentally
                        # match a different token that has identical text/bbox values.
                        col1_ids = {id(w) for w in col1_tokens}
                        line_words = [w for w in line_words if id(w) not in col1_ids]
                        remainder = merged_sl_text[sl_match.end():].strip()
                        if remainder:
                            anchor = col1_tokens[0]
                            line_words = [{'text': remainder, 'x0': anchor['x0'], 'x1': anchor['x1'], 'top': anchor['top']}] + line_words
                        if not line_words: continue

                line_full_text = " ".join([w['text'] for w in line_words])
                if re.search(r'COURT\s+HALL|Cause\s+List|Case\s+No|Pet/Appl|Resp\s+&\s+Adv', line_full_text, re.IGNORECASE):
                    continue

                pet_marker = next((w for w in line_words if re.match(r'PET\s*:', w['text'], re.IGNORECASE)), None)

                if pet_marker is None and block_left_boundary is not None:
                    left_side = [w for w in line_words if w['x0'] < block_left_boundary]
                    right_side = [w for w in line_words if w['x0'] >= block_left_boundary]
                    straddles_word = any(w['x0'] < block_left_boundary < w['x1'] for w in left_side)
                    small_gap = False
                    if left_side and right_side:
                        gap = min(w['x0'] for w in right_side) - max(w['x1'] for w in left_side)
                        small_gap = gap < 15
                    if straddles_word or small_gap:
                        # A genuine row's columns are separated by real whitespace in
                        # the source PDF -- tens of pixels wide. Text that crosses the
                        # PET-column position with only normal word-spacing (or a word
                        # straddling it outright) isn't column-structured case data at
                        # all: it's free-flowing boilerplate -- a section divider
                        # ("HEARING - INTERLOCUTORY APPLN", "PRONOUNCEMENT OF
                        # JUDGMENT-2:30 PM"), a left-column note that happens to run
                        # the full row width ("NON-COMPLIANCE OF OFFICE-OBJNS FOR 6TH
                        # TIME"), or page-header text bleeding in when a case block is
                        # still open across a page/section boundary (title line,
                        # "PHYSICAL HEARING / VIDEO CONFERENCING", bench composition,
                        # the telegram notice, "NOTE:" disclaimers). None of it belongs
                        # to the current case's PET/RES text.
                        continue

                if pet_marker is not None and active_sl_no != "UNKNOWN":
                    block_left_boundary = pet_marker['x0']
                    block_classification_left = None  # classification is now complete; stop continuation capture

                    if not case_no_captured:
                        left_words = sorted([w for w in line_words if w['x0'] < block_left_boundary], key=lambda w: w['x0'])
                        if left_words:
                            left_text = " ".join(w['text'] for w in left_words).strip()
                            # Case format is always "CASE NO (CLASSIFICATION)" -- splitting
                            # on the first literal "(" is exact and position-independent.
                            paren_idx = left_text.find('(')
                            if paren_idx != -1:
                                case_no_captured = left_text[:paren_idx].strip()
                                classification_captured = left_text[paren_idx:].strip()
                                # Remember the x-position where the classification text
                                # itself starts, so continuation rows (the BNSS/Cr.PC
                                # section name often wraps onto a second physical row,
                                # e.g. "(439(Cr.PC) /" then "483(BNSS), )") can be
                                # recognised and appended below.
                                paren_word = next((w for w in left_words if '(' in w['text']), None)
                                if paren_word is not None:
                                    block_classification_left = paren_word['x0']
                            else:
                                case_no_captured = left_text
                elif block_classification_left is not None and block_left_boundary is not None and active_sl_no != "UNKNOWN":
                    # Continuation row: pick up classification text wrapping into the
                    # same x-zone as row one's classification, while ignoring the
                    # unrelated REG:/A/W NOTE annotation column further to the left.
                    class_cont_words = sorted(
                        [w for w in line_words if block_classification_left - 5 <= w['x0'] < block_left_boundary],
                        key=lambda w: w['x0']
                    )
                    if class_cont_words:
                        cont_text = " ".join(w['text'] for w in class_cont_words).strip()
                        # Genuine classification continuations always carry a
                        # parenthesis (e.g. "483(BNSS), )"). Standalone divider/status
                        # text that happens to land in the same column and even
                        # contain a digit -- "ORDERS", "ADMISSION", "FURTHER
                        # ARGUMENTS - 4.00 PM" -- never has a paren, and must not be
                        # appended.
                        if re.search(r'[()]', cont_text):
                            classification_captured = f"{classification_captured} {cont_text}".strip()

                party_words = [w for w in line_words if block_left_boundary is not None and w['x0'] >= block_left_boundary]

                res_marker = next((w for w in party_words if re.match(r'(RESPONDENT|RES)\s*:', w['text'], re.IGNORECASE)), None)
                if res_marker is not None:
                    block_party_divider = res_marker['x0']
                    last_known_party_divider = block_party_divider
                else:
                    # pdfplumber sometimes merges adjacent petitioner-name text
                    # with the "RES:" column label into one token when they are
                    # nearly touching in the PDF (e.g. "SAVITHRAMMARES:").
                    # Interpolate where "RES:" starts within the compound token.
                    for w in party_words:
                        label_hit = re.search(r'(RESPONDENT|RES)\s*:$', w['text'], re.IGNORECASE)
                        if label_hit and not re.match(r'(RESPONDENT|RES)\s*:', w['text'], re.IGNORECASE):
                            name_len = len(w['text']) - len(label_hit.group(0))
                            total_len = len(w['text'])
                            block_party_divider = w['x0'] + (name_len / total_len) * (w['x1'] - w['x0'])
                            last_known_party_divider = block_party_divider
                            break

                effective_divider = block_party_divider if block_party_divider is not None else last_known_party_divider
                if effective_divider is not None:
                    c4 = [w for w in party_words if w['x0'] < effective_divider]
                    c5 = [w for w in party_words if w['x0'] >= effective_divider]
                else:
                    # No divider learned at all yet (very first block in document).
                    c4 = party_words
                    c5 = []

                if c4: pet_elements.extend({**w, '_page': page_num} for w in c4)
                if c5: res_elements.extend({**w, '_page': page_num} for w in c5)

        flush_current_block()
            
        print("Parsing completely finished.\n")

    final_cleaned_grouped_data = {}
    total_found_overall = 0
    
    for term in watchlist:
        records = grouped_matches[term]
        unique_records = []
        seen_keys = set()
        for r in records:
            r_key = (r['court_hall'], r['cause_list'], r['sl_no'], r['case_no'])
            if r_key not in seen_keys:
                unique_records.append(r)
                seen_keys.add(r_key)
                
        sorted_records = sorted(unique_records, key=parse_sort_key)
        final_cleaned_grouped_data[term] = sorted_records
        total_found_overall += len(sorted_records)

    # Output Console Reporting Stage
    # Uncomment the line below to print a full match summary to stdout (useful for debugging).
    # print_console_report(final_cleaned_grouped_data, total_pages)

    generate_html_report(final_cleaned_grouped_data, HTML_OUTPUT_PATH, total_pages)
    print(f"\n[Success] HTML report exported to '{HTML_OUTPUT_PATH}' — {total_found_overall} matches across {len([t for t,r in final_cleaned_grouped_data.items() if r])} active term(s).")

def print_console_report(final_cleaned_grouped_data, total_pages):
    """Prints a human-readable summary of all watchlist matches to stdout.
    Commented out in the main call below -- uncomment to enable for debugging."""
    total_found_overall = sum(len(r) for r in final_cleaned_grouped_data.values())

    print("=" * 80)
    print("                      CAUSET LIST WATCHLIST SEARCH REPORT                     ")
    print("=" * 80)
    
    for term, sorted_records in final_cleaned_grouped_data.items():
        count = len(sorted_records)
        
        if count == 0:
            continue
            
        print(f"\n➔ WATCHLIST TERM: '{term}' ({count} matches found)")
        print("~" * 50)
            
        for m in sorted_records:
            c_no = bold_watchlist_text(m['case_no'], term, mode="markdown")
            p_txt = bold_watchlist_text(m['pet_text'], term, mode="markdown")
            r_txt = bold_watchlist_text(m['res_text'], term, mode="markdown")
            
            entry_line = f"PET: {p_txt}"
            if r_txt:
                entry_line += f" | RES: {r_txt}"

            print(f"COURT HALL NO : {m['court_hall']} | Cause List No. {m['cause_list']} | Sl. No. {m['sl_no']} | Judges: {m['judges']}")
            print(f"Case No: {c_no}")
            print(f"Causelist Entry: {entry_line}")
            print("-" * 80)

    print("\n" + "=" * 80)
    print(f"SUMMARY: Processed {total_pages} pages. Total matches generated: {total_found_overall}")
    print("=" * 80)

if __name__ == "__main__":
    try:
        watchlist = load_watchlist(WATCHLIST_PATH)
        if watchlist:
            try: download_causelist(PDF_URL, LOCAL_PDF_PATH)
            except Exception: pass 
            
            if os.path.exists(LOCAL_PDF_PATH):
                parse_and_search_pdf(LOCAL_PDF_PATH, watchlist)
            else:
                print("Execution stopped: Local target PDF configuration not found.")
    except Exception as e:
        print(f"\nRuntime Error: {e}")
