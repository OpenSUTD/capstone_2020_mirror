import time
import boto3
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict

cf = boto3.client("cloudfront")
s3 = boto3.client("s3")
s3_resource = boto3.resource("s3")
STACK_NAME = os.environ["STACK_NAME"]
DISTRIBUTION_ID = os.environ["DISTRIBUTION_ID"]
VERSIONS_BUCKET_NAME = os.environ["VERSIONS_BUCKET_NAME"]


def lambda_handler(event, context):
    datestring = event["datestring"]
    # invalidate cache
    cf.create_invalidation(
        DistributionId=DISTRIBUTION_ID,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/*"]},
            "CallerReference": str(round(time.time())),
        },
    )
    # delete version archives
    bucket = s3_resource.Bucket(VERSIONS_BUCKET_NAME)
    for object_summary in bucket.objects.all():
        if object_summary.key != f"{datestring}.tgz":
            object_summary.delete()
