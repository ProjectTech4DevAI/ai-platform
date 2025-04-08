import warnings
from datetime import datetime, timezone

from fastapi import HTTPException


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
