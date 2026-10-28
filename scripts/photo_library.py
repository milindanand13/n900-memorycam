"""Shared destination and camera-date rules for imported Nokia photographs."""
from datetime import date, datetime
import json
from pathlib import Path
import re

DEFAULT_LIBRARY = Path.home() / "Pictures" / "Personal" / "Nokia-N900"
# The N900 clock was corrected during the September setup. Earlier dates are
# explicitly unreliable; a file's import time is not its capture date.
CLOCK_CORRECTED = date(2026, 9, 29)


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
