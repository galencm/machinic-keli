# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import datetime
import io
import uuid
import redis
import sys
import time
import subprocess
import fnmatch
import glob
from ma_cli import data_models


class SlurpWebCam(object):
    def __init__(self, db_host=None, db_port=None, binary_r=None, redis_conn=None):
        if binary_r and redis_conn:
            self.binary_r = binary_r
            self.redis_conn = redis_conn
        else:
            if not db_host and not db_port:
                db_host, db_port = data_models.service_connection()

            self.redis_conn = redis.StrictRedis(
                host=db_host, port=str(db_port), decode_responses=True
            )
            self.binary_r = redis.StrictRedis(host=db_host, port=str(db_port))

    def set_setting(self, device, attribute, value, value_flag=None):

        set_values = []

        if device == "_":
            device = None

        if device is None:
            devices = self.discover()
        else:
            devices = [{"uid": device}]

        for dev in devices:
            # allow wildcards in attribute
            # get attributes for device
            # run set on any that match
            # fnmatch.fnmatch

            attributes = self.get_setting(dev["uid"])[0]
            for k, v in attributes.items():
                if fnmatch.fnmatch(k, attribute):
                    # simple inc / dec, assumes int
                    if value_flag == "+" or value_flag == "add":
                        current = self.get_setting(dev["uid"], k)[0]
                        print(current, value)
                        if current:
                            value = int(value)
                            current = int(current)
                            current += value
                    elif value_flag == "-" or value_flag == "sub":
                        current = self.get_setting(dev["uid"], k)[0]
                        if current:
                            value = int(value)
                            current = int(current)
                            current -= value
                    else:
                        current = value

                    self.redis_conn.hmset("state:{}".format(dev["uid"]), {k: current})
                    set_values.append(self.get(device, k))

        return set_values

    def get_setting(self, device, attribute=None):

        get_values = []

        if device == "_":
            device = None

        if device is None:
            devices = self.discover()
        else:
            devices = [{"uid": device}]

        for dev in devices:
            if attribute:
                get_values.append(
                    self.redis_conn.hget("state:{}".format(dev["uid"]), attribute)
                )
            else:
                get_values.append(
                    self.redis_conn.hgetall("state:{}".format(dev["uid"]))
                )
        return get_values

    def discover(self):

        method = "webcam"
        discoverable = []
        try:
            now = str(datetime.datetime.now())
            for webcam in glob.glob("/dev/video*"):
                discoverable.append(
                    {
                        "name": webcam,
                        "address": webcam,
                        "uid": webcam,
                        "discovery": method,
                        "lastseen": now,
                    }
                )
        except Exception as ex:
            print(ex)

        return discoverable

    def slurp(self, device=None, container="glworb"):

        if device == "_":
            device = None

        if device is None:
            devices = self.discover()
        else:
            devices = [device]

        slurped = []

        for device in devices:
            slurped_bytes = self.slurpd(device)

            # check using 'in' to allow combinations
            # for example: file+glworb
            if "file" in container:
                fname = "/tmp/{}.slurp".format(time.time())
                with open(fname, "wb+") as f:
                    f.write(slurped_bytes)
                slurped.append(fname)

            if "blob" in container:
                slurped.append(slurped_bytes)

            if "glworb" in container:
                blob_uuid = str(uuid.uuid4())
                blob_uuid = "binary:" + blob_uuid
                self.binary_r.set(blob_uuid, slurped_bytes)

                glworb = {}
                glworb["uuid"] = str(uuid.uuid4())
                glworb["slurp_source_uid"] = device["uid"]
                glworb["slurp_method"] = "slurp_webcam"
                glworb["slurp_source_name"] = device["name"]
                glworb["binary_key"] = blob_uuid
                glworb["created"] = str(datetime.datetime.now())

                glworb_uuid = "glworb:{}".format(glworb["uuid"])
                self.redis_conn.hmset(glworb_uuid, glworb)

                slurped.append(glworb_uuid)

        return slurped

    def slurpd(self, device):

        try:
            tmp_output_filename = "/tmp/slurp_webcam.jpg"
            print(device)
            # name = device["name"]
            addr = device["address"]
            subprocess.call(
                [
                    "fswebcam",
                    "--no-banner",
                    "--save",
                    tmp_output_filename,
                    "-d",
                    addr,
                    "-r",
                    "1280x960",
                ]
            )
            contents = io.BytesIO()

            with open(tmp_output_filename, "rb") as f:
                contents = io.BytesIO(f.read())

            contents = contents.getvalue()

        except Exception as ex:
            print(ex)

        return contents
