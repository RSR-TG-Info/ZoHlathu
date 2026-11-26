from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="zohlathu",
    version="2.2.0",
    author="RSR",
    author_email="imrsrmizo@gmail.com",
    description="A zero-dependency Python package for fetching Mizo song lyrics from Zo Hla thu",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/RSR-TG-Info/ZoHlathu",
    project_urls={
        "Website": "https://www.zohlathu.in",
        "Source": "https://github.com/RSR-TG-Info/ZoHlathu",
        "Bug Tracker": "https://github.com/RSR-TG-Info/ZoHlathu/issues",
    },
    packages=find_packages(),
    install_requires=[],
    keywords=["mizo", "lyrics", "zohlathu", "mizo-songs", "music"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
