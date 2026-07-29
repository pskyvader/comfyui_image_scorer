import os
from setuptools import find_packages, setup

PKG = "comfyui_image_scorer"

EXCLUDES = [
    "comfyui_image_scorer_old",
    "comfyui_image_scorer_old.*",
    "build",
    "build.*",
    "dist",
    "dist.*",
    "*.egg-info",
    "config",
    "output",
]

all_pkgs = find_packages(exclude=EXCLUDES)

package_dir = {PKG: "."}
for p in all_pkgs:
    package_dir[f"{PKG}.{p}"] = p.replace(".", os.sep)

setup(
    name=PKG.replace("_", "-"),
    package_dir=package_dir,
    packages=[PKG] + [f"{PKG}.{p}" for p in all_pkgs],
)
