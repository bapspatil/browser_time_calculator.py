import gradio as gr
import sqlite3
import json
import sys
import configparser
from pathlib import Path
from datetime import datetime, timedelta

def get_installed_browsers():
    """Detect installed browsers and their profile paths"""
    browsers = {
        "Brave": {
            "win32": Path("AppData/Local/BraveSoftware/Brave-Browser/User Data"),
            "darwin": Path("Library/Application Support/BraveSoftware/Brave-Browser"),
            "linux": Path(".config/BraveSoftware/Brave-Browser")
        },
        "Chrome": {
            "win32": Path("AppData/Local/Google/Chrome/User Data"),
            "darwin": Path("Library/Application Support/Google/Chrome"),
            "linux": Path(".config/google-chrome")
        },
        "Edge": {
            "win32": Path("AppData/Local/Microsoft/Edge/User Data"),
            "darwin": Path("Library/Application Support/Microsoft Edge"),
            "linux": Path(".config/microsoft-edge")
        },
        "Arc": {
            "darwin": Path("Library/Application Support/Arc/User Data")
        },
        "Firefox": {
            "win32": Path("AppData/Roaming/Mozilla/Firefox"),
            "darwin": Path("Library/Application Support/Firefox"),
            "linux": Path(".mozilla/firefox")
        },
        "Safari": {
            "darwin": Path("Library/Safari")
        }
    }
    
    platform = sys.platform
    available = []
    
    for name, paths in browsers.items():
        if platform not in paths and name != "Safari":
            continue  # Skip platform-specific checks for Safari
            
        path = Path.home() / paths.get(platform, Path())
        if path.exists():
            available.append(name)
    
    return available

def get_browser_profiles(browser_name):
    """Get profiles for selected browser"""
    platform = sys.platform
    profiles = []
    
    # Chromium-based browsers (Brave, Chrome, Edge, Arc)
    if browser_name in ["Brave", "Chrome", "Edge", "Arc"]:
        browser_paths = {
            "Brave": {
                "win32": "BraveSoftware/Brave-Browser/User Data",
                "darwin": "Library/Application Support/BraveSoftware/Brave-Browser",
                "linux": ".config/BraveSoftware/Brave-Browser"
            },
            "Chrome": {
                "win32": "Google/Chrome/User Data",
                "darwin": "Library/Application Support/Google/Chrome",
                "linux": ".config/google-chrome"
            },
            "Edge": {
                "win32": "Microsoft/Edge/User Data",
                "darwin": "Library/Application Support/Microsoft Edge",
                "linux": ".config/microsoft-edge"
            },
            "Arc": {
                "darwin": "Library/Application Support/Arc/User Data"
            }
        }
        
        base_path = Path.home() / browser_paths[browser_name].get(
            platform, 
            browser_paths[browser_name]['darwin' if browser_name == "Arc" else 'linux']
        )
        
        local_state = base_path / "Local State"
        if local_state.exists():
            with open(local_state, "r", encoding="utf-8") as f:
                data = json.load(f)
                profile_info = data.get("profile", {}).get("info_cache", {})
                
                for profile_id, info in profile_info.items():
                    if "directory" in info:
                        profile_name = info.get("user_name", "Unnamed Profile")
                        profiles.append((
                            profile_name,
                            str(base_path / info["directory"])
                        ))

    # Firefox
    elif browser_name == "Firefox":
        profiles_ini = Path.home() / {
            "win32": Path("AppData/Roaming/Mozilla/Firefox"),
            "darwin": Path("Library/Application Support/Firefox"),
            "linux": Path(".mozilla/firefox")
        }[platform] / "profiles.ini"

        if profiles_ini.exists():
            config = configparser.ConfigParser()
            config.read(profiles_ini)
            
            for section in config.sections():
                if section.startswith("Profile"):
                    profile_path = Path(config[section]["Path"])
                    if platform == "win32":
                        profile_path = Path.home() / "AppData/Roaming/Mozilla/Firefox" / profile_path
                    else:
                        profile_path = Path.home() / "Library/Application Support/Firefox" / profile_path
                    
                    profiles.append((
                        config[section].get("Name", "Default Profile"),
                        str(profile_path)
                    ))

    # Safari (limited support)
    elif browser_name == "Safari" and platform == "darwin":
        safari_path = Path.home() / "Library/Safari"
        if safari_path.exists():
            profiles.append((
                "Default Safari Profile",
                str(safari_path)
            ))
    if local_state.exists():
        with open(local_state, "r", encoding="utf-8") as f:
            data = json.load(f)
            profile_info = data.get("profile", {}).get("info_cache", {})
            
            for profile_id, info in profile_info.items():
                # Use profile ID as directory name if key is missing
                directory = info.get("directory", profile_id)
                profile_path = base_path / directory
                
                # Use name field if user_name is empty
                profile_name = info.get("user_name") or info.get("name") or "Unnamed Profile"
                
                # Verify directory exists
                if profile_path.exists():
                    profiles.append((
                        profile_name,
                        str(profile_path)
                    ))
    return profiles

def calculate_time(browser, profile_path, inactivity_mins, start_str, end_str):
    max_gap = timedelta(minutes=inactivity_mins)
    try:
        # Convert date strings to datetime objects
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )

        # Determine database path and query based on browser
        if browser in ["Brave", "Chrome", "Edge", "Arc"]:
            db_path = Path(profile_path) / "History"
            table = "visits"
            time_column = "visit_time"
            time_conversion = lambda ts: datetime(1601, 1, 1) + timedelta(microseconds=ts)
        elif browser == "Firefox":
            db_path = Path(profile_path) / "places.sqlite"
            table = "moz_historyvisits"
            time_column = "visit_date"
            time_conversion = lambda ts: datetime.fromtimestamp(ts/1000000)
        elif browser == "Safari":
            db_path = Path(profile_path) / "History.db"
            table = "history_visits"
            time_column = "visit_time"
            time_conversion = lambda ts: datetime(2001, 1, 1) + timedelta(seconds=ts)
        else:
            return "Unsupported browser"

        if not db_path.exists():
            return "History database not found"

        # Connect to database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Convert dates to browser-specific timestamps
        if browser in ["Brave", "Chrome", "Edge", "Arc"]:
            def datetime_to_timestamp(dt):
                delta = dt - datetime(1601, 1, 1)
                return int(delta.total_seconds() * 1_000_000)
        elif browser == "Firefox":
            datetime_to_timestamp = lambda dt: int(dt.timestamp() * 1_000_000)
        elif browser == "Safari":
            datetime_to_timestamp = lambda dt: int((dt - datetime(2001, 1, 1)).total_seconds())
        else:
            return "Unsupported browser"

        start_ts = datetime_to_timestamp(start_date)
        end_ts = datetime_to_timestamp(end_date)

        # Get visits in range
        cursor.execute(f'''
            SELECT {time_column} 
            FROM {table}
            WHERE {time_column} BETWEEN ? AND ?
            ORDER BY {time_column} ASC
        ''', (start_ts, end_ts))

        timestamps = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not timestamps:
            return "No browsing history found in this date range"

        # Process visits
        visits = [time_conversion(ts) for ts in timestamps]
        total_time = timedelta()

        for i in range(len(visits) - 1):
            current = visits[i]
            next_visit = visits[i + 1]
            
            if next_visit > end_date:
                next_visit = end_date

            gap = next_visit - current
            if gap <= max_gap:
                total_time += gap

        # Add final segment
        last_visit = min(visits[-1], end_date)
        if (end_date - last_visit) <= max_gap:
            total_time += end_date - last_visit

        hours = total_time.total_seconds() / 3600
        return f"Total active browsing time: {hours:.2f} hours"

    except sqlite3.OperationalError as e:
        if "locked" in str(e):
            return "Error: Close browser before analyzing"
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

def update_profile_dropdown(browser_name):
    """Update profile dropdown when browser changes"""
    profiles = get_browser_profiles(browser_name)
    if profiles:
        # Return both the updated choices and the first profile value
        return {
            "__type__": "update",
            "choices": [(name, path) for name, path in profiles],
            "value": profiles[0][1]  # Auto-select first profile
        }
    return {
        "__type__": "update",
        "choices": [],
        "value": None
    }

with gr.Blocks(theme=gr.themes.Soft()) as app:
    # Get installed browsers
    browsers = get_installed_browsers()
    first_browser = browsers[0] if browsers else None
    first_profiles = get_browser_profiles(first_browser) if first_browser else []
    
    gr.Markdown("""
    # 🕒 Browser Time Calculator
    *Calculate your active browsing time across different browsers*
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            # Browser selector
            browser_selector = gr.Dropdown(
                label="1. Select Browser",
                choices=browsers,
                value=first_browser,
                interactive=True
            )
            
            # Profile selector
            profile_selector = gr.Dropdown(
                label="2. Choose Profile",
                value=first_profiles[0][1] if first_profiles else None,
                choices=[(name, path) for name, path in first_profiles],
                interactive=bool(first_profiles),
                visible=bool(first_profiles)
            )
            
            # New Inactivity Threshold Control
            inactivity_threshold = gr.Number(
                label="Inactivity Threshold (minutes)",
                value=20,
                minimum=1,
                maximum=120,
                step=1,
                precision=0,
                interactive=True
            )
            
            # Date inputs with HTML5 date pickers
            start_date = gr.Textbox(
                label="Start Date (YYYY-MM-DD)",
                value=datetime.now().replace(day=1).strftime("%Y-%m-%d"),
                type="text",
                elem_classes="date-input"
            )
            
            end_date = gr.Textbox(
                label="End Date (YYYY-MM-DD)",
                value=datetime.now().strftime("%Y-%m-%d"),
                type="text",
                elem_classes="date-input"
            )
        
        with gr.Column(scale=2):
            result = gr.Markdown("## Active time: Calculating...")

    # Update profiles when browser changes
    browser_selector.change(
        update_profile_dropdown,
        inputs=browser_selector,
        outputs=profile_selector
    )

    # Auto-calculate when any input changes
    inputs = [browser_selector, profile_selector, inactivity_threshold, start_date, end_date]
    for component in inputs:
        component.change(
            fn=calculate_time,
            inputs=inputs,
            outputs=result,
            queue=True  # Prevent overload
        )

    # Initial calculation on app load
    app.load(
        fn=calculate_time,
        inputs=inputs,
        outputs=result,
        queue=False
    )

# Add custom CSS for date inputs
app.css = """
.date-input input[type="date"]::-webkit-calendar-picker-indicator {
    filter: invert(1);
}
.date-input input {
    color-scheme: dark;
}
"""

if __name__ == "__main__":
    app.launch(
        server_port=7860,
        show_error=True,
        share=False,
        favicon_path="⏳"
    )