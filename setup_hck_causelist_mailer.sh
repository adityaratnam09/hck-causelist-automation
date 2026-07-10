# ==============================================================================
# FILE: setup_hck_causelist_mailer.sh
# DESCRIPTION: Master Infrastructure Deployment Script
# ------------------------------------------------------------------------------
# Sets up the background automation sequence on macOS. It validates runtime
# setups, maps system variable configurations, injects active shell fallback
# paths (for pyenv and Homebrew), dynamically generates the localized runner
# script 'run_hck_causelist_mailer.sh', and registers a persistent launchd
# LaunchAgent wrapper targeting user-configured execution intervals.
# ==============================================================================

#!/bin/bash

# Ensure standard Homebrew installation paths are visible to non-interactive/GUI environments
# Prepend pyenv shims so the app finds your active Python, and append Homebrew at the end as a fallback
export PATH="$HOME/.pyenv/shims:$PATH:/opt/homebrew/bin:/usr/local/bin"

# Define global configuration parameters
PLIST_LABEL="com.hckcauselist.automation"
PLIST_FILE="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
CURRENT_DIR="$(pwd)"
CONFIG_FILE="$CURRENT_DIR/hck_causelist_config.txt"
README_FILE="$CURRENT_DIR/README.md"

echo "=========================================================================="
echo "INITIALIZING MASTER AUTOMATION SETUP ENGINE FOR MACOS"
echo "=========================================================================="
echo "Working Directory Context: $CURRENT_DIR"
echo ""

# Helper function for uniform error output handling
fail_step() {
    echo "[CRITICAL ERROR] $1"
    echo "Setup sequence aborted. Please fix the error above and rerun the setup."
    exit 1
}

# Verify configuration file exists before processing layout rules
if [ ! -f "$CONFIG_FILE" ]; then
    fail_step "Configuration file 'hck_causelist_config.txt' not found in current directory."
fi

# --------------------------------------------------------------------------
# STEP 1: DYNAMIC RUN TIME EXTRACTION
# --------------------------------------------------------------------------
echo "Step 1: Parsing daily schedule from configuration file..."

# Extract the raw entry value, stripping comments, spaces, and quotes
RAW_RUN_TIME=$(grep "^[[:space:]]*DAILY_RUN_TIME" "$CONFIG_FILE" | sed 's/.*=[[:space:]]*//' | tr -d '"' | tr -d "'")

# Default values if extraction fails
RUN_HOUR=18
RUN_MINUTE=30

# Regular expression verification to ensure correct format syntax (HH:MM)
if [[ "$RAW_RUN_TIME" =~ ^([0-9]{1,2}):([0-9]{2})$ ]]; then
    # Convert parameters to base-10 integers to strip any problematic leading zeros
    RUN_HOUR=$((10#${BASH_REMATCH[1]}))
    RUN_MINUTE=$((10#${BASH_REMATCH[2]}))
    
    # Simple bounds check for valid standard clock time ranges
    if [ "$RUN_HOUR" -gt 23 ] || [ "$RUN_MINUTE" -gt 59 ]; then
        echo "Warning: Extracted time [$RAW_RUN_TIME] is out of normal clock bounds."
        echo "Falling back to default automation schedule (18:30)."
        RUN_HOUR=18
        RUN_MINUTE=30
    else
        echo "Successfully matched custom schedule: Running daily at $RAW_RUN_TIME"
    fi
else
    echo "Warning: DAILY_RUN_TIME parameter missing or improperly formatted."
    echo "Falling back to default automation schedule (18:30)."
fi
echo ""

# --------------------------------------------------------------------------
# STEP 2: VERIFY OR INSTALL HOMEBREW & PYTHON3
# --------------------------------------------------------------------------
echo "Step 2: Checking for core runtime environments..."

# Check for Xcode Command Line Tools
if ! xcode-select -p &>/dev/null; then
    echo "Xcode Command Line Tools not detected. Launching native installer..."
    xcode-select --install
    echo "Please complete the pop-up window installation utility before continuing."
    echo "Once complete, press any key here to resume setup..."
    read -n 1 -s -r
fi

# Check for Homebrew package manager
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Bootstrapping official installation stream..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || fail_step "Failed to install Homebrew."
    
    # Inject Homebrew into path based on system architecture
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    echo "Homebrew framework detected."
fi

# Check for Python3 installation via Homebrew
if ! command -v python3 &>/dev/null; then
    echo "Python3 missing. Downloading official stable binary package via Homebrew..."
    brew install python || fail_step "Python3 core installation failed via Homebrew."
else
    echo "Python3 core engine available."
fi

# Extract the absolute path of the python interpreter
PYTHON_EXEC_PATH="$(command -v python3)"
echo "Target Python Executable bound to: $PYTHON_EXEC_PATH"
echo ""

# --------------------------------------------------------------------------
# STEP 3: INSTALL CORE SCRIPT DEPENDENCIES
# --------------------------------------------------------------------------
echo "Step 3: Extracting and building application modules..."

# Ensure pip is up to date
$PYTHON_EXEC_PATH -m pip install --upgrade pip &>/dev/null

# Install explicit external tracking dependencies
echo "Installing 'curl_cffi' and 'pdfplumber' modules..."
$PYTHON_EXEC_PATH -m pip install curl_cffi pdfplumber || fail_step "Failed to compile external packages via pip."

echo "All dependent Python modules successfully linked."
echo ""

# --------------------------------------------------------------------------
# STEP 4: ASSEMBLE PIPELINE RUNNER CONFIGURATION
# --------------------------------------------------------------------------
echo "Step 4: Rewriting execution control paths..."

RUNNER_SCRIPT="$CURRENT_DIR/run_hck_causelist_mailer.sh"

# Inject absolute working directories and python path into the runner script
cat << EOF > "$RUNNER_SCRIPT"
# ==============================================================================
# FILE: run_hck_causelist_mailer.sh
# DESCRIPTION: Dynamic Automation Execution Wrapper
# ------------------------------------------------------------------------------
# Automatically generated by 'setup_hck_causelist_mailer.sh'. Acts as the primary
# execution entry point triggered by the macOS launchd daemon. It sets up the
# required runtime environment paths, isolates the project directory workspace,
# and sequences the core text-scraping and outbound dispatch components.
# ==============================================================================

#!/bin/bash

# --- AUTOMATICALLY GENERATED PROFILE CONFIGURATION ---
PROJECT_DIR="$CURRENT_DIR"
PYTHON_EXEC="$PYTHON_EXEC_PATH"

cd "\$PROJECT_DIR" || exit 1

echo "=========================================================================="
echo "[START] DAILY CAUSELIST PIPELINE: \$(date)"
echo "=========================================================================="

# 1. Clear stale HTML reports and causelist files from previous runs 
# this is to ensure fresh state evaluation
echo "Cleaning up previous report artifacts..."
rm -f "causelist_search.html"
rm -f "blrconsolidation.pdf"

# 2. Execute Core Extraction Frame
echo "Step 1: Initializing parsing engine..."
\$PYTHON_EXEC hck_causelist_search.py
PYTHON_EXIT_STATUS=\$?

# 3. Separate python runtime execution health from data-presence states
if [ \$PYTHON_EXIT_STATUS -ne 0 ]; then
    echo "[ERROR] Parsing engine encountered a critical runtime error (Exit Code: \$PYTHON_EXIT_STATUS)."
    echo "Check your error logs for the trace stack. Pipeline aborted."
    exit \$PYTHON_EXIT_STATUS
fi

# 4. Process the report payload gracefully based on script outcome
if [ -f "causelist_search.html" ]; then
    echo "Step 2: HTML report successfully compiled."
    
    # 5. Trigger Secure Mail Dispatch Routine
    if [ -f "hck_causelist_mailer.py" ]; then
        echo "Step 3: Initializing isolated outbound mailer protocol..."
        \$PYTHON_EXEC hck_causelist_mailer.py
    else
        echo "[ERROR] Outbound mail script frame (hck_causelist_mailer.py) not found."
        exit 1
    fi
else
    echo "Step 2: [INFO] No matches to process (Watchlist may be empty or no keywords matched). Skipping email dispatch."
fi

echo "=========================================================================="
echo "[SUCCESS] PIPELINE EXECUTION COMPLETED: \$(date)"
echo "=========================================================================="
EOF

# Grant execution rights to the shell coordinator
chmod +x "$RUNNER_SCRIPT" || fail_step "Failed to modify permission access keys on runner script."
echo "Operational pipeline paths successfully configured and bound."
echo ""

# --------------------------------------------------------------------------
# STEP 5: DYNAMIC COMPILATION OF LAUNCHD PROPERTY LIST (.PLIST)
# --------------------------------------------------------------------------
echo "Step 5: Compiling launchd system automation matrix..."

# Ensure the logs directory exists before generating plist targets
mkdir -p "$CURRENT_DIR/logs"

# Build XML structural properties using the running execution parameters
cat << EOF > "$PLIST_FILE"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$RUNNER_SCRIPT</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$RUN_HOUR</integer>
        <key>Minute</key>
        <integer>$RUN_MINUTE</integer>
    </dict>

    <key>WorkingDirectory</key>
    <string>$CURRENT_DIR</string>

    <key>StandardOutPath</key>
    <string>$CURRENT_DIR/logs/launchd_output.log</string>
    <key>StandardErrorPath</key>
    <string>$CURRENT_DIR/logs/launchd_error.log</string>
</dict>
</plist>
EOF

# Restrict configuration access keys according to macOS daemon policies
chmod 644 "$PLIST_FILE" || fail_step "Could not set safe permission bits on daemon definition."
echo "Dynamic automation XML structured profile generated at: $PLIST_FILE"
echo ""

# --------------------------------------------------------------------------
# STEP 6: BINDING AUTOMATION PROFILE TO BACKGROUND KERNEL
# --------------------------------------------------------------------------
echo "Step 6: Loading and binding automation profile..."

# Extract user ID to dynamically target the modern GUI execution domain
USER_ID=$(id -u)

# Clean up existing instance of the current configuration to avoid structural collisions
if launchctl print "gui/$USER_ID/$PLIST_LABEL" &>/dev/null; then
    launchctl bootout "gui/$USER_ID" "$PLIST_FILE" 2>/dev/null
fi

# Modern macOS method to safely register and activate the agent daemon background loops
launchctl bootstrap "gui/$USER_ID" "$PLIST_FILE" || fail_step "System rejection encountered while bootstrapping automation daemon."

echo "Automation agent safely bound and active. Will trigger daily at $(printf "%02d:%02d" $RUN_HOUR $RUN_MINUTE)."
echo ""

# --------------------------------------------------------------------------
# STEP 7: VERIFICATION SUMMARY FOR USER ACTION
# --------------------------------------------------------------------------
echo "SYSTEM AUTOMATION INITIALIZATION COMPLETE!"
echo ""
echo "ATTENTION: Please verify and update your operational environment configuration:"
echo ""
echo "1. Update the configuration file: 'hck_causelist_config.txt'"
echo "   - Provide your SENDER_EMAIL."
echo "   - Enter your 16-character Google App Password in SENDER_PASSWORD."
echo "   - Update the RECEIVER_EMAIL with your recipient's email address."
echo "   - If you want to send notifications to multiple recipients, separate them"
echo "     using a comma in RECEIVER_EMAIL."
echo "   - Set your automation schedule via the 'DAILY_RUN_TIME' parameter using"
echo "     the 24-hour clock format (e.g. 18:30). The installation engine reads"
echo "     this value to automatically build and map system daemon interval rules."
echo ""
echo "2. Update the watchlist definitions file: 'hck_causelist_watchlist.txt'"
echo "   - Open the file to add or modify your active tracker list terms."
echo "   - Put each name, lawyer, company, or case number on its own line."
echo "   - The background parsing tool will check all pages against these items."
echo ""
echo "3. Manually Test or Force-Trigger the Pipeline"
echo "   - To run the pipeline instantly via the command line interface, use:"
echo "     launchctl start com.hckcauselist.automation"
echo "   - Track processing outputs and issues inside 'logs/launchd_output.log'"
echo "     and 'logs/launchd_error.log' respectively."
echo "=========================================================================="
