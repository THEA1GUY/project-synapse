from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="synapse-rag",
    version="0.1.0",
    author="Synapse",
    description="Neural Steganography Framework — hide knowledge inside LoRA models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "synapse": ["server/dashboard.html"],
    },
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn[standard]>=0.22.0",
        "numpy>=1.24.0",
        "requests>=2.28.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "torch": ["torch>=2.0.0"],
        "openai": ["openai>=1.0.0"],
        "anthropic": ["anthropic>=0.20.0"],
        "embeddings": ["sentence-transformers>=2.2.0"],
        "all": [
            "torch>=2.0.0",
            "openai>=1.0.0",
            "anthropic>=0.20.0",
            "sentence-transformers>=2.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "syn=synapse.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Security :: Cryptography",
    ],
)
