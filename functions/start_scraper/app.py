import boto3
import os
import time
import json
import logging
from botocore.exceptions import ClientError, WaiterError

logger = logging.getLogger()
logger.setLevel(os.environ["LOG_LEVEL"])
ec2_client = boto3.client("ec2")
ec2 = boto3.resource("ec2")
ssm = boto3.client("ssm")
waiter = ssm.get_waiter("command_executed")
logs = boto3.client("logs")
VOLUME_ID = os.environ["VOLUME_ID"]
PLAYBOOKS_BUCKET_NAME = os.environ["PLAYBOOKS_BUCKET_NAME"]
RUN_ANSIBLE_COMMAND_LOG_GROUP_NAME = os.environ["RUN_ANSIBLE_COMMAND_LOG_GROUP_NAME"]
RUN_HTTRACK_COMMAND_LOG_GROUP_NAME = os.environ["RUN_HTTRACK_COMMAND_LOG_GROUP_NAME"]
HTTRACK_LOG_GROUP_NAME = os.environ["HTTRACK_LOG_GROUP_NAME"]
MIRROR_TARGET = os.environ["MIRROR_TARGET"]
STACK_NAME = os.environ["STACK_NAME"]


class VolumeAlreadyAttached(Exception):
    pass


class CommandRunError(Exception):
    pass


def lambda_handler(event, context):
    volume = ec2.Volume(VOLUME_ID)
    response = volume.describe_status()
    skip_scraping = event.get("skip_scraping", False)
    if len(response["VolumeStatuses"][0].get("AttachmentStatuses", [])) != 0:
        logger.fatal(
            "Volume is already attached to another instance!",
            extra={"volume_id": VOLUME_ID},
        )
        raise VolumeAlreadyAttached()
    instances = ec2.create_instances(
        ImageId="ami-0cd31be676780afa7",
        InstanceType="t3a.medium",
        BlockDeviceMappings=[
            {
                "DeviceName": "/dev/xvda",
                "Ebs": {
                    "DeleteOnTermination": True,
                    "SnapshotId": "snap-07f777fcc29b1061b",
                    "VolumeSize": 20,
                    "VolumeType": "gp2",
                    "Encrypted": False,
                },
            }
        ],
        MinCount=1,
        MaxCount=1,
        Placement={"AvailabilityZone": volume.availability_zone,},
        IamInstanceProfile={"Arn": os.environ["INSTANCE_PROFILE_ARN"],},
        KeyName=os.environ["KEYPAIR_NAME"],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": "crawler"},
                    {"Key": "stack_name", "Value": STACK_NAME},
                ],
            }
        ],
        # for security groups without VPC, ID is actually the name
        SecurityGroups=[os.environ["INSTANCE_SECURITY_GROUP_ID"]],
    )
    instances[0].wait_until_running()
    try:
        volume.attach_to_instance(Device="/dev/sdg", InstanceId=instances[0].id)
    except ClientError as ex:
        if ex.response["Error"]["Code"] == "VolumeInUse":
            logger.fatal(
                "Volume is already in use! terminating instance",
                extra={"volume_id": VOLUME_ID},
            )
            ec2_client.terminate_instances(InstanceIds=[instances[0].instance_id])
            raise VolumeAlreadyAttached
        else:
            raise ex

    instance_id = instances[0].instance_id
    while True:
        response = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        if len(response["InstanceInformationList"]) == 0:
            logger.info("Instance SSM agent is not yet awake; sleeping for 10s...")
            time.sleep(10)
        else:
            break
    # run ansible commands

    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-ApplyAnsiblePlaybooks",
        TimeoutSeconds=9001,
        Parameters={
            "SourceType": ["S3"],
            "SourceInfo": [
                json.dumps(
                    {
                        "path": f"https://s3.amazonaws.com/{PLAYBOOKS_BUCKET_NAME}/provision"
                    }
                )
            ],
            "InstallDependencies": ["True"],
            "PlaybookFile": ["playbook.yml"],
            "Check": ["False"],
            "Verbose": ["-v"],
            "ExtraVariables": [
                f"httrack_log_group_name={HTTRACK_LOG_GROUP_NAME} httrack_target={MIRROR_TARGET} skip_scraping={str(skip_scraping).lower()}"
            ],
        },
        CloudWatchOutputConfig={
            "CloudWatchLogGroupName": RUN_ANSIBLE_COMMAND_LOG_GROUP_NAME,
            "CloudWatchOutputEnabled": True,
        },
    )

    command_id = response["Command"]["CommandId"]
    time.sleep(5)
    while True:
        response = ssm.list_commands(CommandId=command_id)
        if response["Commands"][0]["Status"] in ("InProgress", "Pending"):
            logger.debug("Command status is " + response["Commands"][0]["Status"])
            time.sleep(10)
        else:
            break

    if response["Commands"][0]["Status"] != "Success":
        logger.fatal("Provision playbook run did not exit with status code 0")
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        raise CommandRunError()

    # run httrack

    # response = ssm.send_command(
    #     InstanceIds=[instance_id],
    #     DocumentName="AWS-RunShellScript",
    #     TimeoutSeconds=9001,
    #     Parameters={
    #         "commands": ["sudo -H -u ec2-user /bin/bash /home/ec2-user/run_httrack.sh"],
    #     },
    #     CloudWatchOutputConfig={
    #         "CloudWatchLogGroupName": RUN_HTTRACK_COMMAND_LOG_GROUP_NAME,
    #         "CloudWatchOutputEnabled": True,
    #     },
    # )

    return {
        # "command_id": response["Command"]["CommandId"],
        "instance_id": instance_id,
        "status": "ok",
    }
