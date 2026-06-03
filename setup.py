from setuptools import setup, find_packages

setup(
    name="nexus-demo-api",
    version="1.0.0",
    description="Demonstration microservice for the Project Nexus AI Code Quality & Automated Remediation Pipeline",
    author="Project Nexus Team",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "flask>=3.0.0",
        "requests>=2.31.0",
    ],
    extras_require={
        "test": ["pytest>=8.0.0"],
    },
    entry_points={
        "console_scripts": [
            "nexus-api=src.app:create_app",
        ],
    },
)
