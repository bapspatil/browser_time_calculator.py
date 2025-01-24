import sys
import json
import sqlite3
import configparser
from pathlib import Path
from datetime import datetime

def debug_browser_profiles(browser_name):
    print(f"\n=== Debugging {browser_name} ===")
    
    # Path configuration
    paths = {
        "Brave": Path.home()/"Library/Application Support/BraveSoftware/Brave-Browser",
        "Chrome": Path.home()/"Library/Application Support/Google/Chrome",
        "Arc": Path.home()/"Library/Application Support/Arc/User Data",
        "Firefox": Path.home()/"Library/Application Support/Firefox",
        "Safari": Path.home()/"Library/Safari"
    }

    browser_path = paths.get(browser_name)
    if not browser_path.exists():
        print(f"❌ Browser directory not found: {browser_path}")
        return False

    print(f"✅ Found browser directory: {browser_path}")

    # Chromium-based browsers
    if browser_name in ["Brave", "Chrome", "Arc"]:
        local_state = browser_path / "Local State"
        print(f"\nChecking Local State: {local_state}")
        
        if not local_state.exists():
            print("❌ Local State file missing")
            return False
            
        try:
            with open(local_state, "r") as f:
                data = json.load(f)
                print("✅ Valid Local State file found")
                
                profiles = data.get("profile", {}).get("info_cache", {})
                print(f"Raw profile data: {json.dumps(profiles, indent=2)}")
                
                valid_profiles = [
                    (k, v["directory"]) 
                    for k, v in profiles.items() 
                    if "directory" in v
                ]
                print(f"\nFound {len(valid_profiles)} profiles:")
                for name, dir in valid_profiles:
                    print(f" - {name}: {browser_path/dir}")

        except Exception as e:
            print(f"❌ Error reading Local State: {str(e)}")
            return False

    # Firefox
    elif browser_name == "Firefox":
        profiles_ini = browser_path / "profiles.ini"
        print(f"\nChecking profiles.ini: {profiles_ini}")
        
        if not profiles_ini.exists():
            print("❌ profiles.ini missing")
            return False
            
        try:
            config = configparser.ConfigParser()
            config.read(profiles_ini)
            
            print("Profile sections found:")
            for section in config.sections():
                if section.startswith("Profile"):
                    print(f"\n[{section}]")
                    print(f"Name: {config[section].get('Name', 'Unnamed')}")
                    print(f"Path: {config[section].get('Path', '')}")
                    print(f"IsRelative: {config[section].get('IsRelative', '')}")
                    
                    abs_path = browser_path / config[section]["Path"]
                    print(f"Absolute path: {abs_path}")
                    print(f"History DB exists: {(abs_path/'places.sqlite').exists()}")
            
        except Exception as e:
            print(f"❌ Error reading profiles.ini: {str(e)}")

    # Safari
    elif browser_name == "Safari":
        history_db = browser_path / "History.db"
        print(f"\nChecking Safari History.db: {history_db}")
        
        print(f"Exists: {history_db.exists()}")
        print(f"Readable: {os.access(history_db, os.R_OK)}")
        
        if history_db.exists():
            try:
                conn = sqlite3.connect(f"file:{history_db}?mode=ro", uri=True)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM history_visits")
                print(f"✅ Safari history entries: {cursor.fetchone()[0]}")
                conn.close()
            except Exception as e:
                print(f"❌ Error reading Safari DB: {str(e)}")

    return True

if __name__ == "__main__":
    browsers = ["Brave", "Chrome", "Arc", "Firefox", "Safari"]
    for browser in browsers:
        debug_browser_profiles(browser)
        print("\n" + "="*50 + "\n")