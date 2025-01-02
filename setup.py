from setuptools import setup, find_packages

setup(
    name="nbt_mapart_helper",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "nbtlib>=1.12.1",
        "gnureadline>=6.3.8",
    ],
    entry_points={
        "console_scripts": [
            "nbt-mapart-helper=src.main:main",
        ],
    },
)
