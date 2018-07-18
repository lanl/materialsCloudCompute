# -*- coding: utf-8 -*-
"""Initializes a logger"""
import logging
import os
import sys


class LoggerWriter(object):
    "Helper to log stdout/stderr to the log"
    def __init__(self, level):
        self.level = level

    def write(self, message):
        "Write message to log"
        if message != '\n':
            self.level(message)

    def flush(self):
        "flush stderr"
        self.level(sys.stderr)


def init_logging():
    """Creates a default logger"""
    logFormatter = logging.Formatter("[%(asctime)s] %(levelname)s::%(module)s::%(funcName)s() %(message)s")
    rootLogger = logging.getLogger()

    LOG_DIR = f"{os.path.expanduser('~')}/.mCC"
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    fileHandler = logging.FileHandler(f"{LOG_DIR}/materialsCloudCompute.log")
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)

    rootLogger.setLevel("INFO")

    return rootLogger


logger = init_logging()
