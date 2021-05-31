import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="discordpy-replit-heroku",
    version="0.4.0",
    author="John Doe",
    author_email="johndo3@repl.email",
    description="Hosting your repl based discord.py bot on Heroku to keep it running INDEFINETLY",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/syntax-corp/discordpy-replit-heroku",
    project_urls={
        "Issue tracker": "https://github.com/syntax-corp/discordpy-replit-heroku/issues",
    },
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "discord.py",
        "flask",
        "python-dotenv",
        "PyNaCl",
        "dnspython",
    ],
    python_requires='>=3.6',
)
