from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="ordex",
    version="1.1.0",
    author="Ordex Team",
    author_email="dev@ordexcoin.io",
    description="Python implementation of OrdexCoin (OXC) and OrdexGold (OXG) protocols with RPC services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ordexco/ordex-python-lib",
    project_urls={
        "Bug Tracker": "https://github.com/ordexco/ordex-python-lib/issues",
        "Source": "https://github.com/ordexco/ordex-python-lib",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: Bitcoin",
    ],
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "ecdsa>=0.18.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ordex-rpc=ordex.rpc.cli:main",
        ],
    },
    keywords=[
        "bitcoin",
        "cryptocurrency",
        "blockchain",
        "ordexcoin",
        "ordexgold",
        "rpc",
        "wallet",
        "multisig",
        "hd-wallet",
    ],
    include_package_data=True,
    zip_safe=False,
)