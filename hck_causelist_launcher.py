# ==============================================================================
# FILE: hck_causelist_launcher.py
# DESCRIPTION: Native macOS GUI Bootstrapper
# ------------------------------------------------------------------------------
# Compiles the pipeline installation into a standalone macOS .app bundle via
# PyInstaller, and interfaces natively with the system UI using
# AppleScript dialog prompts.
# ==============================================================================

import os
import sys
import subprocess

def get_project_directory():
    """
    Dynamically tracks down the folder containing the compiled .app bundle.
    When frozen by PyInstaller, sys.executable points deep inside the package:
    YourFolder/HCKCauseListAutomationSetup.app/Contents/MacOS/HCKCauseListAutomationSetup
    Moving exactly 4 parent levels up yields the true absolute project root.
    """
    if getattr(sys, 'frozen', False):
        app_binary_path = sys.executable
        contents_macos_dir = os.path.dirname(app_binary_path)
        contents_dir = os.path.dirname(contents_macos_dir)
        app_bundle_dir = os.path.dirname(contents_dir)
        project_root_dir = os.path.dirname(app_bundle_dir)
        return project_root_dir
    else:
        return os.path.dirname(os.path.abspath(__file__))

def display_macos_alert(title, message, icon_type="note"):
    """
    Renders native macOS dialog windows using AppleScript.
    icon_type options: 'note' (Informational), 'caution' (Warning), 'stop' (Critical Error)
    """
    escaped_message = message.replace('"', '\\"')
    escaped_title = title.replace('"', '\\"')
    applescript_cmd = (
        f'display dialog "{escaped_message}" '
        f'with title "{escaped_title}" '
        f'buttons {{"OK"}} default button "OK" '
        f'with icon {icon_type}'
    )
    subprocess.run(["osascript", "-e", applescript_cmd])

def main():
    # 1. Map working directory safely to your project location
    project_dir = get_project_directory()
    os.chdir(project_dir)
    
    script_name = "setup_hck_causelist_mailer.sh"
    target_script_path = os.path.join(project_dir, script_name)
    
    # 2. Assert setup shell script availability
    if not os.path.exists(target_script_path):
        display_macos_alert(
            "Setup Error", 
            f"Initialization aborted.\n\nCould not locate '{script_name}' inside the destination folder:\n{project_dir}", 
            "stop"
        )
        sys.exit(1)
        
    # 3. Bypass manual chmod +x friction programmatically
    try:
        os.chmod(target_script_path, 0o755)
    except Exception as e:
        display_macos_alert(
            "Permission Error", 
            f"Failed to programmatically set execution permissions via chmod:\n{str(e)}", 
            "stop"
        )
        sys.exit(1)
        
    # 4. Fire setup pipeline and catch downstream exceptions silently
    try:
        execution_result = subprocess.run(
            ["/bin/bash", target_script_path], 
            capture_output=True, 
            text=True
        )
        
        if execution_result.returncode == 0:
            display_macos_alert(
                "Setup Successful", 
                "High Court of Karnataka Causelist Automation Engine built and registered successfully!\n\nBackground agents are active. Please review README.md file and update configuration details.", 
                "note"
            )
        else:
            # If internal script checks fail, catch execution logs for debugging
            error_log_path = os.path.join(project_dir, "logs", "launcher_bootstrap_error.log")
            os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
            
            with open(error_log_path, "w") as error_file:
                error_file.write("--- STANDARD ERROR STREAM ---\n")
                error_file.write(execution_result.stderr)
                error_file.write("\n\n--- STANDARD OUTPUT STREAM ---\n")
                error_file.write(execution_result.stdout)
                
            display_macos_alert(
                "Automation Execution Failure", 
                f"The installation script encountered a failure step.\n\nDiagnostic stack trace saved to:\nlogs/launcher_bootstrap_error.log", 
                "caution"
            )
            
    except Exception as e:
        display_macos_alert(
            "System Exception", 
            f"An unexpected failure interrupted the sub-process container pipeline:\n{str(e)}", 
            "stop"
        )

if __name__ == "__main__":
    main()
