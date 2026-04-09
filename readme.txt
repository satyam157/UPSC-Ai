**UPSC-Ai URL: **[Link Text](https://upsc-ai-1l60.onrender.com)

pip install fastapi uvicorn streamlit requests feedparser python-dotenv groq PyPDF2
pip install streamlit feedparser groq python-dotenv PyPDF2


pip install -r requirements.txt
streamlit run app.py

python -m streamlit run app.py


net start postgresql-x64-18

GitHub PAT TOKEN: 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




"add GPT-like answer explanations + answer evaluation + scoring system"
"add answer evaluation + UPSC scoring + mains answer writing checker"


















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


