# Tech4Dev AI Platform

## Getting starting

### Prerequisite services

You'lll need Python 3.13.2(latest). You can either download the installer directly from the official [Python website](https://www.python.org/) or, if you prefer using conda, simply run the following command in your terminal to create new environment:

```bash
conda create -n ai_platform python=3.13.2
```

then activate this environment

```bash
conda activate ai_platform
```

Ensure Redis and Postgres are installed and running on your
machine. This section assumes that both are accessible on localhost
via their default ports.

If you have not done so already, setup a Postgres user that can
connect to a known database. As an example (in Bash):

```bash
sudo -u postgres psql postgres <<< "ALTER USER postgres with encrypted password 'postgres';"
```

### Platform setup

Clone the repository and enter its root:

```bash
git clone https://github.com/ProjectTech4DevAI/ai-platform.git
cd ai-platform
```

#### Repository configuration

The platform relies on several environment variables read from
`src/.env`. For security, this file is not included in the
repository. You can generate the file by copying the skeleton that is
included:

```bash
cp .env.example src/.env
```

Many of the options in this file pertain to non-trivial usage of the
platform. The bare minimum variables you need to configure relate to
Postgres:

```
# ------------- database -------------
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_SERVER=
POSTGRES_PORT=
POSTGRES_DB=
```

Based on the Postgres configuration described earlier, updated values
would be:

```
# ------------- database -------------
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=postgres
```

#### Python configuration

Your Python version should be 3.11 or higher. Package management is
done via Poetry:

```bash
pip install poetry
poetry install
```

Make sure you have pre-commit setup

```bash
poetry add pre-commit --dev
```

Check if pre-commit runs smoothly using

```bash
poetry run pre-commit run --all-files
```

The platform can then be started with Uvicorn:

```bash
poetry run uvicorn src.app.main:app --reload
```

For more advanced usage and developer documentation, see our [Wiki](https://github.com/ProjectTech4DevAI/ai-platform/wiki).
