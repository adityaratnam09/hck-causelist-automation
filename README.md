# HCK Causelist Automation
Automated Daily Monitoring of the High Court of Karnataka Causelist Using Adaptive Coordinate Calibration

![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21265907.svg)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

**hck_causelist_search** is an open-source Python pipeline that automatically downloads the daily consolidated causelist published by the High Court of Karnataka, parses its layout using an adaptive coordinate calibration algorithm based on semantic anchor tokens, matches records against a user-defined watchlist, and delivers annotated HTML reports by email.

A detailed technical report describing the parsing methodology, evaluation, and implementation is available on Zenodo: [DOI: 10.5281/zenodo.21265907].

---
## Features

- Automatically downloads the latest consolidated causelist.
- Monitors party names.
- Monitors advocate names.
- Monitors case numbers.
- Monitors classification categories.
- Generates searchable HTML reports.
- Highlights matched watchlist terms.
- Sends reports automatically by email.
- Runs unattended using macOS launchd.
- Adaptive coordinate calibration using semantic anchor tokens.
- Automatically adapts to different court-hall layouts.
- Correctly reconstructs multi-page case entries.
- Handles connected-with sub-cases.
- Detects and removes section-divider lines.

## Supported Platforms

| Platform | Status |
|----------|--------|
| macOS (Apple Silicon) | Fully supported |
| macOS (Intel) | Expected to work |
| Linux | Planned |
| Windows | Planned |

## Screenshots

### HTML Report
![HTML Report](screenshots/Figure 6.jpg)

HCK Causelist Automation automatically monitors the daily High Court of Karnataka consolidated causelist, matches user-defined watchlist terms, and delivers annotated HTML reports by email using an adaptive PDF parsing algorithm.

## What It Does

The High Court of Karnataka publishes a daily causelist PDF that runs more than 500 pages and lists thousands of cases across 30+ court halls. Finding a specific name, case number, or classification category within this document by hand is time-consuming and error-prone.

This tool does it automatically:

1. **Downloads** the causelist PDF from the court's official URL each day.
2. **Parses** the spatial column layout — petitioner, respondent, case number, classification, judge — using word-level bounding box coordinates rather than fixed pixel positions, making it robust across court halls that use different column widths.
3. **Matches** every case record against your watchlist (names, case numbers, classification codes, or advocate names).
4. **Generates** an annotated HTML report with every match highlighted.
5. **Emails** the report to one or more recipients.
6. **Runs silently** as a scheduled macOS background daemon — no daily interaction required.

## Files

| File | Purpose |
|---|---|
| `hck_causelist_search.py` | Main parser: downloads PDF, extracts matches, generates HTML |
| `hck_causelist_mailer.py` | Reads the HTML report and dispatches it by Gmail SMTP |
| `hck_causelist_config.txt` | All configuration parameters (paths, email, schedule) |
| `hck_causelist_watchlist.txt` | Your watchlist terms, one per line |
| `run_hck_causelist_mailer.sh` | Shell runner that calls the search engine then the mailer |
| `setup_hck_causelist_mailer.sh` | **One-time setup script** — run this first |

## Repository Structure
.
├── hck_causelist_search.py
├── hck_causelist_mailer.py
├── hck_causelist_config.txt
├── hck_causelist_watchlist.txt
├── setup_hck_causelist_mailer.sh
├── uninstall_hck_causelist_mailer.sh
├── screenshots/
└── README.md

---

## Installation (macOS)

### Step 1 — Download

Download the repository as a ZIP or tarball from GitHub (the green **Code** button → **Download ZIP**), or clone it:

```bash
git clone https://github.com/adityaratnam09/hck-causelist-automation.git
cd cd hck-causelist-automation
```

### Step 2 — Run the Setup Script

```bash
bash setup_hck_causelist_mailer.sh
```

This single command does everything:

- Checks for Xcode Command Line Tools and installs them if missing.
- Checks for Homebrew and installs it if missing.
- Installs Python 3 via Homebrew if not already present.
- Installs the required Python packages (`pdfplumber`, `curl_cffi`) via pip.
- Writes the correctly configured `run_hck_causelist_mailer.sh` runner with the absolute paths for your system.
- Creates a macOS `launchd` daemon (`com.hckcauselist.automation`) that runs the pipeline daily at the time you set in `hck_causelist_config.txt`.
- Creates a `logs/` directory for daemon output.

> **Note:** The setup script reads `DAILY_RUN_TIME` from `hck_causelist_config.txt` to set the daemon schedule. Update that value **before** running the setup script, or re-run the setup script after changing it.

### Step 3 — Configure

Edit `hck_causelist_config.txt`:

```
# hck_causelist_config.txt

PDF_URL = "https://judiciary.karnataka.gov.in/pdfs/consolidatedCauselist/blrconsolidation.pdf"

LOCAL_PDF_PATH   = "./blrconsolidation.pdf"
WATCHLIST_PATH   = "./hck_causelist_watchlist.txt"
HTML_OUTPUT_PATH = "./causelist_search.html"

DAILY_RUN_TIME = 21:00        # 9:00 PM — after the causelist is published

SENDER_EMAIL    = "your-address@gmail.com"
SENDER_PASSWORD = "xxxx xxxx xxxx xxxx"   # 16-character Google App Password
RECEIVER_EMAIL  = "your-address@gmail.com, another@example.com"
SMTP_SERVER     = "smtp.gmail.com"
SMTP_PORT       = 587
SUBJECT_TEMPLATE = "[ALERT] High Court of Karnataka Causelist Search:"
```

**Gmail App Password:** Go to [Google Account → Security → 2-Step Verification → App Passwords](https://myaccount.google.com/apppasswords). Generate a Google App Password and paste the resulting 16-character password into SENDER_PASSWORD. Enter the 16-character code (spaces are ignored).

### Step 4 — Set Your Watchlist

Edit `hck_causelist_watchlist.txt`. Lines starting with `#` are comments and are skipped. Add one search term per line:

```
# hck_causelist_watchlist.txt

# TYPE A: PARTY NAME MATCHES (LITIGANTS)
# Matches anywhere in the PET or RES column. Partial matching works.
Gowramma
Infosys Limited

# TYPE B: ADVOCATE MATCHES
# Advocates are listed alongside party names in the causelist.
M S Hegde

# TYPE C: CASE NUMBER MATCHES
WP 51432/2024

# TYPE D: CLASSIFICATION CATEGORY MATCHES
# Type the classification exactly as it appears in the causelist.
(GM, MM_S)
```

The matching engine is case-insensitive. Partial matching is supported: `Hegde` will match `Santosh Hegde`, `Hegde & Associates`, and so on.

---

## Running on Demand

You do not need to wait for the scheduled time. Either of the following works:

**Trigger via launchctl** (runs the full pipeline including email dispatch):
```bash
launchctl start com.hckcauselist.automation
```

**Run the search engine directly** (generates the HTML report without emailing):
```bash
python3 hck_causelist_search.py
```

**Run just the mailer** (sends a previously generated HTML report):
```bash
python3 hck_causelist_mailer.py
```

**Run both in sequence** (same as launchctl):
```bash
bash run_hck_causelist_mailer.sh
```

Pipeline logs are written to `logs/launchd_output.log` and `logs/launchd_error.log`.

---

## Changing the Schedule

1. Edit `DAILY_RUN_TIME` in `hck_causelist_config.txt`.
2. Re-run `bash setup_hck_causelist_mailer.sh` to update the daemon.

---

## Uninstalling the Daemon

```bash
uninstall_hck_causelist_mailer.sh
```

---

## How the Parser Works

The causelist is a five-column table spanning hundreds of pages. Because column positions vary between court halls, and longer case-type prefixes can shift the respondent column leftward, the parser learns column boundaries dynamically from the literal PET: and RES: label tokens rather than relying on fixed page coordinates. Each court hall is calibrated independently using the first case containing explicit PET: and RES: labels, after which subsequent cases inherit the learned boundaries. The parser reconstructs multi-page case entries, connected-with sub-cases, and varying court-hall layouts without relying on fixed coordinate thresholds.

Key design decisions:
- **Block state persists across pages**: a case entry that begins on the last row of one page and continues onto the next is assembled correctly.
- **Per-court-hall calibration**: the petitioner/respondent column boundary is reset whenever the court hall changes, preventing a boundary learned in one hall from being misapplied to another.
- **Section-divider rejection**: centred section-title rows (e.g. `HEARING - INTERLOCUTORY APPLN`, `PRONOUNCEMENT OF JUDGMENT - 2:30 PM`) are geometrically identified and discarded before they can contaminate party text.
- **Merged-token handling**: when pdfplumber merges adjacent words into a single token (e.g. `SAVITHRAMMARES:` for a petitioner named SAVITHRAMMA followed immediately by `RES:`), the parser interpolates the correct split position from character proportions.
- **Classification matching**: the case number and classification parenthetical (e.g. `(GW, )`) are included in the searchable text, enabling category-level monitoring as a first-class feature.

---

## Packaging Notes for Non-Technical Users

The setup script is designed so that a non-technical user only needs to:

1. Download the ZIP from GitHub.
2. Open Terminal.
3. `cd` into the extracted folder.
4. Run `bash setup_hck_causelist_mailer.sh`.
5. Edit the two plain-text config files.

No Python knowledge, no IDE, and no manual pip commands are required. If Homebrew or Python are not installed, the setup script installs them.

For further simplicity, a future release could package the tool as a macOS `.app` bundle using PyInstaller, eliminating the Terminal step entirely.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `pdfplumber` | ≥ 0.9 | Word-level PDF coordinate extraction |
| `curl_cffi` | ≥ 0.6 | TLS-impersonating HTTP download |

Both are installed automatically by the setup script.

---

## License

MIT License. See `LICENSE` for details.

---

## Citation

If you use this software in research, please cite both the software and the accompanying technical report.

**Software (GitHub):**

```text
Ratnam, A. R. (2026). *HCK Causelist Automation* (Version 1.0.0) [Computer software]. GitHub. https://github.com/adityaratnam09/hck-causelist-automation
```

**Technical report (Zenodo):**

```text
Ratnam, A. R. (2026). *Automated Daily Monitoring of the High Court of Karnataka Causelist Using Adaptive Coordinate Calibration With Semantic Anchor Tokens*. Zenodo. https://doi.org/10.5281/zenodo.21265907
```

