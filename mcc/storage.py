# -*- coding: utf-8 -*-
"""Storage Management"""
import random

import boto3


def connection():
    """Creates an s3 client connection"""
    return boto3.client("s3")


def build_storage(name="", s3=connection()):
    """Builds a storage bucket for the calculation

    Parameters
    ----------
    name : string, optional
        Name of the bucket. (Default: autogenerated)

    s3 : s3 object, optional
        S3 client object (Default: Creates a new one)

    Returns
    -------
    name : string
        Name of the bucket

    response : dict
        api response
    """
    if not name:
        name = str(hex(random.randint(1e10, 1e11-1)))

    response = s3.create_bucket(Bucket=name)

    return name, response


def close_storage(name, s3=connection(), safe=True):
    """Closes storage bucket

    Parameters
    ----------
    s3 : S3 object
        S3 client object

    name : string
        Name of bucket to delete

    safe : bool, optional
        Safely delete will only delete if bucket is empty. (Default: True)
    """
    if safe:
        response = s3.delete_bucket(Bucket=name)
    else:
        empty_storage(name, s3)
        response = s3.delete_bucket(Bucket=name)

    return response


def empty_storage(name, s3=connection()):
    """Empties storage bucket

    Parameters
    ----------
    s3 : s3 object
        S3 client objection

    name : string
        Name of bucket to empty

    Returns
    -------
    response : dict
        api response
    """
    response = []
    object_list = s3.list_objects(Bucket=name)
    for file in object_list.get("Contents", []):
        response.append(s3.delete_object(Bucket=name, Key=file["Key"]))

    return response


def get_bucket_names(s3=connection()):
    """Gets the names of all of the buckets in s3 coonection

    Parameters
    ----------
    s3 : s3 object, optional
        S3 client object (Default: creates connection from aws configuration)

    Returns
    -------
    names : list{string}
        the names, if any, of the existing buckets in your s3
    """
    return [bucket["Name"] for bucket in s3.list_buckets()["Buckets"]]


def upload(bucket, file, s3=connection()):
    """Uploads a file to a specified bucket

    Parameters
    ----------
    bucket : string
        Name of bucket

    file : string
        Path to file

    s3 : s3 object, optional
        S3 client object (Default: auto-connect)

    Returns
    -------
    response : bucket
    """
    response = s3.upload_file(file, bucket, file)
    return response


def download(bucket, file, key=None, output=None, s3=connection()):
    """Download a file to a specified bucket

    Parameters
    ----------
    bucket : string
        Name of bucket

    file : string
        Path to file

    key : string, optional
        path to file in bucket (Default: will try to determine key from filename)

    output : string, optional
        local path to download to

    s3 : s3 object, optional
        S3 client object (Default: auto-connect)

    Returns
    -------
    response : bucket
    """
    if key is None:
        obj_list = s3.list_objects(Bucket=bucket)
        for obj in obj_list.get("Contents", []):
            if obj["Key"].endswith(file):
                key = obj["Key"]
                break

    if output is None:
        output = file

    response = s3.download_file(bucket, key, output)
    return response
