# Cybage MIS Attendance Scraper

A Python-based automation tool that uses Playwright to scrape attendance logs and raw swipe data from the Cybage MIS portal, as well as Work-From-Home (WFH) activity hours from ESPlus. It features a built-in terminal dashboard to track your live office hours and calculate your weekly progress against your 40-hour goal.

> 🚀 **Coming Soon:** A full Graphical User Interface (GUI) to make tracking your hours even easier and more intuitive!

---

## 🌟 Features

- ✅ **Dual-Tracking System**
  - Track both Work-From-Office (WFO) swipes and Work-From-Home (WFH) active hours.

- 🤖 **Automated Web Scraping**
  - Logs into the MIS portal and ESPlus securely to extract attendance reports, swipe logs, and active times.

- 🔄 **Smart Network Retry & Auto-Login**
  - Automatically waits for your corporate network/VPN to stabilize (resolving DNS errors) and seamlessly injects your credentials into native browser pop-ups.

- 🧠 **Smart Fallback Logic**
  - If the MIS portal hasn't generated the final hours for yesterday or today, the script calculates live office hours from raw swipes or fetches live WFH hours from ESPlus.

- 📊 **40-Hour Weekly Goal Dashboard**
  - Displays a clean terminal UI showing progress toward weekly goals (e.g., **24h WFO + 16h WFH = 40h Total**).

- 🖥️ **Interactive Terminal Menu**
  - Quickly view reports or trigger a hard refresh without restarting the console.

---

# 📋 Prerequisites

Before running this project, ensure you have the following installed:

- Python **3.8+**
- Google Chrome (The scraper uses the Chrome browser channel.)
- Corporate Network / VPN Connection (Required for the Cybage portals to resolve.)

---

# 🚀 Installation & Setup

## 1. Clone the Repository

```bash
git clone https://github.com/pavankokane/cybage-attendance-scraper.git
cd cybage-attendance-scraper
```

---

## 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Set Up Your Credentials

Create a file named **`.env`** in the project root.

```env
CYBAGE_USERNAME=your_actual_username
CYBAGE_PASSWORD=your_actual_password
```

> **⚠️ Important:** Never commit or upload your `.env` file to GitHub.

---

# 💻 How to Use

Depending on your tracking needs, run one of the following scripts.

## Option A — Comprehensive 40-Hour Tracker (WFO + WFH)

```bash
python wfh-wfo.py
```

Tracks:

- Office Swipes
- ESPlus Active Hours
- Weekly 40-hour goal

---

## Option B — Office-Only Tracker

```bash
python wfo.py
```

Tracks:

- Physical office swipe hours
- Weekly 24-hour office goal

---

# 🔄 Initial Run Sequence

When the script starts:

1. Chrome launches automatically.
2. The script checks network connectivity.
3. If the MIS portal is unreachable, it retries every **5 seconds** for **up to one minute**, allowing time to connect to VPN.
4. Credentials from the `.env` file are automatically supplied to the native browser login prompt.
5. The scraper then:

   - Downloads the monthly attendance report.
   - Downloads today's swipe log.
   - Downloads yesterday's swipe log.
   - *(For `wfh-wfo.py` only)* If no swipe data exists for the previous 48 hours, it navigates to ESPlus and retrieves Active Time minutes.
   - Saves all reports as CSV files.
   - Launches the interactive dashboard.

---

# 🖥️ Interactive Menu

## `[m]` Monthly Report — 40h Breakdown

Displays:

- Daily WFO hours
- Daily WFH hours
- Weekly summaries
- Remaining hours for:
  - 24h WFO
  - 16h WFH
  - 40h Total

---

## `[h]` Hard Refresh — Fetch Fresh Data

This option:

- Closes the current browser session
- Starts a new Playwright instance
- Downloads fresh attendance reports
- Downloads fresh swipe logs
- Downloads fresh ESPlus logs

---

## `[r]` Refresh — Recalculate Time Locally *(Available only in `wfo.py`)*

Instantly recalculates your live office hours using the existing:

```text
timetable-log.csv
```

No browser launch required.

---

## `[q]` Quit

Safely:

- Closes the browser
- Cleans up Playwright processes
- Exits the application

---

# 📁 Project Structure

```text
cybage-attendance-scraper/
│
├── wfh-wfo.py                 # Comprehensive 40h tracker (MIS + ESPlus)
├── wfo.py                     # Office-only tracker
├── requirements.txt
├── pyproject.toml
├── .env                       # (User-created) Credentials
│
├── attendance-report.csv      # Auto-generated MIS attendance report
├── timetable-log.csv          # Auto-generated swipe log
├── esplus-wfh-log.csv         # Auto-generated WFH log (wfh-wfo.py only)
│
└── README.md
```

---

# 🛠️ Tech Stack

- Python
- Playwright
- python-dotenv

---

# 📄 License

This project is intended for **personal/internal automation use only**.

It is designed to simplify attendance tracking for employees by automating the retrieval of attendance logs, swipe records, and Work-From-Home activity from internal portals.

---