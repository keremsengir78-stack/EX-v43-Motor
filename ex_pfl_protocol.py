"""Read PFL match protocol PDFs as published, preserving nominal regulation minutes."""

import re
import subprocess

from ex_official_minutes import minutes_from_timeline
from ex_official_report_html import nominal_minute


def pdf_layout(raw):
    if not raw.startswith(b"%PDF-"):
        raise ValueError("PFL response is not a PDF")
    try:
        return subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", "-", "-"],
                              input=raw, capture_output=True, check=True, timeout=15).stdout.decode()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"Unable to extract PFL PDF layout: {exc}") from exc


def extract_minutes(text, home, away, date_label):
    if not text.strip().startswith(date_label + ". Saat "):
        raise ValueError("PFL match date does not match the registry")
    if re.search(r"qırmızı vərəq|əlavə hissə", text, re.I):
        raise ValueError("Dismissals or extra time require a reviewed representation")
    headings = ("“" + home + "”", "“" + away + "”")
    states = [None, None]
    starters, changes = [[], []], [[], []]
    seen = [set(), set()]
    for line in text.splitlines():
        if not line.strip():
            continue
        leading = len(line) - len(line.lstrip())
        left, *right = re.split(r" {3,}", line.strip(), maxsplit=1)
        cells = ("", left) if leading >= 25 and not right else (left, right[0] if right else "")
        for side, cell in enumerate(cells):
            cell = cell.strip()
            if cell == headings[side]:
                if states[side] is not None:
                    raise ValueError("Duplicate PFL lineup heading")
                states[side] = "starters"
            elif states[side] == "starters" and cell.startswith("Ehtiyat oyunçular"):
                states[side] = "bench"
            elif states[side] == "starters" and cell and cell != "Əsas heyət:":
                starter = re.fullmatch(r"(\d{1,2})\. (.+?)(?: \(k\))?", cell)
                sub = re.fullmatch(r"\((\d{1,2})\. (.+), (\d{1,2}(?:\+\d{1,2})?)\)", cell)
                if starter:
                    number, name = starter.groups()
                    starters[side].append(name)
                elif sub and starters[side]:
                    number, name, minute = sub.groups()
                    changes[side].append((nominal_minute(minute), starters[side][-1], name))
                else:
                    raise ValueError(f"Unrecognized PFL lineup row: {cell}")
                if number in seen[side]:
                    raise ValueError("Duplicate shirt number in PFL lineup")
                seen[side].add(number)
    if states != ["bench", "bench"]:
        raise ValueError("PFL document is missing both complete lineups")
    return {side: minutes_from_timeline(starters[i], sorted(changes[i], key=lambda event: event[0]))
            for i, side in enumerate(("home", "away"))}
