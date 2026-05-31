from setuptools import setup, find_packages

setup(
    name="token-viz",
    version="1.0.0",
    description="Token cost visualizer for GitHub Copilot CLI and Cursor agent sessions",
    author="codes1gn",
    url="https://github.com/codes1gn/token-viz",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "tv=token_viz.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
        "Topic :: Utilities",
    ],
)
