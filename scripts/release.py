"""Gera o instalador e sobe um release em RASCUNHO no GitHub (como o npm run release do Voice).

    .venv\\Scripts\\python scripts\\release.py              # build + rascunho
    .venv\\Scripts\\python scripts\\release.py --no-build   # usa o instalador já em dist/

1. Lê a versão do pyproject.toml e confere que ela tem seção no CHANGELOG.md.
2. Roda scripts/build.py (a não ser com --no-build).
3. `gh release create v<versão> --draft` com o instalador e as notas da versão.

Nada chega a ninguém até o rascunho ser publicado no GitHub. Ao publicar, o GitHub cria a
tag v<versão> no último commit da main: faça o push antes. A versão precisa ser maior que a
do último release para a atualização automática oferecer (services/updater.py).
Precisa do gh autenticado. Ver docs/decisions/0012-atualizacao-automatica.md.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import DIST, ROOT, version  # noqa: E402

REPO = "eduoliveira1504/aureum-island"


def notes_for(text: str) -> str:
    """A seção "## <versão>" do CHANGELOG.md, com o título do arquivo."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(text)}\n(.*?)(?=^## |\Z)", changelog, re.M | re.S)
    if match is None:
        raise SystemExit(f"CHANGELOG.md não tem a seção '## {text}'")
    title = changelog.splitlines()[0]
    return f"{title}\n\n## {text}\n{match.group(1).rstrip()}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-build", action="store_true", help="usa o instalador de dist/")
    args = parser.parse_args()

    text = version()
    notes = notes_for(text)
    if not args.no_build:
        subprocess.run([sys.executable, str(ROOT / "scripts/build.py")], check=True, cwd=ROOT)
    installer = DIST / f"AureumIsland-Setup-{text}.exe"
    if not installer.is_file():
        raise SystemExit(f"falta o instalador: {installer}")

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(notes)
        notes_file = f.name
    subprocess.run(
        [
            "gh",
            "release",
            "create",
            f"v{text}",
            str(installer),
            "--repo",
            REPO,
            "--draft",
            "--target",
            "main",
            "--title",
            f"Aureum Island {text}",
            "--notes-file",
            notes_file,
        ],
        check=True,
        cwd=ROOT,
    )
    Path(notes_file).unlink(missing_ok=True)
    print(f"rascunho v{text} criado. Faça o push da main e publique pelo GitHub.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
