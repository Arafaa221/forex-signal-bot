# FOREX SIGNAL BOT — Deployment Guide

## What this bot does
- Scans EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CHF every hour
- Uses 5 strategies: Z-Score, RSI, MACD, EMA Cross, Bollinger Bands
- Sends Telegram alert ONLY when 4+/5 strategies agree (strong signal)
- Sends hourly summary showing all pair statuses
- Runs 24/7 on free server — works even when phone is off

---

## DEPLOY ON RENDER.COM (FREE — Recommended)

### Step 1 — GitHub (free account needed)
1. Go to github.com → Sign up free
2. Click "New repository"
3. Name it: forex-signal-bot
4. Click "Create repository"
5. Upload these 4 files: bot.py, requirements.txt, render.yaml, Procfile

### Step 2 — Render.com
1. Go to render.com → Sign up with GitHub
2. Click "New +" → "Background Worker"
3. Connect your GitHub repo (forex-signal-bot)
4. Render auto-detects render.yaml — click Deploy
5. Wait 2-3 minutes for build to complete
6. Check Telegram — you'll get the startup message ✅

---

## DEPLOY ON RAILWAY.APP (Alternative)

### Step 1 — GitHub same as above

### Step 2 — Railway
1. Go to railway.app → Login with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select forex-signal-bot
4. Add environment variables:
   - TELEGRAM_TOKEN = your token
   - TELEGRAM_CHAT  = your chat id
   - TWELVE_API_KEY = your api key
   - MIN_AGREE = 4
   - INTERVAL = 1h
5. Deploy → check Telegram ✅

---

## What you'll receive on Telegram

### Every hour — Summary:
```
🔍 HOURLY SCAN COMPLETE — 14:00 UTC
📊 Results for all 5 pairs:
🟢 BUY signals:  2
🔴 SELL signals: 1
⏸ HOLD:         2
⏳ No strong signals yet — waiting for 4+/5 setup
Next scan in 1 hour.
```

### When strong signal fires:
```
📊 FOREX SIGNAL ALERT
🟢 EUR/USD — BUY
⚡ STRONG SIGNAL (4/5)

💰 Entry: 1.08450
🎯 Take Profit: 1.08810 (+36 pips)
🛑 Stop Loss: 1.08270 (-18 pips)

📈 Strategy Agreement: 4/5
  ✅ Z-Score: Z=-1.52 Mild oversold
  ✅ RSI: RSI=32 Oversold
  ✅ MACD: MACD hist=+0.00012 Bullish
  ✅ EMA: Uptrend: EMA9 > EMA21
  ⏸ Bollinger: Mid-band (45%)

Olymp Trade Action:
Open UP / HIGHER trade on EUR/USD
Use Forex Mode — hold until TP or SL hit
Risk only 1-3% of your balance
```

---

## Customization (edit bot.py)

Change scan interval:    INTERVAL = "4h"  (options: 1h, 4h, 1day)
Change min strategies:   MIN_AGREE = 3    (lower = more signals)
Add/remove pairs:        PAIRS list at top of file

---

## Cost: COMPLETELY FREE
- GitHub: Free
- Render.com: Free tier (750 hours/month = enough for 24/7)
- Railway.app: $5 free credits/month (enough for ~3 months)
