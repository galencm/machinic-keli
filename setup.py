from setuptools import find_packages, setup

setup(
    name="keli",
    version="0.1",
    description="",
    author="Galen Curwen-McAdams",
    author_email="",
    platforms=["any"],
    license="Mozilla Public License 2.0 (MPL 2.0)",
    include_package_data=True,
    url="",
    packages=find_packages(),
    install_requires=[
        "redis",
        "ma_cli",
        "logzero",
        "tesserocr",
        "lings",
        "gphoto2",
        "fold_ui",
        "pre-commit",
    ],
    dependency_links=[
        "https://github.com/galencm/ma-cli/tarball/master#egg=ma_cli-0.1",
        "https://github.com/galencm/machinic-lings/tarball/master#egg=lings-0.1",
        "https://github.com/galencm/fold-lattice-ui/tarball/master#egg=fold_ui-0.1",
    ],
    entry_points={"console_scripts": ["keli = keli.keli_cli:main"]},
)
