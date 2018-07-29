from setuptools import find_packages, setup
setup(
name="keli",
    version="0.1",
    description="",
    author="Galen Curwen-McAdams",
    author_email='',
    platforms=["any"],
    license="Mozilla Public License 2.0 (MPL 2.0)",
    include_package_data=True,
    data_files = [("", ["LICENSE.txt"])],
    url="",
    packages=find_packages(),
    install_requires=['redis', 'ma_cli', 'logzero', 'tesserocr'],
    dependency_links=["https://github.com/galencm/ma-cli/tarball/master#egg=ma_cli-0.1"],
    entry_points = {'console_scripts': ['keli = keli.keli_cli:main'
                                       ],
                            },
)
