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
WFH_LOG_FILE = "esplus-wfh-log.csv"
SWIPE_LOG_FILE = "timetable-log.csv"
REPORT_FILE = "attendance-report.csv"

def get_report_dates():
    """Calculates the Monday of the week containing the 1st of the month to keep the date range short."""
    now = datetime.now()
    today_date = now.strftime("%d-%b-%Y")
    
    first_of_month = now.replace(day=1)
    days_to_subtract = first_of_month.weekday()
    start_date = first_of_month - timedelta(days=days_to_subtract)
    
    first_date = start_date.strftime("%d-%b-%Y")
    return first_date, today_date

def parse_hours_to_float(time_str):
    """Converts a 'HH:MM' string or float string into a float for easy math."""
    if not time_str or str(time_str).strip() in ["N/A", ""]:
        return 0.0
    try:
        time_clean = str(time_str).split()[0]
        if ":" in time_clean:
            parts = time_clean.split(":")
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            return hours + (minutes / 60.0)
        else:
            return float(time_clean)
    except ValueError:
        return 0.0

def float_to_hhmm(f_hours):
    """Converts float hours to HH:MM format."""
    hrs = int(f_hours)
    mins = int(round((f_hours - hrs) * 60))
    if mins == 60:
        hrs += 1
        mins = 0
    return f"{hrs}:{mins:02d}"

def calculate_hours_from_swipes(target_date):
    """Calculates actual in-office time for a specific date using raw swipe logs."""
    if not os.path.exists(SWIPE_LOG_FILE):
        return None

    target_date_norm = target_date.replace("-", " ").strip()

    with open(SWIPE_LOG_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        logs = list(reader)

    valid_logs = []
    for log in logs:
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

    today_str_norm = datetime.now().strftime("%d %b %Y")
    if current_in_time and target_date_norm == today_str_norm:
        total_seconds += (datetime.now() - current_in_time).total_seconds()

    if total_seconds == 0:
        return None

    hours, remainder = divmod(int(total_seconds), 3600)
    minutes = remainder // 60
    return f"{hours}:{minutes:02d}"

def get_wfh_from_local_log(target_date):
    """Fetches WFH hours from the local ESPlus log CSV."""
    if not os.path.exists(WFH_LOG_FILE):
        return None
    target_dt = datetime.strptime(target_date, "%d-%b-%Y")
    target_iso = target_dt.strftime("%Y-%m-%d")
    
    with open(WFH_LOG_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Date") == target_iso:
                # ActiveTime is in minutes (e.g., 38.95). Convert it to float hours (e.g., 0.649) before converting to HH:MM.
                active_minutes = float(row.get("ActiveTime", 0))
                return float_to_hhmm(active_minutes / 60.0)
    return None

def show_monthly_report():
    """Reads attendance-report.csv and prints WFO + WFH summaries."""
    if not os.path.exists(REPORT_FILE):
        print("\n❌ attendance-report.csv not found. Please run a Hard Refresh [h] first.")
        return

    now = datetime.now()
    current_month = now.month
    current_year = now.year

    recent_dates = [
        (now - timedelta(days=1)).strftime("%d-%b-%Y"),
        now.strftime("%d-%b-%Y")
    ]
    processed_dates = set()
    weekly_wfo = defaultdict(float)
    weekly_wfh = defaultdict(float)

    print(f"\n=========================================================================================")
    print(f"📊 MONTHLY REPORT (Daily Log - {now.strftime('%B %Y')})")
    print(f"=========================================================================================")
    print(f"| {'Date':<15} | {'WFO Hours (A)':<22} | {'WFH Hours (B)':<22} | {'Total':<14} |")
    print(f"|{'-'*17}|{'-'*24}|{'-'*24}|{'-'*16}|")

    with open(REPORT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get("Date", "N/A")
            if date_str == "N/A" or not date_str.strip():
                continue
            
            try:
                dt = datetime.strptime(date_str, "%d-%b-%Y")
            except ValueError:
                continue 
                
            processed_dates.add(date_str)
            is_current_month = (dt.month == current_month and dt.year == current_year)
            
            wfo_str = row.get("Actual Working Hours - Swipes (A)", "").strip()
            wfh_str = row.get("Actual Working Hours - WFH (B)", "").strip()
            status = row.get("Status", "").strip().lower()

            # Handle WFO Fallback
            if not wfo_str or wfo_str == "N/A":
                calc_wfo = calculate_hours_from_swipes(date_str)
                wfo_str = f"{calc_wfo} (*)" if calc_wfo else "0:00"

            wfo_val = parse_hours_to_float(wfo_str)

            # Handle WFH Fallback (ONLY if WFO is zero)
            if wfo_val > 0:
                wfh_str = "0:00" # WFO overrides WFH
            elif not wfh_str or wfh_str == "N/A":
                calc_wfh = get_wfh_from_local_log(date_str)
                wfh_str = f"{calc_wfh} (*)" if calc_wfh else "0:00"

            wfh_val = parse_hours_to_float(wfh_str)
            
            # Holiday Handling
            if "holiday" in status:
                wfo_str += " (+8h H)"
                wfo_val += 8.0
            elif "planned leave" in status:
                wfo_str += " (+8h PL)"
                wfo_val += 8.0

            total_val = wfo_val + wfh_val

            if is_current_month:
                print(f"| {date_str:<15} | {wfo_str:<22} | {wfh_str:<22} | {float_to_hhmm(total_val):<14} |")
            
            monday = dt - timedelta(days=dt.weekday())
            week_str = f"{monday.strftime('%d-%b')} to {(monday + timedelta(days=6)).strftime('%d-%b')}"
            
            weekly_wfo[(monday, week_str)] += wfo_val
            weekly_wfh[(monday, week_str)] += wfh_val

    # Append Missing Recent Days (Yesterday & Today) if not generated by portal yet
    for date_str in recent_dates:
        if date_str not in processed_dates:
            dt = datetime.strptime(date_str, "%d-%b-%Y")
            
            calc_wfo = calculate_hours_from_swipes(date_str)
            wfo_str = f"{calc_wfo} (Live)" if calc_wfo else "0:00"
            wfo_val = parse_hours_to_float(calc_wfo)
            
            if wfo_val > 0:
                wfh_str = "0:00"
                wfh_val = 0.0
            else:
                calc_wfh = get_wfh_from_local_log(date_str)
                wfh_str = f"{calc_wfh} (Live)" if calc_wfh else "0:00"
                wfh_val = parse_hours_to_float(calc_wfh)
            
            total_val = wfo_val + wfh_val

            if dt.month == current_month and dt.year == current_year:
                print(f"| {date_str:<15} | {wfo_str:<22} | {wfh_str:<22} | {float_to_hhmm(total_val):<14} |")
                
            monday = dt - timedelta(days=dt.weekday())
            week_str = f"{monday.strftime('%d-%b')} to {(monday + timedelta(days=6)).strftime('%d-%b')}"
            
            weekly_wfo[(monday, week_str)] += wfo_val
            weekly_wfh[(monday, week_str)] += wfh_val

    print(f"=========================================================================================\n")

    if weekly_wfo or weekly_wfh:
        print(f"=====================================================================================")
        print(f"📅 WEEKLY PROGRESS (Goal: 40h | WFO: 24h, WFH: 16h)")
        print(f"=====================================================================================")
        print(f"| {'Week (Mon-Sun)':<18} | {'WFO Done/Rem':<15} | {'WFH Done/Rem':<15} | {'Total Achieved':<18} |")
        print(f"|{'-'*20}|{'-'*17}|{'-'*17}|{'-'*20}|")
        
        first_day_of_month = datetime(current_year, current_month, 1)

        for (monday, week_str) in sorted(weekly_wfo.keys()):
            sunday = monday + timedelta(days=6)
            if sunday >= first_day_of_month:
                wfo_tot = weekly_wfo[(monday, week_str)]
                wfh_tot = weekly_wfh[(monday, week_str)]
                total_all = wfo_tot + wfh_tot
                
                wfo_rem = max(0.0, 24.0 - wfo_tot)
                wfh_rem = max(0.0, 16.0 - wfh_tot)
                
                wfo_display = f"{float_to_hhmm(wfo_tot)} / {float_to_hhmm(wfo_rem)}"
                wfh_display = f"{float_to_hhmm(wfh_tot)} / {float_to_hhmm(wfh_rem)}"
                
                if total_all >= 40.0:
                    tot_display = f"✅ {float_to_hhmm(total_all)} (Met)"
                else:
                    tot_display = f"⚠️ {float_to_hhmm(total_all)} / 40:00"

                print(f"| {week_str:<18} | {wfo_display:<15} | {wfh_display:<15} | {tot_display:<18} |")
            
        print(f"=====================================================================================\n")

def run_scraper():
    playwright = sync_playwright().start()

    def perform_scraping():
        username = os.getenv('CYBAGE_USERNAME')
        password = os.getenv('CYBAGE_PASSWORD')
        
        if not username or not password:
            print("❌ Missing credentials. Check .env file.")
            return None

        browser = playwright.chromium.launch(channel="chrome", headless=False) 
        
        # This parameter intercepts native browser pop-ups (HTTP Basic Auth) and injects the credentials automatically
        context = browser.new_context(
            http_credentials={
                'username': username,
                'password': password
            }
        )

        # ---------------------------------------------------------
        # 1. MIS ATTENDANCE & SWIPE SCRAPING LOGIC
        # ---------------------------------------------------------
        page = context.new_page()
        print("\nNavigating to MIS portal...")
        
        try:
            # DIRECT CONNECTION: No retry loop. Playwright will handle the browser pop-up Auth instantly.
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            print("\n✅ Reached MIS URL and logged in!")
            page.wait_for_timeout(2000) 
        except Exception as e:
            print(f"❌ Failed to reach MIS portal. Error: {e}")
            return browser

        print("1. Clicking 'Reports' / 'Report Builder'")
        reports_btn = page.get_by_text("Report Builder", exact=True)
        reports_btn.wait_for(state="attached", timeout=15000)
        reports_btn.evaluate("node => node.click()") 
        page.wait_for_timeout(2000)

        print("2. Switching context to iframe...")
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

        print(f"9. Saving to {REPORT_FILE}...")
        headers = [
            "Employee ID", "Employee Name", "Date", "Swipe Count", "In Time", "Out Time",
            "Total Working Hours - Swipes", "Actual Working Hours - Swipes (A)",
            "Total Working Hours - WFH", "Actual Working Hours - WFH (B)",
            "Actual Working Hours Swipe (A) + WFH (B) (HH:MM)", "Status",
            "First Half Status", "Second Half Status"
        ]
        with open(REPORT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(csv_data)

        print("10. Clicking Back to Filters...")
        target_frame.locator("#BackImage").evaluate("node => node.click()")
        page.wait_for_timeout(2000)

        print("11. Clicking 'Today's and Yesterday's Swipe Log'")
        target_frame.locator("#TempleteTreeViewt7").evaluate("node => node.click()")
        page.wait_for_timeout(2000)

        all_swipe_data = []
        swipe_targets = [("0", "Yesterday"), ("1", "Today")]

        for index, (day_val, day_name) in enumerate(swipe_targets):
            print(f"\n12. Selecting '{day_name}' from dropdown...")
            try:
                day_dropdown = target_frame.locator("select[title='Day']")
                day_dropdown.wait_for(state="visible", timeout=10000)
                day_dropdown.select_option(value=day_val)

                target_frame.locator("input[title='Generate Report']").evaluate("node => node.click()")
                page.wait_for_timeout(5000)  

                no_data_text = "Sorry, data is not available, so report cannot be generated."
                no_data_locator = target_frame.get_by_text(no_data_text)

                if no_data_locator.is_visible():
                    print(f"⚠️ No data found for {day_name}. Skipping extraction.")
                else:
                    today_data_table = target_frame.locator("#ReportViewer1 [id$='ReportCell']").last
                    today_data_table.wait_for(state="visible", timeout=30000)

                    today_rows = today_data_table.locator("tr").all()
                    
                    for row in today_rows[8:]: 
                        cells = row.locator("th, td").all()
                        row_data = [cell.inner_text().strip() for cell in cells]
                        if any(row_data):
                            all_swipe_data.append(row_data)

                if index < len(swipe_targets) - 1:
                    target_frame.locator("#BackImage").evaluate("node => node.click()")
                    page.wait_for_timeout(2000)

            except Exception as e:
                print(f"⚠️ Could not pull {day_name} logs.")

        print(f"\n15. Saving raw swipe data to {SWIPE_LOG_FILE}...")
        swipe_headers = ["Employee ID", "Date", "Machine Name", "Direction", "Time"]
        with open(SWIPE_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(swipe_headers)
            writer.writerows(all_swipe_data)
            
        page.close()

        # ---------------------------------------------------------
        # 2. ESPLUS WFH SCRAPING LOGIC (ONE BY ONE)
        # ---------------------------------------------------------
        now = datetime.now()
        yesterday_fmt = (now - timedelta(days=1)).strftime("%d %b %Y")
        today_fmt = now.strftime("%d %b %Y")
        
        yesterday_iso = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        today_iso = now.strftime("%Y-%m-%d")

        has_swipes_yesterday = any(row[1].strip().replace("-", " ") == yesterday_fmt for row in all_swipe_data)
        has_swipes_today = any(row[1].strip().replace("-", " ") == today_fmt for row in all_swipe_data)

        dates_to_fetch = []
        if not has_swipes_yesterday:
            dates_to_fetch.append(yesterday_iso)
        if not has_swipes_today:
            dates_to_fetch.append(today_iso)

        if dates_to_fetch:
            print(f"\n🌐 No swipes found for {len(dates_to_fetch)} day(s). Extracting WFH Data from ESPlus one by one...")
            es_page = context.new_page()
            es_page.goto("https://esplusapps.cybage.com/ESPlusPlatform", wait_until="domcontentloaded")
            
            try:
                if es_page.locator("input[type='password']").is_visible(timeout=5000):
                    print("   -> Found ESPlus login page. Submitting credentials...")
                    user_input = es_page.locator("input[type='text'], input[type='email'], input[name='username']").first
                    if user_input.is_visible():
                        user_input.fill(username)
                    es_page.locator("input[type='password']").fill(password)
                    es_page.keyboard.press("Enter")
                    es_page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass 
            
            wfh_logs = []
            if os.path.exists(WFH_LOG_FILE):
                with open(WFH_LOG_FILE, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    wfh_logs = list(reader)

            for single_date in dates_to_fetch:
                print(f"   -> Extracting ActiveTime strictly for date: {single_date}")
                api_url = f"https://esplusapps.cybage.com/ESPlusManagerDashboardAPIV2/api/activity/personal?from={single_date}&to={single_date}"
                
                es_page.goto(api_url, wait_until="domcontentloaded")
                xml_content = es_page.content()
                
                match = re.search(r"<ActiveTime[^>]*>([\d\.]+)</ActiveTime>", xml_content)
                active_time = match.group(1) if match else "0.0"
                
                wfh_logs = [row for row in wfh_logs if row[0] != single_date]
                wfh_logs.append([single_date, active_time])
                
            with open(WFH_LOG_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "ActiveTime"])
                writer.writerows(wfh_logs)
            
            print("✅ ESPlus WFH data synced locally.")
            es_page.close()
        else:
            print("\n✅ Swipes found for all recent days. Skipping ESPlus WFH fetch.")

        print(f"\n✅ Data collection complete!")
        return browser

    browser = perform_scraping()

    while True:
        if browser is None:
            break

        print("\n" + "="*45)
        print(" OPTIONS MENU")
        print(" [m] Monthly Report (40h Breakdown)")
        print(" [h] Hard Refresh (Fetch MIS + WFH data)")
        print(" [q] Quit (Close browser and exit)")
        print("="*45)
        
        choice = input("Select an option: ").strip().lower()

        if choice == 'q':
            print("Shutting down... Goodbye!")
            break
        elif choice == 'h':
            print("🔄 Hard Refresh initiated...")
            try:
                browser.close() 
            except Exception:
                pass
            browser = perform_scraping()
        elif choice == 'm':
            show_monthly_report()
        else:
            print("❌ Invalid option. Please enter 'h', 'm', or 'q'.")

    try:
        browser.close()
    except:
        pass
    playwright.stop()

if __name__ == "__main__":
    run_scraper()