"""
FOREX SIGNAL BOT — 24/7 Server Version
Scans 5 pairs every hour, sends Telegram alerts on 4+/5 signals
"""

import os
import time
import math
import requests
import schedule
import logging
from datetime import datetime

# ── Config (set in environment variables or edit here) ────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8122870086:AAFERJ-M1IWLk_BrTqUA7imHK738sZH684M")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT",  "1548227658")
TWELVE_API_KEY = os.environ.get("TWELVE_API_KEY", "347054c86ce64751983ddc9257ceb778")
MIN_AGREE      = int(os.environ.get("MIN_AGREE", "4"))   # minimum strategies agreeing
INTERVAL       = os.environ.get("INTERVAL", "1h")        # 1h, 4h, 1day

PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF"]

PIP = {"EUR/USD": 0.0001, "GBP/USD": 0.0001,
       "USD/JPY": 0.01,   "AUD/USD": 0.0001, "USD/CHF": 0.0001}

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Track last signals to avoid duplicate alerts ──────────────────
last_signals = {}

# ── Fetch price data from Twelve Data ────────────────────────────
def fetch_closes(symbol, interval="1h", count=100):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":     symbol,
        "interval":   interval,
        "outputsize": count,
        "apikey":     TWELVE_API_KEY,
        "format":     "JSON"
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("status") == "error":
            raise ValueError(data.get("message", "API error"))
        values = data.get("values", [])
        if len(values) < 30:
            raise ValueError("Not enough data")
        # Reverse: oldest first
        closes = [float(v["close"]) for v in reversed(values)]
        highs  = [float(v["high"])  for v in reversed(values)]
        lows   = [float(v["low"])   for v in reversed(values)]
        return closes, highs, lows
    except Exception as e:
        log.warning(f"Fetch failed for {symbol}: {e}")
        return None, None, None

# ── Indicators ────────────────────────────────────────────────────
def z_score(closes, window=20):
    if len(closes) < window + 1:
        return 0.0
    sl = closes[-window-1:-1]
    mean = sum(sl) / window
    std  = math.sqrt(sum((x - mean)**2 for x in sl) / window)
    if std == 0:
        return 0.0
    return (closes[-1] - mean) / std

def rsi(closes, period=14):
    if len(closes) < period + 2:
        return 50.0
    sl = closes[-period-1:]
    gains = losses = 0.0
    for i in range(1, len(sl)):
        d = sl[i] - sl[i-1]
        if d > 0: gains += d
        else:     losses -= d
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100 - 100 / (1 + rs)

def ema(closes, period):
    if not closes:
        return 0.0
    k = 2 / (period + 1)
    e = closes[0]
    for c in closes[1:]:
        e = c * k + e * (1 - k)
    return e

def ema_arr(closes, period):
    k = 2 / (period + 1)
    out = [closes[0]]
    for c in closes[1:]:
        out.append(c * k + out[-1] * (1 - k))
    return out

def macd_hist(closes):
    if len(closes) < 27:
        return 0.0
    macd_line = []
    for i in range(26, len(closes) + 1):
        fast = ema(closes[i-12:i], 12)
        slow = ema(closes[i-26:i], 26)
        macd_line.append(fast - slow)
    if len(macd_line) < 9:
        return 0.0
    signal = ema(macd_line[-9:], 9)
    return macd_line[-1] - signal

def bollinger_pct(closes, window=20):
    if len(closes) < window + 1:
        return 0.5
    sl = closes[-window-1:]
    mean = sum(sl) / len(sl)
    std  = math.sqrt(sum((x - mean)**2 for x in sl) / len(sl))
    if std == 0:
        return 0.5
    upper = mean + 2 * std
    lower = mean - 2 * std
    return (closes[-1] - lower) / (upper - lower)

def atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return PIP.get("EUR/USD", 0.0001) * 15
    trs = []
    for i in range(-period, 0):
        h, l, pc = highs[i], lows[i], closes[i-1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / period

# ── 5 Strategy signals ────────────────────────────────────────────
def strat_zscore(closes):
    z = z_score(closes)
    if z <= -1.8: return "BUY",  f"Z={z:.2f} Strong oversold"
    if z >=  1.8: return "SELL", f"Z={z:.2f} Strong overbought"
    if z <= -1.2: return "BUY",  f"Z={z:.2f} Mild oversold"
    if z >=  1.2: return "SELL", f"Z={z:.2f} Mild overbought"
    return "HOLD", f"Z={z:.2f} Neutral"

def strat_rsi(closes):
    r = rsi(closes[-20:])
    if r <= 25: return "BUY",  f"RSI={r:.0f} Strongly oversold"
    if r >= 75: return "SELL", f"RSI={r:.0f} Strongly overbought"
    if r <= 35: return "BUY",  f"RSI={r:.0f} Oversold"
    if r >= 65: return "SELL", f"RSI={r:.0f} Overbought"
    return "HOLD", f"RSI={r:.0f} Neutral"

def strat_macd(closes):
    h = macd_hist(closes[-60:])
    if h > 0: return "BUY",  f"MACD hist=+{h:.5f} Bullish"
    if h < 0: return "SELL", f"MACD hist={h:.5f} Bearish"
    return "HOLD", "MACD flat"

def strat_ema(closes):
    e9  = ema_arr(closes[-30:], 9)
    e21 = ema_arr(closes[-30:], 21)
    if len(e9) < 2:
        return "HOLD", "Not enough data"
    if e9[-1] > e21[-1] and e9[-2] <= e21[-2]:
        return "BUY",  "EMA9 crossed above EMA21"
    if e9[-1] < e21[-1] and e9[-2] >= e21[-2]:
        return "SELL", "EMA9 crossed below EMA21"
    if e9[-1] > e21[-1]:
        return "BUY",  "Uptrend: EMA9 > EMA21"
    if e9[-1] < e21[-1]:
        return "SELL", "Downtrend: EMA9 < EMA21"
    return "HOLD", "EMA9 ≈ EMA21"

def strat_boll(closes):
    bp = bollinger_pct(closes[-25:])
    if bp <= 0.05: return "BUY",  f"At lower Bollinger band ({bp*100:.0f}%)"
    if bp >= 0.95: return "SELL", f"At upper Bollinger band ({bp*100:.0f}%)"
    if bp <= 0.15: return "BUY",  f"Near lower band ({bp*100:.0f}%)"
    if bp >= 0.85: return "SELL", f"Near upper band ({bp*100:.0f}%)"
    return "HOLD", f"Mid-band ({bp*100:.0f}%)"

def analyse(closes, highs, lows, pair):
    r0, d0 = strat_zscore(closes)
    r1, d1 = strat_rsi(closes)
    r2, d2 = strat_macd(closes)
    r3, d3 = strat_ema(closes)
    r4, d4 = strat_boll(closes)

    votes  = [r0, r1, r2, r3, r4]
    buy    = votes.count("BUY")
    sell   = votes.count("SELL")

    if buy >= sell and buy > 0:
        sig, agree = "BUY", buy
    elif sell > buy:
        sig, agree = "SELL", sell
    else:
        sig, agree = "HOLD", 0

    conf = round(agree / 5 * 100)

    # ATR-based SL/TP
    atr_val = atr(highs, lows, closes)
    entry   = closes[-1]
    pip_size = PIP.get(pair, 0.0001)
    tp_pips = round(atr_val * 2 / pip_size)
    sl_pips = round(atr_val / pip_size)

    if sig == "BUY":
        tp = entry + atr_val * 2
        sl = entry - atr_val
    elif sig == "SELL":
        tp = entry - atr_val * 2
        sl = entry + atr_val
    else:
        tp = sl = entry

    details = {
        "Z-Score":  (r0, d0),
        "RSI":      (r1, d1),
        "MACD":     (r2, d2),
        "EMA":      (r3, d3),
        "Bollinger":(r4, d4),
    }

    return {
        "sig":     sig,
        "agree":   agree,
        "conf":    conf,
        "price":   entry,
        "tp":      tp,
        "sl":      sl,
        "tp_pips": tp_pips,
        "sl_pips": sl_pips,
        "details": details,
        "rsi_val": rsi(closes[-20:]),
        "z_val":   z_score(closes),
    }

# ── Send Telegram message ─────────────────────────────────────────
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT,
        "text":       text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log.info("Telegram sent ✓")
        else:
            log.warning(f"Telegram error: {r.text}")
    except Exception as e:
        log.error(f"Telegram failed: {e}")

# ── Format signal message ─────────────────────────────────────────
def format_message(pair, result, strength):
    sig   = result["sig"]
    emoji = "🟢" if sig == "BUY" else "🔴"
    arrow = "▲ UP / HIGHER" if sig == "BUY" else "▼ DOWN / LOWER"
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    strat_lines = ""
    icons = {"BUY": "✅", "SELL": "❌", "HOLD": "⏸"}
    for name, (s, d) in result["details"].items():
        strat_lines += f"  {icons[s]} {name}: {d}\n"

    msg = f"""📊 <b>FOREX SIGNAL ALERT</b>
{emoji} <b>{pair} — {sig}</b>
⚡ <b>{strength}</b>

💰 <b>Entry:</b> {result['price']:.5f}
🎯 <b>Take Profit:</b> {result['tp']:.5f} (+{result['tp_pips']} pips)
🛑 <b>Stop Loss:</b> {result['sl']:.5f} (-{result['sl_pips']} pips)

📈 <b>Strategy Agreement: {result['agree']}/5</b>
{strat_lines}
🕐 <b>Timeframe:</b> {INTERVAL} | <b>Conf:</b> {result['conf']}%
⏰ {now}

<b>Olymp Trade Action:</b>
Open <b>{arrow}</b> trade on {pair}
Use <b>Forex Mode</b> — hold until TP or SL hit
Risk only 1–3% of your balance

⚠️ Not financial advice. Always use SL."""

    return msg

# ── Scan all pairs ────────────────────────────────────────────────
def scan_all():
    log.info(f"=== SCANNING {len(PAIRS)} PAIRS [{INTERVAL}] ===")
    found = 0

    for pair in PAIRS:
        log.info(f"Scanning {pair}...")
        closes, highs, lows = fetch_closes(pair, INTERVAL, 100)

        if closes is None:
            log.warning(f"Skipping {pair} — no data")
            time.sleep(2)
            continue

        result = analyse(closes, highs, lows, pair)
        sig    = result["sig"]
        agree  = result["agree"]

        log.info(f"{pair}: {sig} {agree}/5 (conf {result['conf']}%)")

        # Only alert on 4+ agree and non-HOLD
        if agree >= MIN_AGREE and sig != "HOLD":
            # Check if signal changed from last scan
            last = last_signals.get(pair, {})
            is_new = (last.get("sig") != sig or last.get("agree") != agree)

            if is_new:
                strength = "🔥 PERFECT SIGNAL (5/5)" if agree == 5 else "⚡ STRONG SIGNAL (4/5)"
                msg = format_message(pair, result, strength)
                send_telegram(msg)
                log.info(f"  → ALERT SENT for {pair} {sig} {agree}/5")
                found += 1
            else:
                log.info(f"  → Same signal as last scan, no duplicate alert")

        last_signals[pair] = {"sig": sig, "agree": agree}

        # Delay between API calls (free plan rate limit)
        time.sleep(3)

    log.info(f"=== SCAN COMPLETE — {found} alerts sent ===\n")

    # Send summary to Telegram every scan
    now = datetime.utcnow().strftime("%H:%M UTC")
    buys  = sum(1 for p, v in last_signals.items() if v.get("sig") == "BUY")
    sells = sum(1 for p, v in last_signals.items() if v.get("sig") == "SELL")
    holds = sum(1 for p, v in last_signals.items() if v.get("sig") == "HOLD")

    summary = f"""🔍 <b>HOURLY SCAN COMPLETE</b> — {now}

📊 Results for all 5 pairs:
🟢 BUY signals:  {buys}
🔴 SELL signals: {sells}
⏸ HOLD:         {holds}

{"🚨 " + str(found) + " strong alert(s) sent above!" if found > 0 else "⏳ No strong signals yet — waiting for 4+/5 setup"}

Next scan in 1 hour."""

    send_telegram(summary)

# ── Main ──────────────────────────────────────────────────────────
def main():
    log.info("=" * 50)
    log.info("FOREX SIGNAL BOT STARTING")
    log.info(f"Pairs:    {', '.join(PAIRS)}")
    log.info(f"Interval: {INTERVAL}")
    log.info(f"Min agree: {MIN_AGREE}/5")
    log.info(f"Telegram: {TELEGRAM_CHAT}")
    log.info("=" * 50)

    # Send startup message
    send_telegram(f"""🤖 <b>FOREX SIGNAL BOT STARTED</b>

✅ Bot is now running 24/7
📊 Monitoring: {", ".join(PAIRS)}
⏰ Scans every: 1 hour
🎯 Alert threshold: {MIN_AGREE}+/5 strategies agree
📈 Timeframe: {INTERVAL}

First scan starting now...""")

    # Run immediately on start
    scan_all()

    # Schedule every hour
    schedule.every(1).hours.do(scan_all)

    log.info("Scheduler running — scanning every hour")

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
