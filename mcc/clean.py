# -*- coding: utf-8 -*-
"""Functions for cleaning up MCC created AWS artifacts"""
import os

import boto3
import botocore


def delete_s3_bucket(bucket_name, safe=True, s3=boto3.resource("s3")):
    try:
        response = s3.meta.client.delete_bucket(Bucket=bucket_name)
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "BucketNotEmpty":
            if safe:
                raise e
            else:
                responses = []
                object_list = s3.meta.client.list_objects(Bucket=bucket_name)
                for file in object_list:
                    responses.append(s3.meta.client.delete_object(Bucket=bucket_name, Key=file["Key"]))


def delete_keypair(keyname, ec2=boto3.resource("ec2")):
    os.remove(os.path.join(os.environ["HOME"], ".ssh", f"{keyname}.pem"))
    response = ec2.meta.client.delete_key_pair(KeyName=keyname)
    return response


def delete_launch_template(template_id, ec2=boto3.resource("ec2")):
    response = ec2.meta.client.delete_launch_template(LaunchTemplateId=template_id)


def delete_custom_image(custom_image_id, ec2=boto3.resource("ec2")):
    response = ec2.meta.client.deregister_image(ImageId=custom_image_id)


def delete_security_group(security_group_id, ec2=boto3.resource("ec2")):
    response = ec2.meta.client.delete_security_group(GroupId=security_group_id)


def delete_cache_cluster(name, cache_client=boto3.client("elasticache")):
    response = cache_client.delete_cache_cluster(CacheClusterId=name)
