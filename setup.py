import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="gnucash-ch-filing",
    version="0.2",
    author="Cybermaggedon",
    author_email="mark@cyberapocalypse.co.uk",
    description="UK Companies House accounts filing for GnuCash users",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cybermaggedon/gnucash-ch-filing",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    download_url = "https://github.com/cybermaggedon/gnucash-uk-corptax/archive/refs/tags/v0.2.tar.gz",
    install_requires=[
        'lxml',
        'requests'
    ],
    scripts=[
        "scripts/ch-filing",
    ]
)
