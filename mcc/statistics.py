# -*- coding: utf-8 -*-
"""Functions for estimating pricing"""
import json

import boto3


def get_ec2_data(client=boto3.client("pricing", region_name="us-east-1"), region='US East (N. Virginia)',
                 instance_type='t2.micro', os='Linux', search_filter=None):
    "Returns price of EC2 instance in USD/hr"
    if search_filter is None:
        search_filter = [{"Field": "tenancy", "Value": "shared", "Type": "TERM_MATCH"},
                         {"Field": "operatingSystem", "Value": f"{os}", "Type": "TERM_MATCH"},
                         {"Field": "preInstalledSw", "Value": "NA", "Type": "TERM_MATCH"},
                         {"Field": "instanceType", "Value": f"{instance_type}", "Type": "TERM_MATCH"},
                         {"Field": "location", "Value": f"{region}", "Type": "TERM_MATCH"}]

    return client.get_products(ServiceCode='AmazonEC2', Filters=search_filter)


def get_ec2_price(client=boto3.client("pricing", region_name="us-east-1"), region='US East (N. Virginia)',
                  instance_type='t2.micro', os='Linux', search_filter=None):
    "Returns price of EC2 instance in USD/hr"
    data = get_ec2_data(client, region, instance_type, os, search_filter)

    od = json.loads(data['PriceList'][0])['terms']['OnDemand']

    id1 = list(od)[0]
    id2 = list(od[id1]['priceDimensions'])[0]

    return float(od[id1]['priceDimensions'][id2]['pricePerUnit']['USD'])


def get_ec2_vcpus(client=boto3.client("pricing", region_name="us-east-1"), region='US East (N. Virginia)',
                  instance_type='t2.micro', os='Linux', search_filter=None):
    "Returns number of vcpus on a given instance"
    data = get_ec2_data(client, region, instance_type, os, search_filter)

    return int(json.loads(data["PriceList"][0])['product']['attributes']['vcpu'])


def get_running_instances(ec2):
    filters = [{"Name": "instance-state-name", "Values": ["running"]}]
    return ec2.instances.filter(Filters=filters)
