"""Shared destination and camera-date rules for imported Nokia photographs."""
from datetime import date, datetime
import json
from pathlib import Path
import re

DEFAULT_LIBRARY = Path.home() / "Pictures" / "Personal" / "Nokia-N900"
# The N900 clock was corrected during the September setup. Earlier dates are
# explicitly unreliable; a file's import time is not its capture date.
CLOCK_CORRECTED = date(2026, 9, 29)
# The single table of real dates for photos taken while the N900 clock was wrong. Filing and the daily pick both read
# it. The clock restarted at 2009-01-01 on 2026-09-11 and counted up a day at a time until it was fixed on 2026-09-29.
# Only dates Milind confirmed belong here (Nov 11: 20090101 is Sep 12, 20090114 is Sep 20, 20090118 is Sep 29, although
# counting days would say Sep 11, Sep 24 and Sep 28). To correct one, edit this table and run `organize_photos.py --refile`.
CLOCK_FIXES = {'20090101': date(2026, 9, 12), '20090110': date(2026, 9, 20),
               '20090113': date(2026, 9, 23), '20090114': date(2026, 9, 20),
               '20090118': date(2026, 9, 29), '20090119': date(2026, 9, 29)}


def validate_root(root, repository):
    root = Path(root).expanduser()
    if not root.is_absolute():
        raise ValueError("Use an absolute photo-library path outside the repository.")
    root = root.resolve()
    repository = repository.resolve()
    if root == repository or repository in root.parents:
        raise ValueError("Keep the photo library outside the code repository.")
    return root


def configured_root(private, repository):
    config = private / "photo-library.json"
    if not config.exists():
        return None
    settings = json.loads(config.read_text())
    if settings.get("layout") != "iso-week/date-v1":
        raise ValueError("Unknown photo-library layout; refusing to choose another destination.")
    return validate_root(settings["root"], repository)


def date_folders(name, today=None):
    """Use the recorded filename date, never an invented date for old photos."""
    fixed = CLOCK_FIXES.get(Path(name).name[:8])
    if fixed:
        year, week, _ = fixed.isocalendar()
        return Path("{}-W{:02d}".format(year, week)) / fixed.isoformat()
    match = re.match(r"^(\d{8})_\d+", Path(name).name)
    if match:
        try:
            day = datetime.strptime(match.group(1), "%Y%m%d").date()
            if CLOCK_CORRECTED <= day <= (today or date.today()):
                year, week, _ = day.isocalendar()
                return Path("{}-W{:02d}".format(year, week)) / day.isoformat()
        except ValueError:
            pass
    return Path("Date-unverified")


def photo_directory(root, name):
    folder = root / date_folders(name)
    if root.resolve() not in folder.resolve().parents:
        raise ValueError("A photo folder points outside the configured library.")
    folder.mkdir(parents=True, exist_ok=True)
    return folder
