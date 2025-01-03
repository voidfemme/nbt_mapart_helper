from setuptools import setup, find_packages

setup(
    name="nbt_mapart_helper",
    version="0.2.0",  # Bumped version for LAN feature addition
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "nbtlib>=2.0.4",
        "gnureadline>=8.2.13",
        "setuptools>=75.2.0",
    ],
    entry_points={
        "console_scripts": [
            "nbt-mapart-helper=src.main:main",
        ],
    },
    python_requires='>=3.7',
)
