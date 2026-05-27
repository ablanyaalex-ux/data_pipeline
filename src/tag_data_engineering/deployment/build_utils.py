import shutil
import subprocess
from pathlib import Path


def clean_build_artifacts(project_path: Path | None = None) -> None:
    if project_path is None:
        project_path = Path.cwd()
    print("Cleaning build artifacts...")
    for dir_name in ["build", "dist"]:
        dir_path = project_path / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
    for egg_info in (project_path / "src").glob("*.egg-info"):
        if egg_info.is_dir():
            shutil.rmtree(egg_info)


def build_wheel(project_path: Path | None = None) -> Path:
    if project_path is None:
        project_path = Path.cwd()
    print("Building wheel...")
    subprocess.run(
        ["python", "-m", "pip", "wheel", ".", "--no-deps", "-w", "dist"],
        check=True,
        cwd=project_path,
    )
    wheel_files = list((project_path / "dist").glob("*.whl"))
    if not wheel_files:
        raise FileNotFoundError("No wheel file found after build")
    wheel_file = wheel_files[0]
    print(f"Built wheel: {wheel_file.name}")
    return wheel_file
