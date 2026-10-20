from pathlib import Path


def get_asset_path(filename: str) -> Path:
    """Resolve an asset file path from the package directory or repository root."""
    pkg_asset = Path(__file__).resolve().parent / filename
    if pkg_asset.exists():
        return pkg_asset

    repo_asset = Path(__file__).resolve().parents[3] / "assets" / filename
    if repo_asset.exists():
        return repo_asset

    return pkg_asset
