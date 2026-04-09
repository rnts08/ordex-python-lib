from setuptools import setup, find_packages

setup(
    name="ordex",
    version="0.1.0",
    description="Python implementation of OrdexCoin (OXC) and OrdexGold (OXG) protocols",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "ecdsa>=0.18.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0"],
    },
)
