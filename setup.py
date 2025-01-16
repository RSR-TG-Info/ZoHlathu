import os
from setuptools import setup, find_packages


def requirements(file="requirements.txt"):
    if os.path.isfile(file):
        with open(file, encoding="utf-8") as r:
            return [i.strip() for i in r]
    else:
        return []


def readme(file="README.md"):
    if os.path.isfile(file):
        with open(file, encoding="utf-8") as r:
            return r.read()
    else:
        return ""


setup(
    name="zohlathu",
    version="0.1.1",
    packages=find_packages(),
    install_requires=requirements(),
    author="RSR",
    author_email="imrsrmizo@gmail.com",
    description="A Python package for fetching Mizo song lyrics from Zohlathu.in",
    long_description=readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/RSR-TG-Info/ZoHlathu",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
