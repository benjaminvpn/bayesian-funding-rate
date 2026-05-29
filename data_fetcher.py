"""从 Bybit API 获取数据"""
import json, urllib.request, urllib.error, numpy as np
BYBIT_BASE = "https://api.bybit.com"

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {}

def get_funding_rate(symbol="BTCUSDT"):
    d = fetch_json(f"{BYBIT_BASE}/v5/market/tickers?category=linear&symbol={symbol}")
    r = float(d.get("result",{}).get("list",[{}])[0].get("fundingRate",0))
    return round(r*3*365*100,4)

def get_funding_rate_history(s="BTCUSDT", n=50):
    d = fetch_json(f"{BYBIT_BASE}/v5/market/funding/history?category=linear&symbol={s}&limit={n}")
    items = d.get("result",{}).get("list",[])
    if not items: return np.array([])
    return np.array([float(i["fundingRate"])*3*365*100 for i in items])

def get_all_data(symbol="BTCUSDT"):
    print(f"  [*] {symbol} (Bybit)...")
    r = get_funding_rate(symbol)
    print(f"      费率: {r}%")
    td = fetch_json(f"{BYBIT_BASE}/v5/market/tickers?category=linear&symbol={symbol}")
    t = td.get("result",{}).get("list",[{}])[0]
    price = float(t.get("lastPrice",0))
    vol = float(t.get("volume24h",0))
    tv = float(t.get("turnover24h",0))
    print(f"      价格: ${price:,.2f}")
    od = fetch_json(f"{BYBIT_BASE}/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min&limit=50")
    oi = od.get("result",{}).get("list",[])
    oz = 0.0
    if len(oi) >= 10:
        v = np.array([float(i["openInterest"]) for i in oi])
        oz = float((v[-1]-np.mean(v[:-1]))/(np.std(v[:-1])+1e-8))
    print(f"      OI Z-score: {oz:.3f}")
    vr = round(vol/(tv/price),2) if price>0 and tv>0 else 1.0
    tr = fetch_json(f"{BYBIT_BASE}/v5/market/recent-trade?category=linear&symbol={symbol}&limit=100")
    tl = tr.get("result",{}).get("list",[])
    lr = round(sum(1 for x in tl if x.get("side","")=="Buy")/len(tl),2) if tl else 1.0
    return {"funding_rate":r/100,"price":price,"oi_change":round(oz,3),"volume_ratio":vr,"liq_long_ratio":lr}

def get_mock_data(s="BTCUSDT"):
    m = {"BTCUSDT":{"funding_rate":0.06,"price":105000,"oi_change":1.2,"volume_ratio":1.8,"liq_long_ratio":0.4},"ETHUSDT":{"funding_rate":0.04,"price":3800,"oi_change":0.8,"volume_ratio":1.3,"liq_long_ratio":0.7}}
    return m.get(s,m["BTCUSDT"])