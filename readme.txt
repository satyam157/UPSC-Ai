**UPSC-Ai**

pip install fastapi uvicorn streamlit requests feedparser python-dotenv groq PyPDF2
pip install streamlit feedparser groq python-dotenv PyPDF2


pip install -r requirements.txt
streamlit run app.py

python -m streamlit run app.py


net start postgresql-x64-18


The News Display Limit is structured across database query and UI levels:

1. Global Database Query Limit (news_display_limit)
Current Value: 600 articles (active in system_config).
How it works: When fetching news from PostgreSQL in 

get_news()
, it queries the most recent articles up to this limit:
sql
SELECT title, content, date, url, source, category 
FROM news 
ORDER BY date DESC, id DESC 
LIMIT 600;
2. Daily Database Retention Cap (news_max_per_day)
Current Value: 40 articles per day (active in system_config).
How it works: In 

trim_news_to_max()
, regular news and PIB articles are scored and trimmed to keep the top 40 items per date (Editorials, Explained, and Opinion pieces are exempt and always kept).
3. UI Display Limits per Date Expander (

page_ca.py
)
When browsing news grouped by Year ➔ Month ➔ Date, each category tab applies a per-date display limit:

All News Tab: up to 50 items per date (limit=50)
Editorials Tab: up to 20 items per date (limit=20)
Explained Tab: up to 20 items per date (limit=20)
PIB Tab: up to 15 items per date (limit=15)
Manual Sync Tab: up to 50 items per date (limit=50)
⚙️ How to Adjust the Limit:
As an administrator, you can change both values at any time from:

Admin Panel ➔ 📰 News & System Settings tab:

News Display Limit: Adjustable from 50 to 2,000 (step 50).
Max News Per Day: Adjustable from 10 to 100 (step 5).





❌ ERROR EXPLAINED
error fixes:
ENOENT: no such file or directory, lstat 'C:\Users\91990\AppData\Roaming\npm'
👉 Meaning:
npm is trying to access a folder
That folder does not exist


✅ FIX (WORKS 100%)
🥇 STEP 1 — Create Missing Folder

Manually create this folder:

C:\Users\91990\AppData\Roaming\npm
How:
Press Win + R
Type:
%appdata%
Open folder
Create new folder → name it:
npm
🥈 STEP 2 — Restart Terminal

Close PowerShell → reopen

🥉 STEP 3 — Verify Node & npm

Run:

node -v
npm -v

👉 If both show versions → OK
👉 If not → reinstall Node

🧰 STEP 4 — If still broken (RECOMMENDED CLEAN FIX)

Reinstall Node properly:

1. Go to:

👉 Node.js

2. Download:

👉 LTS version

3. Install with:
✅ Add to PATH (IMPORTANT)
🧹 STEP 5 — Reset npm (if needed)

Run:

npm config set prefix "%APPDATA%\npm"
🚀 STEP 6 — Run React Again
npx create-react-app upsc-dashboard
⚡ ALTERNATIVE (FASTER METHOD)

If CRA still fails, use Vite (better + faster):

npm create vite@latest upsc-dashboard
cd upsc-dashboard
npm install
npm run dev

👉 Open:

http://localhost:5173
🧠 WHY THIS HAPPENED
npm folder deleted/corrupted
Node installed incorrectly
PATH not set properly

👉 Use Vite instead of CRA


