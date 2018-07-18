# -*- coding: utf-8 -*-
"""Configuration Functions"""
import subprocess

import botocore


def get_aws_credentials(session=botocore.session.get_session()):
    "Returns access key, secret key and region"
    access_key = session.get_credentials().access_key
    secret_key = session.get_credentials().secret_key
    region = session.get_config_variable("region")

    return access_key, secret_key, region


def set_aws_credentials(access_key, secret_key, region):
    "Sets shared aws credentials file"
    subprocess.call(["aws", "configure", "set", "aws_access_key_id", access_key])
    subprocess.call(["aws", "configure", "set", "aws_secret_access_key", secret_key])
    subprocess.call(["aws", "configure", "set", "aws_region", region])
