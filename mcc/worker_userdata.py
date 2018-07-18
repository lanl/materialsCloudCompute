#!/opt/anaconda/bin/python
"""UserData template for workers"""
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from multiprocessing import cpu_count
from multiprocessing.dummy import Pool
from threading import Thread
import requests

import arrow
import boto3
import psutil
import redis


class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n':
            self.level(message)

    def flush(self):
        self.level(sys.stderr)

logging.basicConfig(filename="worker.log", level=logging.DEBUG, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", filemode="a")
logger = logging.getLogger(__name__)
sys.stdout = LoggerWriter(logger.debug)
sys.stderr = LoggerWriter(logger.warning)

instance_id = requests.get('http://169.254.169.254/latest/meta-data/instance-id').text

worker_data = json.loads("{{worker_data}}")

s3 = boto3.resource("s3")
files = [obj.key for obj in s3.Bucket(worker_data['s3_bucket']).objects.all() if obj.key.startswith(f"script/")]
for file in files:
    s3.meta.client.download_file(worker_data['s3_bucket'], file, file.replace("script/", ""))

try:
    os.mkdir("results")
except FileExistsError:
    pass

rcache = redis.Redis(host=worker_data['redis_endpoint'], port=worker_data['redis_port'], db=0)
with rcache.pipeline() as pipe:
    while True:
        try:
            pipe.watch(f"{worker_data['manager_instance_id']}_in_progress")
            in_progress = json.loads(pipe.get(f"{worker_data['manager_instance_id']}_in_progress"))
            in_progress[instance_id] = dict(points=[], check_in=str(arrow.utcnow()))
            pipe.multi()
            pipe.set(f"{worker_data['manager_instance_id']}_in_progress", json.dumps(in_progress))
            pipe.execute()
            break
        except redis.WatchError:
            continue


def main(fileout):
    "Main script call"
    remaining = json.loads(rcache.get(f"{worker_data['manager_instance_id']}_remaining"))
    while remaining:
        with rcache.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(f"{worker_data['manager_instance_id']}_remaining")
                    pipe.watch(f"{worker_data['manager_instance_id']}_in_progress")

                    remaining = json.loads(pipe.get(f"{worker_data['manager_instance_id']}_remaining"))
                    in_progress = json.loads(pipe.get(f"{worker_data['manager_instance_id']}_in_progress"))

                    try:
                        point = remaining.pop()
                        in_progress[instance_id]["points"].append(point)
                        in_progress[instance_id]["check_in"] = str(arrow.utcnow())
                    except IndexError:
                        point = None
                        break

                    pipe.multi()
                    pipe.set(f"{worker_data['manager_instance_id']}_in_progress", json.dumps(in_progress))
                    pipe.set(f"{worker_data['manager_instance_id']}_remaining", json.dumps(remaining))
                    pipe.execute()
                    break
                except redis.WatchError:
                    continue

        if point is not None:
            logging.info(f"Starting point {point}")
            subprocess.call(["/opt/anaconda/bin/python", "{script_path}", fileout] + [str(i) for i in point])
            logging.info(f"Point {point} finished")

            with rcache.pipeline() as pipe:
                while True:
                    try:
                        pipe.watch(f"{worker_data['manager_instance_id']}_in_progress")
                        pipe.watch(f"{worker_data['manager_instance_id']}_completed")
                        completed = json.loads(pipe.get(f"{worker_data['manager_instance_id']}_completed"))
                        in_progress = json.loads(pipe.get(f"{worker_data['manager_instance_id']}_in_progress"))
                        in_progress[instance_id]["points"].remove(point)
                        completed.append(point)
                        pipe.multi()
                        pipe.set(f"{worker_data['manager_instance_id']}_completed", json.dumps(completed))
                        pipe.set(f"{worker_data['manager_instance_id']}_in_progress", json.dumps(in_progress))
                        pipe.execute()
                        break
                    except redis.WatchError:
                        continue
        remaining = json.loads(rcache.get(f"{worker_data['manager_instance_id']}_remaining"))


def is_alive():
    "Function to check if worker instance is still alive"
    while True:
        time.sleep(15)
        cpu = max([sum(y) / len(y) for y in zip(*[psutil.cpu_percent(interval=1, percpu=True) for x in range(10)])])
        if cpu > 25.0:
            with rcache.pipeline() as pipe:
                while True:
                    try:
                        pipe.watch(f"{worker_data['manager_instance_id']}_in_progress")
                        in_progress = json.loads(pipe.get(f"{worker_data['manager_instance_id']}_in_progress"))
                        now = str(arrow.utcnow())
                        try:
                            in_progress[instance_id]["check_in"] = now
                        except KeyError:
                            break
                        pipe.multi()
                        pipe.set(f"{worker_data['manager_instance_id']}_in_progress", json.dumps(in_progress))
                        pipe.execute()
                        logging.debug(f"Updated {instance_id} 'check_in' to {now} ::: CPU @ {cpu}%")
                        break
                    except redis.WatchError:
                        continue
        else:
            break


thread = Thread(target=is_alive)
thread.start()

vcpus = cpu_count()
if vcpus > 1:
    vcpus //= worker_data['hyperthread_const']

pool = Pool(vcpus)
pool.map(main, [f"output/{instance_id}_{i+1}.h5" for i in range(vcpus)])

with rcache.pipeline() as pipe:
    while True:
        try:
            pipe.watch(f"{worker_data['manager_instance_id']}_in_progress")
            in_progress = json.loads(pipe.get(f"{worker_data['manager_instance_id']}_in_progress"))
            del in_progress[instance_id]
            pipe.multi()
            pipe.set(f"{worker_data['manager_instance_id']}_in_progress", json.dumps(in_progress))
            pipe.execute()
            logging.info(f"Deleting instance {instance_id} from 'in_progress'")
            break
        except redis.WatchError:
            continue

logging.info(f"No points remaining, terminating instance {instance_id}")

shutil.copyfile("worker.log", f"output/{instance_id}.log")

for file in os.listdir("output"):
    s3.meta.client.upload_file(file, worker_data['s3_bucket'], f"results/{worker_data['manager_instance_id']}/{file}")

ec2 = boto3.resource("ec2")
ec2.meta.client.describe_instances(InstanceIds=[instance_id])[0].terminate()
