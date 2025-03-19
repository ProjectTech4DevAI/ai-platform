import logging

from botocore.exceptions import ClientError

from app.core.cloud import AmazonCloudStorageClient
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init() -> None:
    aws = AmazonCloudStorageClient()
    try:
        # does the bucket exist...
        aws.client.head_bucket(Bucket=settings.AWS_S3_BUCKET)
    except ClientError as err:
        response = int(err.response['Error']['Code'])
        if response != 404:
            raise
        # ... if not create it
        aws.client.create_bucket(Bucket=settings.AWS_S3_BUCKET)

def main() -> None:
    logger.info("START: setup cloud storage")
    init()
    logger.info("END: setup cloud storage")


if __name__ == "__main__":
    main()
