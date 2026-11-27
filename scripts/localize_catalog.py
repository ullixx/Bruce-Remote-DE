#!/usr/bin/env python3
"""Generate the German String Catalog localization before the Xcode build.

Uses Google's public translate endpoint without credentials. Format placeholders
are protected and checked before writing; technical identifiers are preserved.
"""
import concurrent.futures
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

CATALOG = Path("BruceRemote/Localizable.xcstrings")
PLACEHOLDER = re.compile(r"%(?:[0-9]+\$)?(?:@|lld|ld|d|f|s|\.\*f|%)")
TOKEN = "ZXQBRUCEPH"
TECHNICAL = re.compile(r"^[A-Z0-9 _./&()+:-]+$")

def translate_one(item):
    key, value = item
    if not value or not value.strip() or TECHNICAL.fullmatch(value.strip()):
        return key, value
    placeholders = []
    def protect(match):
        token = f"{TOKEN}{len(placeholders)}ZXQ"
        placeholders.append(match.group(0))
        return token
    protected = PLACEHOLDER.sub(protect, value)
    params = urllib.parse.urlencode({
        "client": "gtx", "sl": "auto", "tl": "de", "dt": "t", "q": protected
    })
    url = "https://translate.googleapis.com/translate_a/single?" + params
    last_error = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
            translated = "".join(part[0] for part in payload[0] if part and part[0])
            for index, original in enumerate(placeholders):
                translated = translated.replace(f"{TOKEN}{index}ZXQ", original)
            if sorted(PLACEHOLDER.findall(value)) != sorted(PLACEHOLDER.findall(translated)):
                raise ValueError("format placeholders changed")
            return key, translated
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Translation failed for {key!r}: {last_error}")

def main():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    strings = data.get("strings", {})
    work = []
    for key, entry in strings.items():
        if not key:
            continue
        source = key
        if key in ("—",):
            source = key
        work.append((key, source))
    translated = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(translate_one, item) for item in work]
        for future in concurrent.futures.as_completed(futures):
            key, value = future.result()
            translated[key] = value
    for key, value in translated.items():
        entry = strings[key]
        entry.setdefault("localizations", {})["de"] = {
            "stringUnit": {"state": "translated", "value": value}
        }
    CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = [key for key, entry in strings.items()
               if key and not entry.get("localizations", {}).get("de", {}).get("stringUnit", {}).get("value") and key.strip()]
    if missing:
        print("Missing German translations:", missing, file=sys.stderr)
        sys.exit(1)
    print(f"Generated and validated {len(translated)} German strings.")

if __name__ == "__main__":
    main()
