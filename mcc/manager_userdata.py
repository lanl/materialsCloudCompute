#!/opt/anaconda/bin/python
"""UserData Script for Manager Instance"""
import json
import logging
import os
import sys
import time
import requests

import boto3
import botocore

import arrow
import redis

sys.path.append("/")

class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n':
            self.level(message)

    def flush(self):
        self.level(sys.stderr)


def check_stalled(in_progress, instances):
    "Checks active instances for stalls"
    stalled = []
    for instance_id, info in in_progress.items():
        last = arrow.get(info["check_in"])
        now = arrow.utcnow()
        tdelta = now - last
        if tdelta.total_seconds() > 240:
            instance = None
            for inst in instances:
                if inst.id == instance_id:
                    instance = inst
                    break
            stalled.append((instance, info["points"]))

    return stalled


logging.basicConfig(filename="manager.log", level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", filemode="a")
logger = logging.getLogger(__name__)
sys.stdout = LoggerWriter(logger.debug)
sys.stderr = LoggerWriter(logger.warning)

logging.info("START")

manager_data = json.loads("{{manager_data}}")

logging.info(f"Hyperthreading = {not bool(manager_data['hyperthread_cost'] - 1)}")

ec2 = boto3.resource("ec2")
s3 = boto3.resource("s3")

for file in ["userdata_template", "points", "combine_data_template"]:
    response = s3.meta.client.download_file(manager_data['s3_bucket'], f"script/{file}.py", f"{file}.py")

from points import get_points
points = get_points()

instance_id = requests.get("http://169.254.169.254/latest/meta-data/instance-id").text

rcache = redis.Redis(host=manager_data['redis_endpoint'], port=manager_data['redis_port'], db=0)
rcache.set(f"{instance_id}_all", json.dumps(points))
rcache.set(f"{instance_id}_remaining", json.dumps(points))
rcache.set(f"{instance_id}_completed", json.dumps([]))
rcache.set(f"{instance_id}_in_progress", json.dumps({}))

worker_data = dict(s3_bucket=manager_data['s3_bucket'], entry_point=manager_data['entry_point'],
                   manager_instance_id=instance_id, hyperthread_const=manager_data['hyperthread_const'],
                   redis_endpoint=manager_data['redis_endpoint'], redis_port=manager_data['redis_port'])

with open("worker_userdata.py", "r") as f:
    userdata = f.read()
    userdata = userdata.replace(r"{{worker_data}}", json.dumps(worker_data))

launch = dict(LaunchTemplate={'LaunchTemplateId': manager_data['worker_template_id'], 'Version': manager_data['worker_template_version']},
              InstanceType=manager_data['worker_instance_type'], MaxCount=len(points) // manager_data['vcpus_per_node'] * manager_data['hyperthread_cost'] + 1,
              MinCount=1, InstanceInitiatedShutdownBehavior="terminate", UserData=userdata)

try:
    instances = ec2.create_instances(**launch)
except botocore.exceptions.ClientError as e:
    if e.response["Error"]["Code"] != "InstanceLimitExceeded":
        raise e

if not instances:
    logging.error(f"Manager failed to launch any '{manager_data['worker_instance_type']}' instances!")
    s3.meta.client.upload_file("manager.log", manager_data['s3_bucket'], f"results/{instance_id}_manager.log")
    ec2.meta.client.describe_instances(InstanceIds=[instance_id])[0].terminate()

logging.info(f"Manager launched {len(instances)} '{manager_data['worker_instance_type']}' Instances.")

remaining_points = json.loads(rcache.get(f"{instance_id}_remaining"))
completed_points = json.loads(rcache.get(f"{instance_id}_completed"))
all_points = json.loads(rcache.get(f"{instance_id}_all"))

_points_in_progress = 0
_completed = 0
_stalled = 0

while len(completed_points) < len(all_points):
    time.sleep(30)
    completed_points = json.loads(rcache.get(f"{instance_id}_completed"))
    in_progress = json.loads(rcache.get(f"{instance_id}_in_progress"))
    points_in_progress = []

    for inst, info in in_progress.items():
        for point in info.get("points", []):
            points_in_progress.append(point)

    stalled = check_stalled(in_progress, instances)

    logging.debug(str(in_progress))

    if len(points_in_progress) != _points_in_progress or len(completed_points) != _completed or len(stalled) != _stalled:
        _points_in_progress, _completed, _stalled = len(points_in_progress), len(completed_points), len(stalled)
        logging.info(f"completed: {_completed}  in_progress: {_points_in_progress}  stalled: {_stalled}")

    for instance, points in stalled:
        if len(points) > 0:
            logging.info(f"Instance '{instance.id}' has stalled, returning points {points} to queue and terminating")
            instance.terminate()
            instance.wait_until_terminated()
            with rcache.pipeline() as pipe:
                while 1:
                    try:
                        pipe.watch(f"{instance_id}_remaining")
                        pipe.watch(f"{instance_id}_in_progress")
                        remaining = json.loads(pipe.get(f"{instance_id}_remaining"))
                        in_progress = json.loads(pipe.get(f"{instance_id}_in_progress"))
                        del in_progress[instance.id]
                        for point in points:
                            remaining.append(point)
                        pipe.multi()
                        pipe.set(f"{instance_id}_remaining", json.dumps(remaining))
                        pipe.set(f"{instance_id}_in_progress", json.dumps(in_progress))
                        pipe.execute()
                        break
                    except redis.WatchError:
                        continue
            try:
                instances.append(ec2.create_instances(**launch)[0])
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "InstanceLimitExceeded":
                    continue

rcache.delete(f"{instance_id}_remaining")
rcache.delete(f"{instance_id}_completed")
rcache.delete(f"{instance_id}_in_progress")
rcache.delete(f"{instance_id}_all")

logging.info("No Points Remaining.")

from combine_data import combine_data, file_extensions, output_file

files = []
for file_extension in file_extensions:
    files.extend([obj.key for obj in s3.Bucket(manager_data['s3_bucket']).objects.all() if obj.key.startswith(f"results/{instance_id}") and obj.key.endswith(f".{file_extension}")])

logging.info(f"Combining {len(files)} Partial Data Files")
os.makedirs(f"results/{instance_id}")
for file in files:
    response = s3.meta.client.download_file(manager_data['s3_bucket'], file, file)

fileout = f"results/{instance_id}_{output_file}"

combine_data(files, fileout)

logging.info(f"Uploading combined data file '{fileout}' to S3 bucket")
response = s3.meta.client.upload_file(fileout, manager_data['s3_bucket'], f"{fileout}")

for file in files:
    try:
        os.remove(file)
        response = s3.meta.client.delete_object(Bucket=manager_data['s3_bucket'], Key=file)
    except FileNotFoundError:
        pass

log_files = [obj.key for obj in s3.Bucket(manager_data['s3_bucket']).objects.all() if obj.key.startswith(f"results/{instance_id}") and obj.key.endswith(f".log")]
logging.info(f"Combining {len(log_files)} Worker Logs")

worker_log_lines = []
for file in log_files:
    s3.meta.client.download_file(manager_data['s3_bucket'], file, file)
    with open(file, "r") as f:
        worker_log_lines.extend(f.readlines())
    os.remove(file)
    response = s3.meta.client.delete_object(Bucket=manager_data['s3_bucket'], Key=file)

worker_log_lines.sort()

with open("workers.log", "a") as f:
    f.write("".join(worker_log_lines))

logging.info("END")

s3.meta.client.upload_file("manager.log", manager_data['s3_bucket'], f"results/{instance_id}_manager.log")
s3.meta.client.upload_file("workers.log", manager_data['s3_bucket'], f"results/{instance_id}_workers.log")

os.removedirs(f"results/{instance_id}")

ec2.meta.client.describe_instances(InstanceIds=[instance_id])[0].terminate()
