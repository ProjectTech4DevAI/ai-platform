# Tech4Dev AI Platform

## Getting started

### Prerequisite services

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

Your Python version should be 3.13.2 or higher. Package management is
done via Poetry:

```bash
pip install poetry
poetry install
```

The platform can then be started with Uvicorn:

```bash
poetry run uvicorn src.app.main:app --reload
```

## Contributing

When contributing to this codebase, make sure pre-commit is
setup and running smoothly:

```bash
poetry add pre-commit --dev
poetry run pre-commit run --all-files
```

## Further reading

For more advanced usage and developer documentation, see our
[Wiki](https://github.com/ProjectTech4DevAI/ai-platform/wiki).
