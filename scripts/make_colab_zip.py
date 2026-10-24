"""Zip the code the Colab notebooks need -> dist/p2-netops-code.zip. Upload it to Google Drive: MyDrive/p2-netops/."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "p2-netops-code.zip"


def code_files() -> list[Path]:
    files = [*ROOT.joinpath("src").rglob("*"), *ROOT.joinpath("configs").glob("*.yaml"),
             ROOT / "requirements-colab.txt", ROOT / "pyproject.toml"]
    return [p for p in files if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p in code_files():
            z.write(p, p.relative_to(ROOT).as_posix())
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")
