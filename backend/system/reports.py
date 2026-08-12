from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPORT_NAME = re.compile(r"report_(\d{6})_(\d{4})\.md")
GENERATED_AT = re.compile(r"Générée le ([^ ]+)")
REPORT_TIMEZONE = ZoneInfo("Europe/Paris")


def reports_directory(summary_path: Path) -> Path:
    return summary_path.parent / "reports"


def report_path(summary_path: Path, generated_at: datetime) -> Path:
    local_time = generated_at.astimezone(REPORT_TIMEZONE)
    return reports_directory(summary_path) / local_time.strftime(
        "report_%y%m%d_%H%M.md"
    )


def latest_report_path(summary_path: Path) -> Path | None:
    directory = reports_directory(summary_path)
    reports = (
        sorted(
            (
                path
                for path in directory.glob("report_*.md")
                if REPORT_NAME.fullmatch(path.name)
            ),
            key=lambda path: path.name,
            reverse=True,
        )
        if directory.exists()
        else []
    )
    if reports:
        return reports[0]
    return summary_path if summary_path.exists() else None


def report_updated_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def report_generated_at(path: Path) -> datetime:
    try:
        generated = GENERATED_AT.search(path.read_text(encoding="utf-8")[:500])
        if generated:
            return datetime.fromisoformat(generated.group(1)).astimezone(
                REPORT_TIMEZONE
            )
    except (OSError, UnicodeError, ValueError):
        pass
    match = REPORT_NAME.fullmatch(path.name)
    if match:
        return datetime.strptime("".join(match.groups()), "%y%m%d%H%M").replace(
            tzinfo=REPORT_TIMEZONE
        )
    return datetime.fromtimestamp(path.stat().st_mtime, REPORT_TIMEZONE)


def telegram_summary_path(summary_path: Path, report: Path) -> Path:
    match = REPORT_NAME.fullmatch(report.name)
    if match:
        return report.parent / f"telegram_{match.group(1)}_{match.group(2)}.txt"
    return summary_path.with_suffix(".telegram.txt")


def latest_telegram_summary_path(summary_path: Path) -> Path | None:
    report = latest_report_path(summary_path)
    if report is None:
        return None
    telegram_path = telegram_summary_path(summary_path, report)
    return telegram_path if telegram_path.exists() else None
