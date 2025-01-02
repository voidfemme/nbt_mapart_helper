from setuptools import setup, find_packages

setup(
    name="nbt_mapart_helper",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "nbtlib>=1.12.1",
        "readline>=6.2.4.1",
    ],
    entry_points={
        "console_scripts": [
            "nbt-mapart-helper=src.main:main",
        ],
    },
)
