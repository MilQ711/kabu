"""東証の株価を Yahoo Finance (yfinance) から取得して data/prices.json に保存する。

GitHub Actions から定期実行される。手元で試すときは:
    pip install yfinance
    python scripts/fetch_prices.py
"""
import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf

JST = timezone(timedelta(hours=9))

STOCKS = [
    ("7203", "トヨタ自動車"), ("6758", "ソニーグループ"), ("7974", "任天堂"),
    ("8306", "三菱UFJ"), ("6861", "キーエンス"), ("9983", "ファーストリテイリング"),
    ("9984", "ソフトバンクグループ"), ("8035", "東京エレクトロン"), ("6501", "日立製作所"),
    ("9433", "KDDI"), ("9432", "NTT"), ("6098", "リクルート"),
    ("4063", "信越化学"), ("8031", "三井物産"), ("8001", "伊藤忠商事"),
    ("4661", "オリエンタルランド"), ("8136", "サンリオ"), ("7832", "バンダイナムコ"),
    ("9697", "カプコン"), ("9766", "コナミグループ"), ("9202", "ANA"),
    ("4385", "メルカリ"), ("4755", "楽天グループ"), ("8473", "SBIホールディングス"),
    ("9684", "スクウェア・エニックス"),
]

OUT = Path(__file__).resolve().parent.parent / "data" / "prices.json"


def ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def closes(df, ticker):
    """group_by="ticker" で取った表から、ある銘柄の (時刻, 終値) の一覧を返す。"""
    try:
        col = df[ticker]["Close"]
    except KeyError:
        return []
    return [(ts, float(v)) for ts, v in col.items() if ok(v)]


def main():
    tickers = [code + ".T" for code, _ in STOCKS]
    daily = yf.download(tickers, period="6mo", interval="1d", group_by="ticker",
                        auto_adjust=False, progress=False, threads=True)
    intra = yf.download(tickers, period="1d", interval="5m", group_by="ticker",
                        auto_adjust=False, progress=False, threads=True)

    out_stocks = []
    latest_ts = None
    for (code, name), t in zip(STOCKS, tickers):
        d = closes(daily, t)
        i = closes(intra, t)
        if not d:
            print(f"skip {code} {name}: 日足が取れませんでした", file=sys.stderr)
            continue

        day_pts = []
        today = None
        for ts, c in i:
            ts = ts.tz_convert(JST) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(JST)
            day_pts.append({"t": ts.strftime("%H:%M"), "c": round(c, 2)})
            today = ts.date()
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts
        price = i[-1][1] if i else d[-1][1]

        # 前日終値: 5分足の日付より前の日足のうち最後のもの
        prior = [c for ts, c in d if today is None or ts.date() < today]
        prev = prior[-1] if prior else (d[-2][1] if len(d) > 1 else d[-1][1])

        out_stocks.append({
            "code": code,
            "name": name,
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "daily": [{"d": ts.strftime("%Y-%m-%d"), "c": round(c, 2)} for ts, c in d[-60:]],
            "intraday": day_pts,
        })

    if len(out_stocks) < len(STOCKS) // 2:
        print(f"取得できた銘柄が少なすぎます ({len(out_stocks)}件)。前回のデータを残すため失敗扱いにします。", file=sys.stderr)
        sys.exit(1)

    data = {
        "source": "Yahoo Finance (yfinance)",
        "updated": datetime.now(JST).isoformat(timespec="minutes"),
        "market_time": latest_ts.isoformat(timespec="minutes") if latest_ts is not None else None,
        "stocks": out_stocks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out_stocks)}銘柄を保存しました -> {OUT}")


if __name__ == "__main__":
    main()
