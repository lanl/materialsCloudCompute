# -*- coding: utf-8 -*-
"""Instance Management"""
import json
import logging
import os

import boto3

from .statistics import get_ec2_vcpus


def upload_user_entrypoint(s3_bucket_name, location="script", s3=boto3.resource("s3")):
    """Uploads the user script to script/ on s3 bucket"""
    files = [os.path.join(dp, f) for dp, dn, fn in os.walk(os.path.expanduser(location)) for f in fn]
    for file in files:
        s3.meta.client.upload_file(file, s3_bucket_name, f"script/{os.path.relpath(file, location)}")


def upload_req_files(s3_bucket_name, s3=boto3.resource("s3"), combine_data="combine_data.py", points="points.py"):
    """Uploads required scripts to s3 bucket"""
    files = [combine_data, points, "worker_userdata.py"]
    for file in files:
        s3.meta.client.upload_file(file, s3_bucket_name, f"script/{file}")


def launch_manager(instance_type="t2.micro", template_id="", template_version="1", s3_bucket="",
                   worker_instance_type="t2.micro", worker_template_id="", worker_template_version="",
                   vcpus_per_node=None, hyperthreading=True, entry_point="", redis_endpoint="",
                   redis_port=6379, ec2=boto3.resource("ec2")):
    """Launches manager instance"""
    if not worker_template_id:
        worker_template_id = template_id

    if not worker_template_version:
        worker_template_version = template_version

    if vcpus_per_node is None:
        vcpus_per_node = get_ec2_vcpus(instance_type=worker_instance_type)

    manager_data = dict(s3_bucket=s3_bucket, worker_template_id=worker_template_id, worker_instance_type=worker_instance_type,
                        worker_template_version=worker_template_version, hyperthread_const=int(not hyperthreading) + 1,
                        vcpus_per_node=vcpus_per_node, redis_endpoint=redis_endpoint, redis_port=redis_port,
                        entry_point=entry_point)

    with open("manager_userdata.py", "r") as f:
        userdata = f.read()
        userdata = userdata.replace(r"{{manager_data}}", json.dumps(manager_data))

    launch = dict(LaunchTemplate={'LaunchTemplateId': template_id, 'Version': template_version}, UserData=userdata,
                  InstanceType=instance_type, MaxCount=1, MinCount=1, InstanceInitiatedShutdownBehavior="terminate")

    manager = ec2.create_instances(**launch)[0]

    manager.wait_until_running()
    manager.load()

    logging.info(f"Manager Instance {manager.id} is operational!")

    return dict(Instance=manager, UserData=userdata)
