import csv
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables
load_dotenv() 

URL = "https://cybagemis.cybage.com/Framework/Iframe.aspx"

def get_report_dates():
    """Calculates the Monday of the week containing the 1st of the month to keep the date range short."""
    now = datetime.now()
    today_date = now.strftime("%d-%b-%Y")
    
    first_of_month = now.replace(day=1)
    days_to_subtract = first_of_month.weekday()
    start_date = first_of_month - timedelta(days=days_to_subtract)
    
    first_date = start_date.strftime("%d-%b-%Y")
    return first_date, today_date

def calculate_hours_from_swipes(target_date):
    """Calculates actual in-office time for a specific date using raw swipe logs."""
    if not os.path.exists("timetable-log.csv"):
        return None

    # Normalize target date to use spaces (e.g., '24 Jun 2026')
    target_date_norm = target_date.replace("-", " ").strip()

    with open("timetable-log.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        logs = list(reader)

    valid_logs = []
    for log in logs:
        # Normalize log date to use spaces so they match perfectly
        log_date_norm = log.get('Date', '').replace("-", " ").strip()
        if log_date_norm != target_date_norm:
            continue
            
        machine = log.get('Machine Name', '').lower()
        if ("tripod" in machine or "barrier" in machine) and "main gate" not in machine:
            valid_logs.append(log)

    if not valid_logs:
        return None

    def parse_time(log):
        d_str = log.get('Date', '').replace("-", " ").strip()
        t_str = log.get('Time', '').strip()
        time_str = f"{d_str} {t_str}"
        return datetime.strptime(time_str, "%d %b %Y %I:%M:%S %p")

    valid_logs.sort(key=parse_time)

    total_seconds = 0
    current_in_time = None

    for log in valid_logs:
        log_time = parse_time(log)
        direction = log.get('Direction', '').strip().lower()

        if direction == 'entry':
            if not current_in_time:
                current_in_time = log_time
        elif direction == 'exit':
            if current_in_time:
                total_seconds += (log_time - current_in_time).total_seconds()
                current_in_time = None 

    # If the user is currently still in the office TODAY, calculate up to this exact moment
    today_str_norm = datetime.now().strftime("%d %b %Y")
    if current_in_time and target_date_norm == today_str_norm:
        total_seconds += (datetime.now() - current_in_time).total_seconds()

    if total_seconds == 0:
        return None

    hours, remainder = divmod(int(total_seconds), 3600)
    minutes = remainder // 60
    return f"{hours}:{minutes:02d}"

def _get_live_today_data():
    """Helper method to calculate today's time dynamically. Returns (total_seconds, is_currently_in)."""
    if not os.path.exists("timetable-log.csv"):
        return 0, False
    
    with open("timetable-log.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        logs = list(reader)
        
    if not logs:
        return 0, False

    today_str_norm = datetime.now().strftime("%d %b %Y")
    valid_logs = []
    
    for log in logs:
        log_date_norm = log.get('Date', '').replace("-", " ").strip()
        if log_date_norm != today_str_norm:
            continue
        machine = log.get('Machine Name', '').lower()
        if ("tripod" in machine or "barrier" in machine) and "main gate" not in machine:
            valid_logs.append(log)

    if not valid_logs:
        return 0, False

    def parse_time(log):
        d_str = log.get('Date', '').replace("-", " ").strip()
        t_str = log.get('Time', '').strip()
        time_str = f"{d_str} {t_str}"
        return datetime.strptime(time_str, "%d %b %Y %I:%M:%S %p")

    valid_logs.sort(key=parse_time)
    total_seconds = 0
    current_in_time = None

    for log in valid_logs:
        log_time = parse_time(log)
        direction = log.get('Direction', '').strip().lower()

        if direction == 'entry':
            if not current_in_time:
                current_in_time = log_time
        elif direction == 'exit':
            if current_in_time:
                total_seconds += (log_time - current_in_time).total_seconds()
                current_in_time = None 

    is_currently_in = False
    if current_in_time:
        is_currently_in = True
        total_seconds += (datetime.now() - current_in_time).total_seconds()

    return total_seconds, is_currently_in

def calculate_today_office_hours():
    """Prints the banner for today's actual time inside the office."""
    total_seconds, is_currently_in = _get_live_today_data()
    
    hours, remainder = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    print(f"\n==========================================")
    print(f"🏢 TODAY'S ACTUAL OFFICE TIME")
    print(f"==========================================")
    print(f"Total Time: {hours:02d} hours, {minutes:02d} mins, {seconds:02d} secs")
    
    if total_seconds == 0 and not is_currently_in:
        print(f"Status: 🏠 Currently in WFH")
    elif is_currently_in:
        print(f"Status: 🟢 Currently IN (Time includes up to now)")
    else:
        print(f"Status: 🔴 Currently OUT")
    print(f"==========================================\n")

def parse_hours_to_float(time_str):
    """Converts a 'HH:MM' string into a float for easy math."""
    if not time_str or time_str == "N/A" or time_str.strip() == "":
        return 0.0
    try:
        time_clean = time_str.split()[0]
        parts = time_clean.split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours + (minutes / 60.0)
    except ValueError:
        return 0.0

def show_monthly_report():
    """Reads attendance-report.csv and prints daily hours + weekly tracking summaries."""
    file_path = "attendance-report.csv"
    if not os.path.exists(file_path):
        print("\n❌ attendance-report.csv not found. Please run a Hard Refresh [h] first to fetch the data.")
        return

    now = datetime.now()
    current_month = now.month
    current_year = now.year

    today_str = now.strftime("%d-%b-%Y")
    
    today_processed = False
    weekly_totals = defaultdict(float)

    print(f"\n=======================================================")
    print(f"📊 MONTHLY REPORT (Daily Log - {now.strftime('%B %Y')})")
    print(f"=======================================================")
    print(f"| {'Date':<15} | {'Actual Working Hours - Swipes (A)':<37} |")
    print(f"|{'-'*17}|{'-'*39}|")

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get("Date", "N/A")
            hours_str = row.get("Actual Working Hours - Swipes (A)", "N/A").strip()
            status = row.get("Status", "").strip().lower()
            
            if date_str.strip() and date_str != "N/A":
                try:
                    dt = datetime.strptime(date_str, "%d-%b-%Y")
                except ValueError:
                    continue 
                
                is_today = (date_str == today_str)
                is_current_month = (dt.month == current_month and dt.year == current_year)
                
                # --- FALLBACK LOGIC: If portal hasn't calculated hours yet, do it locally ---
                if not hours_str or hours_str == "" or hours_str == "N/A":
                    calculated_hours = calculate_hours_from_swipes(date_str)
                    if calculated_hours:
                        hours_str = calculated_hours
                        if is_today:
                            hours_str += " (Live)"
                        else:
                            hours_str += " (Calc from Logs)"
                    else:
                        hours_str = "0:00"

                if is_today:
                    today_processed = True

                display_hours = hours_str
                daily_hours = parse_hours_to_float(hours_str)
                
                if "holiday" in status:
                    display_hours += " (+8h Holiday)"
                    daily_hours += 8.0
                elif "planned leave" in status:
                    display_hours += " (+8h Planned Leave)"
                    daily_hours += 8.0

                if is_current_month:
                    print(f"| {date_str:<15} | {display_hours:<37} |")
                
                monday = dt - timedelta(days=dt.weekday())
                sunday = monday + timedelta(days=6)
                
                week_str = f"{monday.strftime('%d-%b')} to {sunday.strftime('%d-%b')}"
                week_key = (monday, week_str)
                
                weekly_totals[week_key] += daily_hours

    # Append today if portal didn't generate an empty row for it yet
    if not today_processed:
        calculated_today = calculate_hours_from_swipes(today_str)
        if calculated_today:
            display_hours = f"{calculated_today} (Live)"
            hours_val = parse_hours_to_float(calculated_today)
        else:
            display_hours = "0:00 (WFH / No Swipes)"
            hours_val = 0.0

        print(f"| {today_str:<15} | {display_hours:<37} |")
        try:
            dt = datetime.strptime(today_str, "%d-%b-%Y")
            monday = dt - timedelta(days=dt.weekday())
            sunday = monday + timedelta(days=6)
            week_str = f"{monday.strftime('%d-%b')} to {sunday.strftime('%d-%b')}"
            week_key = (monday, week_str)
            weekly_totals[week_key] += hours_val
        except ValueError:
            pass

    print(f"=======================================================\n")

    if weekly_totals:
        print(f"===================================================================")
        print(f"📅 WEEKLY TARGET PROGRESS (Goal: 24 hrs/week)")
        print(f"===================================================================")
        print(f"| {'Week (Mon-Sun)':<20} | {'Total Hours':<15} | {'Remaining Hours':<22} |")
        print(f"|{'-'*22}|{'-'*17}|{'-'*24}|")
        
        first_day_of_current_month = datetime(current_year, current_month, 1)

        for (monday, week_str), total in sorted(weekly_totals.items()):
            sunday = monday + timedelta(days=6)
            if sunday >= first_day_of_current_month:
                total_hrs = int(total)
                total_mins = int(round((total - total_hrs) * 60))
                
                remaining = 24.0 - total
                if remaining < 0:
                    remaining = 0.0
                    
                rem_hrs = int(remaining)
                rem_mins = int(round((remaining - rem_hrs) * 60))
                
                total_str = f"{total_hrs:02d}:{total_mins:02d} / 24"
                
                if remaining > 0:
                    rem_str = f"{rem_hrs:02d}:{rem_mins:02d} hours left"
                    padding = 22
                else:
                    rem_str = "✅ Target Met"
                    padding = 21
                    
                print(f"| {week_str:<20} | {total_str:<15} | {rem_str:<{padding}} |")
            
        print(f"===================================================================\n")

def run_scraper():
    playwright = sync_playwright().start()

    def perform_scraping():
        browser = playwright.chromium.launch(channel="chrome", headless=False) 
        context = browser.new_context(
            http_credentials={
                'username': os.getenv('CYBAGE_USERNAME'), 
                'password': os.getenv('CYBAGE_PASSWORD')  
            }
        )
        page = context.new_page()
        
        print("\nNavigating to portal...")
        needs_vpn = False
        
        try:
            response = page.goto(URL, wait_until="networkidle", timeout=15000)
            if response and response.status == 404:
                needs_vpn = True
        except Exception:
            needs_vpn = True

        if needs_vpn:
            print("\n🚨 Portal returned 404. Redirecting to VPN...")
            max_retries = 3
            vpn_loaded = False
            
            for attempt in range(max_retries):
                try:
                    page.goto("https://ctvpn.cybage.com/sslvpn/Login/Login", wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_selector("#userName", state="visible", timeout=10000)
                    vpn_loaded = True
                    break 
                except Exception:
                    print(f"⚠️ Network not ready. Waiting 5 seconds before retrying...")
                    page.wait_for_timeout(5000) 
            
            if not vpn_loaded:
                print("❌ FATAL NETWORK ERROR: Could not reach the VPN portal.")
                return browser 
            
            print("\n🔐 Entering credentials automatically...")
            username = os.getenv('CYBAGE_USERNAME')
            password = os.getenv('CYBAGE_PASSWORD')
            if not username or not password:
                print("❌ Missing credentials. Check .env file.")
                return browser

            page.fill("#userName", username)
            page.fill("#passwordDisplayed", password)
            page.click("#LoginButton")
            
            print("\n=======================================================")
            print("📱 TWO-FACTOR AUTHENTICATION (2FA) REQUIRED.")
            print("=======================================================")
            input("\n➡️  Press [ENTER] here in the terminal once you have successfully passed 2FA... ")
            
            print("\n✅ Continuing! Routing to Report Builder URL...")
            try:
                page.goto("https://ctvpn.cybage.com/sslvpn/PT/https://cybagemis.cybage.com/Report%20Builder/RPTN/Reportpage.aspx", wait_until="networkidle")
            except Exception as e:
                print(f"❌ Failed to load Report Builder: {e}")
                return browser
            target_frame = page
        else:
            print("1. Clicking 'Reports' / 'Report Builder'")
            reports_btn = page.get_by_text("Report Builder", exact=True)
            reports_btn.wait_for(state="attached", timeout=15000)
            reports_btn.evaluate("node => node.click()") 
            page.wait_for_timeout(2000)

            print("Switching context to iframe...")
            page.wait_for_selector("iframe[name='RPTN_Reportpage']", state="attached", timeout=15000)
            target_frame = page.frame_locator("iframe[name='RPTN_Reportpage']")
            page.wait_for_timeout(2000)

        print("3. Clicking the tree expander arrow")
        expander = target_frame.locator("#TempleteTreeViewn3")
        expander.wait_for(state="visible", timeout=10000)
        expander.evaluate("node => node.click()") 
        page.wait_for_timeout(1500)

        print("4. Clicking 'Attendance Log Report'")
        attendance_log = target_frame.locator("#TempleteTreeViewt4")
        attendance_log.wait_for(state="visible", timeout=10000)
        attendance_log.evaluate("node => node.click()") 
        page.wait_for_timeout(2000) 

        first_date, today_date = get_report_dates()
        print(f"5. Entering dates: {first_date} to {today_date}")

        from_date_input = target_frame.locator("input[id$='_FromDateCalender_DTB']")
        to_date_input = target_frame.locator("input[id$='_ToDateCalender_DTB']")
        
        from_date_input.wait_for(state="visible", timeout=15000)
        from_date_input.evaluate(f"""(node) => {{
            node.value = '{first_date}';
            node.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}""")
        page.wait_for_timeout(500)
        to_date_input.evaluate(f"""(node) => {{
            node.value = '{today_date}';
            node.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}""")
        page.wait_for_timeout(500)
        to_date_input.press("Escape")
        page.wait_for_timeout(1500) 

        print("6. Clicking 'Generate Report' button")
        generate_btn = target_frame.locator("input[title='Generate Report']")
        generate_btn.wait_for(state="visible", timeout=10000)
        generate_btn.evaluate("node => node.click()")

        print("7. Waiting for the report table to generate...")
        data_table = target_frame.locator("td[id$='ReportCell']").last
        data_table.wait_for(state="visible", timeout=60000)
        page.wait_for_timeout(5000) 
        target_frame.locator("body").press("End")
        page.wait_for_timeout(2000)

        print("8. Extracting data into CSV...")
        rows = data_table.locator("tr").all()
        csv_data = []
        for row in rows: 
            cells = row.locator("th, td").all()
            row_data = [cell.inner_text().strip() for cell in cells]
            if len(row_data) >= 12 and "-" in row_data[2]:
                csv_data.append(row_data)

        print("9. Saving to attendance-report.csv...")
        headers = [
            "Employee ID", "Employee Name", "Date", "Swipe Count", "In Time", "Out Time",
            "Total Working Hours - Swipes", "Actual Working Hours - Swipes (A)",
            "Total Working Hours - WFH", "Actual Working Hours - WFH (B)",
            "Actual Working Hours Swipe (A) + WFH (B) (HH:MM)", "Status",
            "First Half Status", "Second Half Status"
        ]
        with open("attendance-report.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(csv_data)

        print("10. Clicking Back to Filters...")
        target_frame.locator("#BackImage").evaluate("node => node.click()")
        page.wait_for_timeout(2000)

        print("11. Clicking 'Today's and Yesterday's Swipe Log'")
        target_frame.locator("#TempleteTreeViewt7").evaluate("node => node.click()")
        page.wait_for_timeout(2000)

        # --- Ordered loop for Yesterday ("0") then Today ("1") ---
        all_swipe_data = []
        swipe_targets = [("0", "Yesterday"), ("1", "Today")]

        for index, (day_val, day_name) in enumerate(swipe_targets):
            print(f"\n12. Selecting '{day_name}' from dropdown...")
            try:
                day_dropdown = target_frame.locator("select[title='Day']")
                day_dropdown.wait_for(state="visible", timeout=10000)
                day_dropdown.select_option(value=day_val)

                print(f"13. Clicking 'Generate Report' for {day_name}...")
                target_frame.locator("input[title='Generate Report']").evaluate("node => node.click()")
                page.wait_for_timeout(5000)  

                no_data_text = "Sorry, data is not available, so report cannot be generated."
                no_data_locator = target_frame.get_by_text(no_data_text)

                if no_data_locator.is_visible():
                    print(f"⚠️ No data found for {day_name}. Skipping extraction.")
                else:
                    today_data_table = target_frame.locator("#ReportViewer1 [id$='ReportCell']").last
                    today_data_table.wait_for(state="visible", timeout=30000)

                    print(f"14. Extracting {day_name}'s data...")
                    today_rows = today_data_table.locator("tr").all()
                    
                    for row in today_rows[8:]: 
                        cells = row.locator("th, td").all()
                        row_data = [cell.inner_text().strip() for cell in cells]
                        if any(row_data):
                            all_swipe_data.append(row_data)

                if index < len(swipe_targets) - 1:
                    print("    Clicking Back to Filters...")
                    target_frame.locator("#BackImage").evaluate("node => node.click()")
                    page.wait_for_timeout(2000)

            except Exception as e:
                print(f"⚠️ Could not pull {day_name} logs. Proceeding anyway...")

        print("\n15. Saving raw swipe data to timetable-log.csv...")
        swipe_headers = ["Employee ID", "Date", "Machine Name", "Direction", "Time"]
        with open("timetable-log.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(swipe_headers)
            writer.writerows(all_swipe_data)

        print(f"\n✅ Success! Saved {len(csv_data)} attendance records and {len(all_swipe_data)} total swipe records.")
        return browser

    # Run the initial scrape process
    browser = perform_scraping()
    calculate_today_office_hours()

    # INTERACTIVE TERMINAL MENU
    while True:
        print("\n" + "="*45)
        print(" OPTIONS MENU")
        print(" [r] Refresh (Recalculate time locally)")
        print(" [h] Hard Refresh (Close browser & refetch data)")
        print(" [m] Monthly Report (Show dates, hours & weekly target)")
        print(" [q] Quit (Close browser and exit)")
        print("="*45)
        
        choice = input("Select an option: ").strip().lower()

        if choice == 'q':
            print("Shutting down... Goodbye!")
            break
        elif choice == 'r':
            print("⏳ Recalculating time using local logs...")
            calculate_today_office_hours()
        elif choice == 'h':
            print("🔄 Hard Refresh initiated! Closing browser and restarting process...")
            try:
                browser.close() 
            except Exception as e:
                print(f"Warning during browser close: {e}")
            browser = perform_scraping()
            calculate_today_office_hours()
        elif choice == 'm':
            show_monthly_report()
        else:
            print("❌ Invalid option. Please enter 'r', 'h', 'm', or 'q'.")

    # Cleanup memory and browser on quit
    try:
        browser.close()
    except:
        pass
    playwright.stop()

if __name__ == "__main__":
    run_scraper()