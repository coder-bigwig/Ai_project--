#!/usr/bin/env python3
import base64
import inspect
import re
from pathlib import Path


def _build_source_svg(branding_dir: Path) -> str | None:
    source_png = branding_dir / "fit-logo.png"
    source_jpg = branding_dir / "fit-logo.jpg"
    source_svg = branding_dir / "jupyternaut.svg"

    if source_png.exists():
        encoded = base64.b64encode(source_png.read_bytes()).decode("ascii")
        source_content = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">'
            '<defs><clipPath id="brandClip"><rect width="96" height="96" rx="16" ry="16"/></clipPath></defs>'
            f'<image width="96" height="96" preserveAspectRatio="xMidYMid slice" '
            f'clip-path="url(#brandClip)" href="data:image/png;base64,{encoded}"/>'
            "</svg>"
        )
        print(f"Using PNG branding source: {source_png}")
        return source_content

    if source_jpg.exists():
        encoded = base64.b64encode(source_jpg.read_bytes()).decode("ascii")
        source_content = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">'
            '<defs><clipPath id="brandClip"><rect width="96" height="96" rx="16" ry="16"/></clipPath></defs>'
            f'<image width="96" height="96" preserveAspectRatio="xMidYMid slice" '
            f'clip-path="url(#brandClip)" href="data:image/jpeg;base64,{encoded}"/>'
            "</svg>"
        )
        print(f"Using JPG branding source: {source_jpg}")
        return source_content

    if source_svg.exists():
        print(f"Using SVG branding source: {source_svg}")
        return source_svg.read_text(encoding="utf-8")

    return None


def _patch_python_package_svgs(source_content: str) -> int:
    try:
        import jupyter_ai  # pylint: disable=import-outside-toplevel
    except Exception as err:  # noqa: BLE001
        print(f"jupyter_ai import failed, skip package SVG patch: {err}")
        return 0

    package_file = Path(inspect.getfile(jupyter_ai)).resolve()
    package_root = package_file.parent
    matches = list(package_root.rglob("jupyternaut.svg"))
    if not matches:
        print(f"No jupyternaut.svg found under {package_root}, skip")
        return 0

    replaced = 0
    for target in matches:
        try:
            target.write_text(source_content, encoding="utf-8")
            replaced += 1
        except Exception as write_err:  # noqa: BLE001
            print(f"Failed to patch {target}: {write_err}")
    return replaced


def _patch_labextension_bundles(source_content: str) -> int:
    # Jupyter AI chat avatar is embedded in labextension bundle as:
    # name:"jupyter-ai::jupyternaut",svgstr:'<svg ... </svg>'
    pattern = re.compile(
        r'(name:"jupyter-ai::jupyternaut",svgstr:\')<svg[\s\S]*?(\')'
    )

    search_roots = [
        Path("/opt/conda/share/jupyter/labextensions/@jupyter-ai/core/static"),
        Path.home() / ".local" / "share" / "jupyter" / "labextensions" / "@jupyter-ai" / "core" / "static",
    ]
    candidates: list[Path] = []
    for root in search_roots:
        if root.exists():
            candidates.extend(root.glob("*.js"))

    if not candidates:
        print("No Jupyter AI labextension bundles found, skip")
        return 0

    replaced = 0
    for target in candidates:
        try:
            text = target.read_text(encoding="utf-8")
        except Exception as read_err:  # noqa: BLE001
            print(f"Failed to read {target}: {read_err}")
            continue

        new_text, count = pattern.subn(rf"\1{source_content}\2", text)
        if count == 0:
            continue

        try:
            target.write_text(new_text, encoding="utf-8")
            replaced += count
        except Exception as write_err:  # noqa: BLE001
            print(f"Failed to patch {target}: {write_err}")

    return replaced


def main() -> int:
    try:
        branding_dir = Path(__file__).resolve().parents[1] / "assets" / "jupyter_ai"
        source_content = _build_source_svg(branding_dir)
        if source_content is None:
            print(f"Branding source not found under {branding_dir}, skip")
            return 0

        patched_svg = _patch_python_package_svgs(source_content)
        patched_bundles = _patch_labextension_bundles(source_content)
        print(f"Patched jupyternaut.svg files: {patched_svg}")
        print(f"Patched labextension bundle references: {patched_bundles}")
        return 0
    except Exception as err:  # noqa: BLE001
        print(f"patch_jupyter_ai_branding skipped due to error: {err}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
