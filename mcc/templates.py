# -*- coding: utf-8 -*-
"""Create and Manage Launch Templates"""
import os
import time

import boto3
import botocore


def create_security_group(security_groups=None, ips=None, ports=None, rules=None, ec2=boto3.resource("ec2")):
    "Create Security Group"
    vpc_id = ec2.meta.client.describe_vpcs().get('Vpcs', [{}])[0].get('VpcId', '')

    kwargs = {"Description": f"default-sg for VPC {vpc_id}",
              "GroupName": f"{vpc_id}_default", "VpcId": vpc_id}
    try:
        security_group = ec2.create_security_group(**kwargs)
        security_group_id = security_group.id

        if rules is None:
            rules = []
            if ports is not None and (ips is not None or security_groups is not None):
                for port, protocol in ports.items():
                    base_rule = dict(IpProtocol=protocol, FromPort=port, ToPort=port)
                    if ips is not None:
                        ip_rule = base_rule
                        ip_rule["IpRanges"] = [{"CidrIp": ip, "Description": name} for name, ip in ips.items()]
                        rules.append(ip_rule)
                    if security_groups is not None:
                        sg_rule = base_rule
                        sg_rule["UserIdGroupPairs"] = [{"GroupId": sg, "Description": name} for name, sg in security_groups.items()]
                        rules.append(sg_rule)
                    base_rule["UserIdGroupPairs"] = [{"GroupId": security_group_id, "Description": "Default Security Group"}]
                    rules.append(base_rule)

        response = ec2.meta.client.authorize_security_group_ingress(GroupId=security_group_id, IpPermissions=rules)
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidGroup.Duplicate":
            security_group_id = ec2.meta.client.describe_security_groups(GroupNames=[kwargs["GroupName"]])["SecurityGroups"][0]["GroupId"]
        else:
            raise e

    return security_group_id


def create_key_pair(keyname="aws_default_key", ec2=boto3.resource("ec2")):
    "Creates Key Pair"
    try:
        response = ec2.meta.client.create_key_pair(KeyName=keyname)
        with open(os.path.join(os.environ["HOME"], ".ssh", f"{keyname}.pem"), "w") as f:
            f.write(response["KeyMaterial"])
        os.chmod(os.path.join(os.environ["HOME"], ".ssh", f"{keyname}.pem"), 0o600)
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidKeyPair.Duplicate":
            pass
        else:
            raise e

    return keyname


def build_template_userdata(access_key, secret_key, region):
    "Create UserData script for instance prep"
    with open("template_script.sh", "r") as f:
        launch_script = f.read()

        # Load Additional Python Requirements
        with open("requirements.txt", "r") as f:
            py_reqs = " ".join(f.read().split("\n"))

        template_options = {r"{py_ver}": "3.7",
                            r"{py_reqs}": py_reqs,
                            r"{aws_access_key}": access_key,
                            r"{aws_secret_key}": secret_key,
                            r"{aws_region}":region}

        for key, value in template_options.items():
            launch_script = launch_script.replace(key, value)

    return launch_script


def create_custom_image(security_group_id, keyname, launch_script="", default_ami="ami-0ff8a91507f77f867", instance_type="t2.micro", ec2=boto3.resource("ec2")):
    "Creates custom ec2 ami"
    launch_options = {"ImageId": default_ami, "SecurityGroupIds": [security_group_id], "UserData": launch_script,
                      "MinCount": 1, "MaxCount": 1, "KeyName": keyname, "InstanceType": instance_type,
                      "InstanceInitiatedShutdownBehavior": "stop"}

    base_instance = ec2.create_instances(**launch_options)[0]
    base_instance.wait_until_running()

    userdata_running = True
    while userdata_running:
        instance_details = ec2.meta.client.describe_instances(InstanceIds=[base_instance.id])["Reservations"][0]["Instances"][0]
        for tag in instance_details.get("Tags", []):
            if tag["Key"] == "UserData" and tag["Value"] == "complete":
                userdata_running = False
        time.sleep(5)

    try:
        response = ec2.meta.client.create_image(InstanceId=base_instance.id, Name="default_ami", Description="default custom image")
        custom_ami_id = response["ImageId"]

        ami_status = ec2.meta.client.describe_images(ImageIds=[custom_ami_id])["Images"][0]["State"]
        while ami_status == "pending":
            time.sleep(5)
            ami_status = ec2.meta.client.describe_images(ImageIds=[custom_ami_id])["Images"][0]["State"]

        if ami_status == "available":
            base_instance.terminate()
        elif ami_status == "failed":
            raise Exception("Creation of AMI failed")
        else:
            print(f"Warning: AMI {custom_ami_id} has status {ami_status}")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidAMIName.Duplicate":
            pass
        else:
            raise e

    return custom_ami_id


def create_launch_template(custom_ami_id, security_group_id, ec2=boto3.resource("ec2")):
    "Creates launch template"
    try:
        response = ec2.meta.client.create_launch_template(LaunchTemplateName="default_template", LaunchTemplateData=dict(ImageId=custom_ami_id, SecurityGroupIds=[security_group_id], KeyName="aws_default_key"))
        template_id = response["LaunchTemplate"]["LaunchTemplateId"]
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidLaunchTemplateName.AlreadyExistsException":
            pass
        else:
            raise e

    return template_id


def create_redis_server(security_group_id, name="redis-default-cache", nodes=1, instance_type="cache.t2.micro", port=6379, redis_client=boto3.client("elasticache")):
    "Creates a ElastiCache Redis Server"
    try:
        response = redis_client.create_cache_cluster(CacheClusterId=name,
                                                     AZMode="single-az",
                                                     NumCacheNodes=nodes,
                                                     CacheNodeType=instance_type,
                                                     Engine="redis",
                                                     SecurityGroupIds=[security_group_id],
                                                     Port=port)

        status = response["CacheCluster"]["CacheClusterStatus"]
        while status != "available":
            time.sleep(5)
            response = redis_client.describe_cache_clusters(CacheClusterId=name, ShowCacheNodeInfo=True)
            status = response["CacheClusters"][0]["CacheClusterStatus"]
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] != "CacheClusterAlreadyExists":
            raise e

    response = redis_client.describe_cache_clusters(CacheClusterId=name, ShowCacheNodeInfo=True)
    endpoint = response["CacheClusters"][0]["CacheNodes"][0]["EndPoint"]

    return name, endpoint, port
