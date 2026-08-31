"""Build hooks for integrating frontend build into Python package build process."""

import subprocess
import sys

from setuptools.build_meta import build_editable as _build_editable
from setuptools.build_meta import build_sdist as _build_sdist
from setuptools.build_meta import build_wheel as _build_wheel


def _build_frontend() -> None:
    """Build frontend using npm. Fails if npm is missing or build fails."""
    result = subprocess.run(
        ["npm", "install", "--prefix", "web/"],
        check=False,
    )
    if result.returncode != 0:
        sys.exit(1)

    result = subprocess.run(
        ["npm", "run", "build", "--prefix", "web/"],
        check=False,
    )
    if result.returncode != 0:
        sys.exit(1)


def build_wheel(
    wheel_directory: str,
    config_settings: dict | None = None,
    metadata_directory: str | None = None,
) -> str:
    """Build wheel. Builds frontend first."""
    _build_frontend()
    return _build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(
    sdist_directory: str,
    config_settings: dict | None = None,
) -> str:
    """Build source distribution. Builds frontend first."""
    _build_frontend()
    return _build_sdist(sdist_directory, config_settings)


def build_editable(
    wheel_directory: str,
    config_settings: dict | None = None,
    metadata_directory: str | None = None,
) -> str:
    """Build editable wheel. Builds frontend first."""
    _build_frontend()
    return _build_editable(wheel_directory, config_settings, metadata_directory)
