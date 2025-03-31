# AI Platform

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
![](https://github.com/ProjectTech4DevAI/ai-platform/workflows/Continuous%20Integration/badge.svg)
[![Code coverage badge](https://img.shields.io/codecov/c/github/ProjectTech4DevAI/ai-platform/staging.svg)](https://codecov.io/gh/ProjectTech4DevAI/ai-platform/branch/staging)
![GitHub issues](https://img.shields.io/github/issues-raw/ProjectTech4DevAI/ai-platform)
[![codebeat badge](https://codebeat.co/badges/dd951390-5f51-4c98-bddc-0b618bdb43fd)](https://codebeat.co/projects/github-com-ProjectTech4DevAI/ai-platform-staging)
[![Commits](https://img.shields.io/github/commit-activity/m/ProjectTech4DevAI/ai-platform)](https://img.shields.io/github/commit-activity/m/ProjectTech4DevAI/ai-platform)

## Pre-requisites

- [docker](https://docs.docker.com/get-started/get-docker/) Docker
- [uv](https://docs.astral.sh/uv/) for Python package and environment management.

## Project Setup

You can **just fork or clone** this repository and use it as is.

✨ It just works. ✨

### Configure

Create env file using example file

```bash
cp .env.example .env
```

You can then update configs in the `.env` files to customize your configurations.

Before deploying it, make sure you change at least the values for:

- `SECRET_KEY`
- `FIRST_SUPERUSER_PASSWORD`
- `POSTGRES_PASSWORD`

````bash

### Generate Secret Keys

Some environment variables in the `.env` file have a default value of `changethis`.

You have to change them with a secret key, to generate secret keys you can run the following command:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
````

Copy the content and use that as password / secret key. And run that again to generate another secure key.

## Boostrap & development mode

This is a dockerized setup, hence start the project using below command

```bash
docker compose watch
```

This should start all necessary services for the project and will also mount file system as volume for easy development.

You verify backend running by doing health-check

```bash
curl http://[your-domain]:8000/api/v1/utils/health/
```

or by visiting: http://[your-domain]:8000/api/v1/utils/health-check/ in the browser

## Backend Development

Backend docs: [backend/README.md](./backend/README.md).

## Deployment

Deployment docs: [deployment.md](./deployment.md).

## Development

General development docs: [development.md](./development.md).

This includes using Docker Compose, custom local domains, `.env` configurations, etc.

## Release Notes

Check the file [release-notes.md](./release-notes.md).

## Credits

This project was created using [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template). A big thank you to the team for creating and maintaining the template!!!
