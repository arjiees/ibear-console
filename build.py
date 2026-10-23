"""Rebuild the IBEAR class console from the private deadline calendar.
Runs inside GitHub Actions. Reads the calendar's secret iCal address from the
ICS_URL secret, turns each "[CODE] Assignment" event into a deadline row, and
writes _site/index.html from template.html. Exits non-zero (keeping the last
good page live) if the feed is unreachable or empty.
"""
import json, os, re, sys, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

CORE = {"GSBA 548", "GSBA 534", "GSBA 530", "GSBA 583"}

def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")

def unfold(text):
    # RFC 5545: a line starting with a space or tab continues the previous one
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()

def unescape(v):
    return v.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")

def parse(text):
    rows, ev = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            ev = {}
        elif line == "END:VEVENT" and ev is not None:
            m = re.match(r"\[([A-Z]+ \d{3})\]\s*(.+)", ev.get("SUMMARY", ""))
            d = re.match(r"(\d{4})(\d{2})(\d{2})", ev.get("DTSTART", ""))
            if m and d and m.group(1) in CORE:
                rows.append([m.group(2).strip(), m.group(1), "-".join(d.groups()),
                             None, None, None, False, False])
            ev = None
        elif ev is not None and ":" in line:
            key, val = line.split(":", 1)
            ev[key.split(";")[0]] = unescape(val)
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: (r[2], r[1], r[0])):
        k = (r[0], r[1], r[2])
        if k not in seen:
            seen.add(k); out.append(r)
    return out

def render(rows, now):
    t = open("template.html", encoding="utf-8").read()
    body = ",\n".join("    " + json.dumps(r, ensure_ascii=False) for r in rows)
    stamp = now.strftime("%b %-d, %Y at %-I:%M%p").replace("AM", "am").replace("PM", "pm") + " PT"
    return (t.replace("/*ROWS*/", body)
             .replace("/*SYNC*/", now.strftime("%Y-%m-%dT%H:%M:00"))
             .replace("/*UPDATED*/", stamp)
             .replace("/*COUNT*/", str(len(rows))))

if __name__ == "__main__":
    url = os.environ.get("ICS_URL", "").strip()
    if not url:
        sys.exit("ICS_URL secret is missing")
    rows = parse(fetch(url))
    if not rows:
        sys.exit("Calendar returned no deadlines; keeping the last published page")
    os.makedirs("_site", exist_ok=True)
    html = render(rows, datetime.now(ZoneInfo("America/Los_Angeles")))
    open("_site/index.html", "w", encoding="utf-8").write(html)
    print(f"Built {len(rows)} deadlines")
