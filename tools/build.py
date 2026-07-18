from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT_DIR / "release"
BUILD_ROOT = ROOT_DIR / "build" / "pyinstaller"
ZIP_NAME = "release-win.zip"

TARGETS = (
    ("filter_ai_courses.py", "filter_ai_courses"),
    ("rate_courses.py", "rate_courses"),
    ("build_dashboard.py", "build_dashboard"),
)

PACKAGE_FILES = (
    "keyterms.txt",
    "prompt.txt",
    "dashboard_template.html",
)


def ensure_pyinstaller_available() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller is not installed. Install it with: pip install -e .[build]"
        ) from exc


def run_pyinstaller(script_path: Path, exe_name: str, release_dir: Path) -> None:
    work_dir = BUILD_ROOT / exe_name / "work"
    spec_dir = BUILD_ROOT / exe_name / "spec"
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)
    release_dir.mkdir(parents=True, exist_ok=True)

    release_exe = release_dir / f"{exe_name}.exe"
    if release_exe.exists():
        release_exe.unlink()

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--clean",
        "--noconfirm",
        "--name",
        exe_name,
        "--distpath",
        str(release_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        str(script_path),
    ]
    subprocess.run(command, check=True)

    if not release_exe.exists():
        raise SystemExit(f"Build finished but {release_exe} was not created.")


def build_release_zip(release_dir: Path) -> Path:
    zip_path = release_dir / ZIP_NAME
    if zip_path.exists():
        zip_path.unlink()

    package_paths = [release_dir / f"{exe_name}.exe" for _, exe_name in TARGETS]
    package_paths.extend(ROOT_DIR / file_name for file_name in PACKAGE_FILES)

    missing_files = [path for path in package_paths if not path.exists()]
    if missing_files:
        missing_list = "\n".join(str(path) for path in missing_files)
        raise SystemExit(f"Missing files for release zip:\n{missing_list}")

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in package_paths:
            archive.write(path, arcname=path.name)

    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build all Windows exe files.")
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=RELEASE_DIR,
        help="Directory where the exe files will be placed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_pyinstaller_available()

    for script_name, exe_name in TARGETS:
        script_path = ROOT_DIR / script_name
        if not script_path.exists():
            raise SystemExit(f"Missing source file: {script_path}")
        run_pyinstaller(script_path, exe_name, args.release_dir)

    build_release_zip(args.release_dir)


if __name__ == "__main__":
    main()