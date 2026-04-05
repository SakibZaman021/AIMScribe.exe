# AIMScribe Client Demo Setup

## Quick Start Guide for Client's PC

### What You Need
1. **Windows PC** with microphone
2. **Python 3.11+** installed
3. **Node.js 18+** installed
4. **Backend URL** (provided by AIMScribe team)

### Setup Steps

#### Step 1: Get the Backend URL
Ask the AIMScribe team for the demo backend URL:
```
https://xxxx.ngrok.io  (or similar)
```

#### Step 2: Configure the Recorder
1. Open `recorder\cloud_config.env`
2. Replace the URL:
```env
AIMSCRIBE_BACKEND_URL=https://your-provided-url.ngrok.io
```

#### Step 3: Configure CMED Web
1. Open `cmed-web\.env.local` (create if doesn't exist)
2. Add:
```env
NEXT_PUBLIC_BACKEND_URL=https://your-provided-url.ngrok.io
```

#### Step 4: Install Dependencies (First Time Only)

**Recorder:**
```batch
cd recorder
pip install -r requirements.txt
```

**CMED Web:**
```batch
cd cmed-web
npm install
```

#### Step 5: Start the System

**Option A: Use the quick start script**
```batch
demo-start.bat
```

**Option B: Start manually (2 terminals)**

Terminal 1 - Recorder:
```batch
cd recorder
start-cloud.bat
```

Terminal 2 - CMED Web:
```batch
cd cmed-web
npm run dev
```

#### Step 6: Open CMED Dashboard
Open browser: `http://localhost:3000`

---

## How to Use

### 1. Patient Entry (Reception)
- Fill in Patient ID, Name, Age, Gender
- Add Health Screening data (BP, pulse, etc.)
- Click "Go to Doctor Dashboard"

### 2. Start Recording (Doctor)
- Click "Patient History" tab
- Recording starts automatically (red indicator)
- Talk naturally - system records audio

### 3. View Results
- After ~3 minutes, NER results appear
- Prescription fields populate automatically
- Doctor can edit as needed

### 4. Stop Recording
- Click "Stop Recording" button
- Final NER extraction runs
- Review and print prescription

---

## Troubleshooting

### "Cannot reach backend"
- Check if you have the correct URL in cloud_config.env
- Make sure you have internet connection
- Contact AIMScribe team to verify backend is running

### "Recording not starting"
- Make sure microphone is connected
- Allow microphone permission if prompted
- Check if recorder is running (system tray icon)

### "NER not appearing"
- Wait at least 3 minutes (system processes in batches)
- Check if "Clip uploaded" messages appear in recorder
- Refresh the dashboard page

---

## Contact
For technical support during demo:
- [Your contact info here]
