from setuptools import setup, find_packages

setup(
    name="facelock",
    version="1.0.0",
    description="macOS-styled native facial recognition security system for laptops",
    packages=find_packages(),
    py_modules=["main"],
    entry_points={
        "gui_scripts": [
            "facelock=main:main",
        ],
        "console_scripts": [
            "facelock-cli=main:main",
        ],
    },
)
