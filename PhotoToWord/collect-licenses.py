"""Collect installed Python/runtime license texts into a release folder."""
import importlib.metadata
from pathlib import Path
import shutil
import sys

destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=True)
for distribution in importlib.metadata.distributions():
    name = distribution.metadata.get("Name", "unknown")
    for entry in distribution.files or []:
        if ".." in entry.parts:
            continue
        if not any(word in entry.name.lower() for word in ("license", "copying", "notice")):
            continue
        source = Path(distribution.locate_file(entry))
        if source.is_file() and source.suffix.lower() in ("", ".txt", ".md", ".rst"):
            target = destination / name / Path(entry)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
for source in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE",
               Path(sys.base_prefix) / "tcl/tcl8.6/license.terms",
               Path(sys.base_prefix) / "tcl/tk8.6/license.terms"):
    if source.is_file():
        shutil.copy2(source, destination / (source.parent.name + "-" + source.name))
