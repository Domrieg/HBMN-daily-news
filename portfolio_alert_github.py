#!/usr/bin/env python3
"""
Daily Portfolio Alert — GitHub Actions Version
Credentials werden als Umgebungsvariablen übergeben (GitHub Secrets).
"""

import smtplib, ssl, requests, time, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

# ─── Konfiguration (via GitHub Secrets) ───────────────────────────────────────
EMAIL_FROM     = os.environ["EMAIL_FROM"]      # domrieger@hotmail.com
EMAIL_TO       = os.environ["EMAIL_TO"]        # domrieger@hotmail.com
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]  # App-Passwort
SMTP_HOST      = "smtp-mail.outlook.com"
SMTP_PORT      = 465

# ─── Portfolio ────────────────────────────────────────────────────────────────
PORTFOLIO = [
    # China
    ("CATHAY BIOTECH (CH)",         "688065.SS"),
    # US
    ("ARRIVENT BIOPHARMA",          "AVBP"),
    ("HARMONY BIOSCIENCES",         "HRMY"),
    ("ZYMEWORKS",                   "ZYME"),
    ("NATERA",                      "NTRA"),
    ("ARGENX SE ADR",               "ARGX"),
    ("AXSOME THERAPEUTICS",         "AXSM"),
    ("ALUMIS",                      "ALMS"),
    ("TRAVERE THERAPEUTICS",        "TVTX"),
    ("JAZZ PHARMACEUTICALS",        "JAZZ"),
    ("MONTE ROSA THERAPEUTICS",     "GLUE"),
    ("PARABILIS MEDICINE",          "PBLS"),
    ("ABIVAX ADR",                  "ABVX"),
    ("MINERALYS THERAPEUTICS",      "MLYS"),
    ("LEGEND BIOTECH ADR",          "LEGN"),
    ("BIOHAVEN",                    "BHVN"),
    ("ENLIVEN THERAPEUTICS",        "ELVN"),
    ("KURA ONCOLOGY",               "KURA"),
    ("TREVI THERAPEUTICS",          "TRVI"),
    ("IMMUNEERING",                 "IMRX"),
    ("BENITEC BIOPHARMA",           "BNTC"),
    ("EYEPOINT PHARMA",             "EYPT"),
    ("PERSPECTIVE THERAPEUTICS",    "CATX"),
    ("ALX ONCOLOGY",                "ALXO"),
    ("SYNDAX PHARMACEUTICALS",      "SNDX"),
    ("OCULIS HOLDING",              "OCS"),
    ("ODYSSEY THERAPEUTICS",        "ODTX"),
    ("DIANTHUS THERAPEUTICS",       "DNTH"),
    ("NUVATION BIO",                "NUVB"),
    ("ORUKA THERAPEUTICS",          "ORKA"),
    ("APOGEE THERAPEUTICS",         "APGE"),
    ("INHIBRX BIOSCIENCES",         "INBX"),
    ("ATAI LIFE SCIENCES",          "ATAI"),
    ("DENALI THERAPEUTICS",         "DNLI"),
    ("COHERUS ONCOLOGY",            "CHRS"),
    ("MIRUM PHARMACEUTICALS",       "MIRM"),
    ("UPSTREAM BIO",                "UPB"),
    ("AVALO THERAPEUTICS",          "AVTX"),
    ("ROCKET PHARMACEUTICALS",      "RCKT"),
    ("CHEMOMAB THERAPEUTICS",       "CMMB"),
    ("DEFINIUM THERAPEUTICS",       "DFTX"),
    ("IO BIOTECH",                  "IOPBTQ"),
    ("CARTESIAN THERAPEUTICS",      "RNAC"),
    # Belgien
    ("ARGEN-X NV (Brussels)",       "ARGX.BR"),
    # Schweden
    ("VICORE PHARMA (SE)",          "VICO.ST"),
    ("BIOINVENT INTL (SE)",         "BINV.ST"),
    ("FLERIE AB (SE)",              "FLERIE.ST"),
    # Schweiz
    ("HBM HEALTHCARE (CH)",         "HBMN.SW"),
    ("POLYPEPTIDE GROUP (CH)",      "PPGN.SW"),
    ("MOLECULAR PARTNERS (CH)",     "MOLN.SW"),
    # Hongkong
    ("CSTONE PHARMA (HK)",          "2616.HK"),
    ("FANGZHOU (HK)",               "6086.HK"),
    ("VISEN PHARMA (HK)",           "2561.HK"),
    # Frankreich
    ("NICOX SA (FR)",               "ALCOX.PA"),
    # Niederlande
    ("GALAPAGOS / LAKEFRONT (NL)",  "GLPG.AS"),
    # Indien
    ("LAURUS LABS (IN)",            "LAURUSLABS.NS"),
    ("AUROBINDO PHARMA (IN)",       "AUROPHARMA.NS"),
    ("SAKAR HEALTHCARE (IN)",       "SAKAR.NS"),
    ("ONESOURCE SPECIALTY (IN)",    "ONESOURCE.NS"),
    ("SOLARA ACTIVE PHARMA (IN)",   "SOLARA.NS"),
    ("DISHMAN CARBOGEN (IN)",       "DCAL.NS"),
    ("RUBICON RESEARCH (IN)",       "RUBICON.NS"),
    ("JUBILANT PHARMOVA (IN)",      "JUBLPHARMA.NS"),
]

# ─── Yahoo Finance ────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://fc.yahoo.com", timeout=10)
    except Exception:
        pass
    return s

def yf_chart(session, ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    for attempt in range(3):
        try:
            r = session.get(url, params={"interval": "1d", "range": "13mo"}, timeout=15)
            if r.status_code == 429:
                time.sleep(3 + attempt * 2)
                continue
            if r.status_code != 200:
                return None
            results = r.json().get("chart", {}).get("result")
            return results[0] if results else None
        except Exception:
            time.sleep(1)
    return None

def yf_news(session, ticker):
    try:
        r = session.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": ticker, "newsCount": 5, "quotesCount": 0},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("news", [])
    except Exception:
        pass
    return []

def calc_perf(closes, timestamps):
    if not closes or len(closes) < 2:
        return None, None, None, None
    now   = datetime.now(tz=timezone.utc)
    ytd0  = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    m12   = now - timedelta(days=365)
    pairs = [(t, c) for t, c in zip(timestamps, closes) if t and c]
    if not pairs:
        return None, None, None, None
    last  = pairs[-1][1]
    daily = ((pairs[-1][1] - pairs[-2][1]) / pairs[-2][1]) * 100 if len(pairs) >= 2 else None
    ytd_p = [(t, c) for t, c in pairs if datetime.fromtimestamp(t, tz=timezone.utc) >= ytd0]
    ytd   = ((last - ytd_p[0][1]) / ytd_p[0][1]) * 100 if ytd_p else None
    m12_p = [(t, c) for t, c in pairs if datetime.fromtimestamp(t, tz=timezone.utc) <= m12]
    m12v  = ((last - m12_p[-1][1]) / m12_p[-1][1]) * 100 if m12_p else None
    return daily, ytd, m12v, last

def perf_cell(val):
    if val is None:
        return '<td style="color:#aaa;text-align:right;padding:5px 8px">N/A</td>'
    color = "#1a7a3a" if val > 0 else "#c0392b" if val < 0 else "#888"
    arrow = "▲" if val > 0 else "▼" if val < 0 else "─"
    bg    = "#e8f5e9" if val > 0 else "#fdecea" if val < 0 else "#f5f5f5"
    return (f'<td style="text-align:right;color:{color};background:{bg};'
            f'font-weight:600;padding:5px 8px">{arrow} {val:+.2f}%</td>')

def build_html(rows, movers_up, movers_dn, news_items, today):
    th = "background:#1a3a5c;color:#fff;padding:7px 8px;font-size:11px;text-align:left"
    table_rows = ""
    for name, sym, price_str, daily, ytd, m12 in rows:
        table_rows += (
            f"<tr><td style='padding:5px 8px'>{name}</td>"
            f"<td style='padding:5px 8px;color:#555'>{sym}</td>"
            f"<td style='padding:5px 8px;text-align:right'>{price_str}</td>"
            f"{perf_cell(daily)}{perf_cell(ytd)}{perf_cell(m12)}</tr>\n"
        )

    def mover_rows(lst, color, arrow, bg):
        out = ""
        for nm, sm, dv in lst:
            out += (f"<tr><td style='padding:4px 8px'>{nm}</td>"
                    f"<td style='padding:4px 8px;color:#555'>{sm}</td>"
                    f"<td style='padding:4px 8px;text-align:right;color:{color};"
                    f"background:{bg};font-weight:700'>{arrow} {dv:+.2f}%</td></tr>")
        return out

    gain_rows = mover_rows(movers_up, "#1a7a3a", "▲", "#e8f5e9")
    loss_rows = mover_rows(movers_dn, "#c0392b", "▼", "#fdecea")

    news_html = ""
    for n in news_items:
        news_html += (
            f'<div style="border-left:3px solid #1a3a5c;padding:6px 10px;'
            f'margin-bottom:8px;background:#f9fbff">'
            f'<span style="font-weight:700;color:#1a3a5c;font-size:12px">'
            f'{n["company"]} [{n["sym"]}]</span>'
            f'<p style="margin:3px 0;font-size:12px">{n["title"]}</p>'
            f'<span style="font-size:11px;color:#888">{n["date"]} &nbsp;·&nbsp; {n["source"]}</span>'
            f'</div>'
        )
    if not news_html:
        news_html = "<p style='color:#888;font-size:12px'>Keine aktuellen Nachrichten (letzte 7 Tage).</p>"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;font-size:13px;color:#222;background:#f0f4f8;margin:0;padding:0">
<div style="max-width:920px;margin:20px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)">
  <div style="background:#1a3a5c;color:#fff;padding:18px 24px">
    <h1 style="margin:0;font-size:20px">&#128200; Daily Portfolio Alert</h1>
    <div style="font-size:12px;opacity:.75;margin-top:4px">{today} &nbsp;·&nbsp; Biotech / Pharma Portfolio</div>
  </div>
  <div style="padding:18px 24px">
    <h2 style="font-size:14px;color:#1a3a5c;border-bottom:2px solid #e0e8f0;padding-bottom:6px;margin-top:0">Performance-Übersicht</h2>
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <tr><th style="{th}">Unternehmen</th><th style="{th}">Ticker</th>
          <th style="{th};text-align:right">Kurs</th>
          <th style="{th};text-align:right">Täglich</th>
          <th style="{th};text-align:right">YTD</th>
          <th style="{th};text-align:right">12 Monate</th></tr>
      {table_rows}
    </table>
  </div>
  <div style="padding:18px 24px;background:#f9fbff">
    <h2 style="font-size:14px;color:#1a3a5c;border-bottom:2px solid #e0e8f0;padding-bottom:6px;margin-top:0">&#128680; Top Movers heute</h2>
    <table style="width:48%;border-collapse:collapse;font-size:12px;display:inline-table;vertical-align:top">
      <tr><th colspan="3" style="background:#e8f5e9;color:#1a7a3a;padding:6px 8px">Top 5 Gewinner</th></tr>
      {gain_rows}
    </table>
    &nbsp;&nbsp;
    <table style="width:48%;border-collapse:collapse;font-size:12px;display:inline-table;vertical-align:top">
      <tr><th colspan="3" style="background:#fdecea;color:#c0392b;padding:6px 8px">Top 5 Verlierer</th></tr>
      {loss_rows}
    </table>
  </div>
  <div style="padding:18px 24px">
    <h2 style="font-size:14px;color:#1a3a5c;border-bottom:2px solid #e0e8f0;padding-bottom:6px;margin-top:0">&#128240; Aktuelle Nachrichten (letzte 7 Tage)</h2>
    {news_html}
  </div>
  <div style="background:#f0f4fa;text-align:center;font-size:11px;color:#888;padding:10px">
    Daily Portfolio Alert &nbsp;·&nbsp; {today} &nbsp;·&nbsp; Daten via Yahoo Finance
  </div>
</div></body></html>"""

def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html_body, "html"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=30) as s:
        s.login(EMAIL_FROM, EMAIL_PASSWORD)
        s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print(f"Mail gesendet an {EMAIL_TO}")

def main():
    today   = datetime.now().strftime("%Y-%m-%d")
    session = make_session()
    rows, all_news, dailies = [], [], []

    for i, (company, sym) in enumerate(PORTFOLIO):
        if i > 0 and i % 10 == 0:
            time.sleep(0.5)
        chart = yf_chart(session, sym)
        daily = ytd = m12 = price = None
        ccy = ""
        if chart:
            meta   = chart.get("meta", {})
            ccy    = meta.get("currency", "")
            ts     = chart.get("timestamp", [])
            q      = chart.get("indicators", {}).get("quote", [{}])[0]
            raw    = q.get("close", [])
            closes, last_c = [], None
            for c in raw:
                if c is not None:
                    last_c = c
                closes.append(last_c)
            daily, ytd, m12, price = calc_perf(closes, ts)
            if i % 5 == 0 or i < 5:
                news   = yf_news(session, sym)
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
                for n in news[:3]:
                    pub = datetime.fromtimestamp(n.get("providerPublishTime", 0), tz=timezone.utc)
                    if pub >= cutoff:
                        all_news.append({
                            "company": company, "sym": sym,
                            "title":   n.get("title", ""),
                            "date":    pub.strftime("%Y-%m-%d"),
                            "source":  n.get("publisher", ""),
                        })
        price_str = f"{ccy} {price:.2f}" if price else "—"
        rows.append((company, sym, price_str, daily, ytd, m12))
        if daily is not None:
            dailies.append((company, sym, daily))

    dailies.sort(key=lambda x: x[2], reverse=True)
    movers_up = dailies[:5]
    movers_dn = list(reversed(dailies[-5:]))
    seen, unique_news = set(), []
    for n in all_news:
        k = n["title"][:60]
        if k not in seen:
            seen.add(k)
            unique_news.append(n)

    html = build_html(rows, movers_up, movers_dn, unique_news, today)
    send_email(f"📊 Daily Portfolio Alert — {today}", html)

if __name__ == "__main__":
    main()
