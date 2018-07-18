# -*- coding: utf-8 -*-
"""Data analysis of Log files"""
import os
import re

import arrow

from .statistics import get_ec2_price, get_ec2_vcpus


def collect_data(files):
    "Collects relevant data from log files"
    data = {}

    for file in files:
        _data = {"stalls": 0}
        with open(os.path.join("results", file), "r") as f:
            for line in f.readlines():
                if "START" in line:
                    _data["start"] = arrow.get(line.split(',')[0])
                if "END" in line:
                    _data["end"] = arrow.get(line.split(',')[0])

                if "Manager launched" in line:
                    reg = r"MASTER launched (\d+) \'(\w\d\.[\w\d]+)\' Instances\."
                    matches = re.findall(reg, line)[0]
                    _data["instances"] = int(matches[0])
                    _data["instance_type"] = matches[1]

                if "Hyperthreading = True" in line:
                    _data["hyper"] = 1
                elif "Hyperthreading = False" in line:
                    _data["hyper"] = 2

                if "stalled:" in line:
                    reg = r"stalled:\s(\d+)"
                    stalled = int(re.findall(reg, line)[0][0])
                    _data["stalls"] += stalled

        if "instances" not in _data:
            continue

        data[file.replace("_manager.log", "")] = _data

    return data


def aggregate_data(data):
    "aggregates information from data-collected log files"
    for instance, info in data.items():
        info["data_size"] = os.stat(f"results/{instance}.h5").st_size / 1024
        info["total_time"] = (info["end"] - info["start"]).total_seconds() / 60 / 60

        if info["total_time"] < 1:
            charge_time = 1.0
        else:
            charge_time = info["total_time"]

        info["vcpus"] = (info["instances"] * get_ec2_vcpus(instance_type=info["instance_type"]) + 1)
        info["total_cost"] = charge_time * (info["instances"] * get_ec2_price(instance_type=info["instance_type"]) + get_ec2_price(instance_type="t2.micro")) + info["stalls"] * get_ec2_price(instance_type=info["instance_type"])
        info["cost_per_vcpu"] = info["total_cost"] / info["vcpus"]
        info["time_per_vcpu"] = info["total_time"] / info["vcpus"]

    return data


def analyse_data(data, data_filter=""):
    "analyses data from data aggregated log files"
    analysis = dict()
    for instance, info in data.items():
        if info["data_size"] == data_filter:
            if info["instance_type"] not in analysis:
                analysis[info["instance_type"]] = dict(total_hours=[], total_cost=[], cost_per_vcpu=[], time_per_vcpu=[])

            analysis[info["instance_type"]]["total_hours"].append(info["total_time"])
            analysis[info["instance_type"]]["total_cost"].append(info["total_cost"])
            analysis[info["instance_type"]]["cost_per_vcpu"].append(info["cost_per_vcpu"])
            analysis[info["instance_type"]]["time_per_vcpu"].append(info["time_per_vcpu"])

    for instance_type, info in analysis.items():
        info["avg_total_hours"] = sum(info["total_hours"]) / len(info["total_hours"])
        info["avg_total_cost"] = sum(info["total_cost"]) / len(info["total_cost"])
        info["avg_cost_per_vcpu"] = sum(info["cost_per_vcpu"]) / len(info["cost_per_vcpu"])
        info["avg_time_per_vcpu"] = sum(info["time_per_vcpu"]) / len(info["time_per_vcpu"])
        info["avg_cost_per_hour_per_vcpu"] = info["avg_cost_per_vcpu"] / info["avg_time_per_vcpu"]

        del info["total_hours"]
        del info["total_cost"]
        del info["cost_per_vcpu"]
        del info["time_per_vcpu"]

    return data


def output_data(data, file="summary.txt", delimiter="\t"):
    "outputs aggregated data from log files to delimited text file"
    header = delimiter.join(["Start", "Run ID", "Instance Type", "# Instances", "Total VCPUS",
                             "Total Time (hr)", "Time / VCPU (hr)", "Total Cost ($)", "Cost / VCPU ($)",
                             "Data Size (KB)"])
    output = []
    for instance, info in data.items():
        output.append(delimiter.join([f"{info['start'].format('YYYY-MM-DD HH:mm:ss')}", f"{instance}", f"{info['instance_type']}",
                                      f"{info['instances']}", f"{info['vcpus']}", f"{info['total_time']:.2f}", f"{info['time_per_vcpu']:.2f}",
                                      f"{info['total_cost']:.2f}", f"{info['cost_per_vcpu']:.4f}", f"{info['data_size']:.2f}"]))

    output.sort()

    output = "\n".join([header] + output)

    with open(file, "w") as f:
        f.write(output)


def output_analysis(analysis, file="analysis.txt", delimiter="\t"):
    "outputs analysed data from log files to delimited text file"
    analysis_header = delimiter.join(["Instance Type", "Average Total Hours (hrs)",
                                      "Average Hours per VCPU (hrs)", "Average Total Cost ($)",
                                      "Average Cost per VCPU ($)", "Avgerage Cost / Hr per VCPU"])

    analysis_out = []
    for instance_type, info in analysis.items():
        analysis_out.append(delimiter.join([f"{instance_type}", f"{info['avg_total_hours']:.2f}", f"{info['avg_time_per_vcpu']:.2f}",
                                            f"{info['avg_total_cost']:.2f}", f"{info['avg_cost_per_vcpu']:.2f}",
                                            f"{info['avg_cost_per_hour_per_vcpu']:.2f}"]))

    analysis_out.sort()
    analysis_out = "\n".join([analysis_header] + analysis_out)

    with open(file, "w") as f:
        f.write(analysis_out)
