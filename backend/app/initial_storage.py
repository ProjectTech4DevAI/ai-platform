import logging

from app.core.cloud import AmazonCloudStorageClient, CloudStorageError
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init() -> None:
    aws = AmazonCloudStorageClient()
    try:
        aws.create()
    except CloudStorageError as err:
        logging.error(err)

def main() -> None:
    logger.info("START: setup cloud storage")
    init()
    logger.info("END: setup cloud storage")


if __name__ == "__main__":
    main()
