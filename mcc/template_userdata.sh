#!/bin/bash

yum update -y
yum install -y tmux htop

wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh -b -p /opt/anaconda
export PATH="/opt/anaconda/bin:$PATH"

source /opt/anaconda/bin/activate
conda install -y -q python={py_ver} boto3 botocore redis-py arrow psutil
conda install -y -q {py_reqs}

aws configure set aws_access_key_id {aws_access_key}
aws configure set aws_secret_access_key {aws_secret_key}
aws configure set region {aws_region}

INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 create-tags --resource $INSTANCE_ID --tags Key=UserData,Value=complete

sed -i 's/scripts-user$/\[scripts-user, always\]/' /etc/cloud/cloud.cfg
