@echo off
:: Weekly valuation pipeline runner for Windows Task Scheduler.
:: Task Scheduler does not inherit the user shell environment, so weekly_run.py
:: loads .env via load_dotenv() automatically — no env setup needed here.

cd /d "F:\dev\Portfolio\business-valuation-tool"
"C:\Python314\python.exe" -m scheduler.weekly_run --markets KR,US --max-per-market 5
