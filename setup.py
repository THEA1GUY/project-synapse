from setuptools import setup, find_packages

setup(
    name="synapse-forge",
    version="1.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "numpy",
        "torch",
        "fastapi",
        "uvicorn",
        "pydantic",
    ],
    entry_points={
        "console_scripts": [
            "synapse-forge=synapse.cli.cli:main",
        ],
    },
    author="SenatraxAI",
    description="Neural Steganography for Decentralized RAG",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/SenatraxAI/project-synapse",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
