# materialsCloudCompute

Release as Open-Source under BSD-3 license by Los Alamos National Laboratory (C19104)

materialsCloudCompute (mCC) is a software package for running easily parallelizable materials science theoretical computations on Amazon Web Services (AWS) infrastructure. mCC provides tools to partition out computational problem into smaller subproblems which can be run in parallel, and ensure that each of those subproblems completes successfully. It utilizes the following AWS services: EC2, S3, and RDS. It operates by launch a managing EC2 instance, which can launch worker instances that perform the calculations. The Managing instance tracks the subproblems and ensures that the Worker instances continue to operation, killing and relaunching them if they fail.

## Descriptions of Functionality

materialsCloudCompute (mCC) provides the following functionalities (enumerated by source file located in `mcc`):

`analysis.py` :: functions for aggregating and analyzing log files from the AWS EC2 instances, including information about costs and total and average time to run subproblems.

`clean.py` :: functions for cleaning up S3 instances, EC2 templates and images, RDS caches, and security credentials on AWS

`config.py` :: get and set local AWS credentials using awscli

`launch.py` :: launches the EC2 instances and uploads necessary files from the S3 bucket to EC2 instances

`logger.py` :: logging functions to create log files for export and analysis

`manager_userdata.py` :: script to be run on managing instance, performs tasks including logging, launching and killing EC2 instances, tracks subproblems in the RDS cache, and combines subproblem results.

`statistics.py` :: functions for getting information about EC2 instances from the AWS API

`storage.py` :: functions for managing S3 storage, including upload and download, creation and deletion

`template_userdata.sh` :: startup bash script used to create custom EC2 images

`templates.py` :: functions to create all necessary aspects of EC2 instances, including secruity groups, key pairs, customizing the template scripts, creating the custom EC2 image, and creating the RDS cache (redis) server

`worker_userdata.py` :: script to be run on the worker instances that actually perform the calculations. Contains logic for keeping instances alive, logging, and performing the calculations of the subproblems provided to them by the Managing instance via the RDS cache (redis) server.

See docstrings for intended usages.

## Example of EC2 instance setup

Before using, you must have an AWS account, and use the AWS CLI to configure your credentials on your local machine, see [https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

```python
import mcc
import boto3

ec2 = boto3.resource("ec2")
rc = boto3.client("elasticache")

ips = {"my address": "192.168.1.0/16"}
ports = {80: "tcp", 22: "tcp", 6379: "tcp"}

security_group = mcc.templates.create_security_group(ec2, ips=ips, ports=ports)
keyname = mcc.templates.create_key_pair(ec2)
template_userdata = mcc.templates.build_template_userdata(*get_aws_settings())
custom_image_id = mcc.templates.create_custom_image(ec2, security_group, keyname, launch_script=template_userdata)
template_id = mcc.templates.create_launch_template(ec2, custom_image_id, security_group)
redis_id, redis_endpoint, redis_port = mcc.templates.create_redis_server(rc, security_group)
```

## Example of S3 setup

```python
s3_name = mcc.storage.create_s3_bucket(boto3.resource("s3"))

mcc.launch.upload_user_endpoint(s3_name)  # uploads all files in `script` directory to S3
mcc.launch.upload_req_files(s3_name)  # uploads template files, combine_data.py and points.py to S3
```

## Example of running calculations

```python
manager = launch_master_node(master_template_id=template_id,
                             s3_bucket_name=s3_name,
                             worker_instance_type="t3.medium",
                             entry_point_script="my_script.py",
                             hyperthreading=True,
                             redis_endpoint=redis_endpoint)
```

## Example of `points.py`

```python
import numpy as np


def get_points():
    rho = np.arange(0.001, 5.051, 0.05)
    theta = np.arange(0.5, 30, 1.0)
    z = np.arange(0, 0.051, 0.025)

    RHO, THETA, Z = np.meshgrid(rho, theta, z)

    kzs = Z.flatten()
    kys = (RHO * np.sin(np.deg2rad(THETA))).flatten()
    kxs = (RHO * np.cos(np.deg2rad(THETA))).flatten()

    points = [[item for item in triple] for triple in zip(kxs, kys, kzs)]

    rho = np.arange(5.101, 8.051, 0.05)
    theta = np.arange(0, 30, 0.5)
    z = np.arange(0, 0.051, 0.025)

    RHO, THETA, Z = np.meshgrid(rho, theta, z)

    kzs = Z.flatten()
    kys = (RHO * np.sin(np.deg2rad(THETA))).flatten()
    kxs = (RHO * np.cos(np.deg2rad(THETA))).flatten()

    points2 = [[item for item in triple] for triple in zip(kxs, kys, kzs)]

    for point in points2:
        points.append(point)

    return points


if __name__ == "__main__":
    points = get_points()
```

## Example of `combine_data.py`

```python
import h5py

file_extension = "h5"

def combine_data(files, fileout):
    sizes = []
    for file in files:
        with h5py.File(file, "r") as f:
            dset = f["data"]
            sizes.append(dset.shape[0])

    size = sum(sizes)
    with h5py.File(fileout, "w") as f:
        f.create_dataset("data", (size, 5), maxshape=(size, 5), dtype="float64")
        dset = f["data"]
        start = 0
        end = 0
        for file in files:
            with h5py.File(file, "r") as _f:
                _dset = _f["data"]
                end = start + _dset.shape[0]
                dset[start:end,:] = _dset[:,:]
                start = end
```

## Copyright

Copyright 2020. Triad National Security, LLC. All rights reserved.

This program was produced under U.S. Government contract 89233218CNA000001 for Los Alamos
National Laboratory (LANL), which is operated by Triad National Security, LLC for the U.S.
Department of Energy/National Nuclear Security Administration. All rights in the program are
reserved by Triad National Security, LLC, and the U.S. Department of Energy/National Nuclear
Security Administration. The Government is granted for itself and others acting on its behalf a
nonexclusive, paid-up, irrevocable worldwide license in this material to reproduce, prepare
derivative works, distribute copies to the public, perform publicly and display publicly, and to permit
others to do so.
