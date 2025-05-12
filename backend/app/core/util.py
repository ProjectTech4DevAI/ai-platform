import logging
import warnings
from datetime import datetime, timezone

from fastapi import HTTPException
from requests import Session, RequestException
from pydantic import BaseModel, HttpUrl


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def raise_from_unknown(error: Exception, status_code=500):
    warnings.warn(
        'Unexpected exception "{}": {}'.format(
            type(error).__name__,
            error,
        )
    )
    raise HTTPException(status_code=status_code, detail=str(error))


def post_callback(url: HttpUrl, payload: BaseModel):
    errno = 0
    with Session() as session:
        response = session.post(str(url), json=payload.model_dump())
        try:
            response.raise_for_status()
        except RequestException as err:
            warnings.warn(f"Callback failure: {err}")
            errno += 1

    return not errno
