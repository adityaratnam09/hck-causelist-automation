# ==============================================================================
# FILE: uninstall_hck_causelist_mailer.sh
# DESCRIPTION: System Service Removal Tool
# ------------------------------------------------------------------------------
# Offboards and purges background execution loops. It communicates directly
# with the system daemon kernel to terminate active worker IDs and decouple
# the service mapping. It cleans up temporary HTML file caches and execution
# logs while safely leaving core scripts, watchlists, and
# configuration files intact.
# ==============================================================================

#!/bin/bash

# Define tracking parameters matching the installation matrix
PLIST_LABEL="com.hckcauselist.automation"
PLIST_FILE="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
CURRENT_DIR="$(pwd)"
RUNNER_SCRIPT="$CURRENT_DIR/run_hck_causelist_mailer.sh"

echo "=========================================================================="
echo "INITIALIZING AUTOMATION REMOVAL ENGINE FOR MACOS"
echo "=========================================================================="
echo "Targeting Service Domain: gui/$(id -u)/$PLIST_LABEL"
echo ""

# --------------------------------------------------------------------------
# STEP 1: DE-REGISTER AND UNLOAD FROM LAUNCHD KERNEL
# --------------------------------------------------------------------------
echo "Step 1: Terminating and unloading background daemon service..."

USER_ID=$(id -u)

# Check if the service is currently managed by launchd
if launchctl print "gui/$USER_ID/$PLIST_LABEL" &>/dev/null; then
    echo "Active background service found. Offboarding daemon..."
    if launchctl bootout "gui/$USER_ID" "$PLIST_FILE" 2>/dev/null; then
        echo "Successfully decoupled service from the launchd engine."
    else
        echo "[WARNING] Standard bootout sequence failed. Attempting force-targeting by service label..."
        launchctl bootout "gui/$USER_ID/$PLIST_LABEL" 2>/dev/null
    fi
else
    echo "No active background instances registered under label '$PLIST_LABEL'."
fi
echo ""

# --------------------------------------------------------------------------
# STEP 2: PURGE SYSTEM LAUNCHAGENT DEFINITIONS
# --------------------------------------------------------------------------
echo "Step 2: Cleaning up persistent system launch definitions..."

if [ -f "$PLIST_FILE" ]; then
    rm -f "$PLIST_FILE"
    echo "Permanently removed launch configuration file: $PLIST_FILE"
else
    echo "LaunchAgent configuration file already absent from user library folder."
fi
echo ""

# --------------------------------------------------------------------------
# STEP 3: CLEAN RUNTIME COMPILATION ARTIFACTS
# --------------------------------------------------------------------------
echo "Step 3: Removing automatic loop-runner scripts and logs..."

# Remove the generated runner layout script
if [ -f "$RUNNER_SCRIPT" ]; then
    rm -f "$RUNNER_SCRIPT"
    echo "Removed operational pipeline script: run_hck_causelist_mailer_2.sh"
fi

# Clean up transient application outputs and data files inside the directory
[ -f "$CURRENT_DIR/causelist_search.html" ] && rm -f "$CURRENT_DIR/causelist_search.html" && echo "Cleared local HTML cache."
[ -f "$CURRENT_DIR/blrconsolidation.pdf" ] && rm -f "$CURRENT_DIR/blrconsolidation.pdf" && echo "Cleared temporary PDF cache."

# Purge logs directory tracking records if requested
if [ -d "$CURRENT_DIR/logs" ]; then
    rm -rf "$CURRENT_DIR/logs"
    echo "Purged diagnostic automation logging directory hierarchy (/logs)."
fi
echo ""

# --------------------------------------------------------------------------
# UNINSTALLATION SUMMARY
# --------------------------------------------------------------------------
echo "=========================================================================="
echo "UNINSTALLATION SEQUENCE COMPLETE"
echo "=========================================================================="
echo "The background automation engine has been successfully deactivated."
echo "Your core scripts, configurations, and watchlists have been preserved."
echo "=========================================================================="