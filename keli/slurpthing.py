# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import datetime
import io
import uuid
import redis
import time
import subprocess
from ma_cli import data_models

# chdkptp needs to be installed/linked in a callable path
# to set settings


class SlurpThing(object):
    def __init__(self, db_host=None, db_port=None, binary_r=None, redis_conn=None):
        self.slurp_method = None
        self.virtual_device_pattern = None
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

    def discover(self):
        # discovery method here
        discoverable = []
        # virtual keys for classes that set
        # self.virtual_device_pattern
        if self.virtual_device_pattern is not None:
            for discovered in self.redis_conn.scan_iter(
                match=self.virtual_device_pattern
            ):
                defaults = {
                    "name": "",
                    "address": "virtual",
                    "uid": "",
                    "discovery": self.slurp_method,
                    "lastseen": str(datetime.datetime.now()),
                }
                # only update with keys from defaults?
                # name and uid important
                defaults.update(self.redis_conn.hgetall(discovered))
                discoverable.append(defaults)
        return discoverable

    def slurp(self, device=None, container="glworb", metadata=None):
        if device == "_":
            device = None

        if device is None:
            devices = self.discover()
        else:
            devices = [device]

        if metadata is None:
            metadata = {}

        slurped = []
        print(devices)
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
                glworb["binary_key"] = blob_uuid
                glworb["created"] = str(datetime.datetime.now())
                glworb["slurp_method"] = self.slurp_method
                try:
                    glworb["slurp_source_uid"] = device["uid"]
                    glworb["slurp_source_name"] = device["name"]
                except:
                    pass
                for k, v in metadata.items():
                    glworb[k] = v
                glworb_uuid = "glworb:{}".format(glworb["uuid"])
                self.redis_conn.hmset(glworb_uuid, glworb)
                slurped.append(glworb_uuid)

        return slurped

    def set_setting(self, device, setting, setting_value, dry_run=False):
        if not "scripts" in device:
            device["scripts"] = self.redis_conn.hget(
                "device:script_lookup", device["name"]
            )

        setting_call = self.redis_conn.hget(
            "scripts:" + device["scripts"], setting
        ).format_map({setting: setting_value})
        print(setting_call)

        if dry_run is True:
            print(setting_call)
        else:
            print("setting {}".format(setting_call))

    def slurpd(self, device):
        # slurp bytes here
        contents = b""
        return contents

    def file_bytes(self, filename, delete_file=False):
        contents = io.BytesIO()

        with open(filename, "rb") as f:
            contents = io.BytesIO(f.read())

        contents = contents.getvalue()
        return contents
