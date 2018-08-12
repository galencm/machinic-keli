# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import gphoto2 as gp
import datetime
import io
import uuid
import redis
import time
import subprocess
from ma_cli import data_models

# chdkptp needs to be installed/linked in a callable path
# to set settings

class SlurpGphoto2(object):
    def __init__(self, db_host=None, db_port=None, binary_r=None, redis_conn=None):
        if binary_r and redis_conn:
             self.binary_r = binary_r
             self.redis_conn = redis_conn
        else:
            if not db_host and not db_port:
                db_host, db_port =  data_models.service_connection()

            self.redis_conn = redis.StrictRedis(host=db_host, port=str(db_port),decode_responses=True)
            self.binary_r = redis.StrictRedis(host=db_host, port=str(db_port))

    def discover(self):
        method = "gphoto2"
        discoverable = []
        context = gp.Context()
        try:
            for name, addr in context.camera_autodetect():
                now = str(datetime.datetime.now())
                c = gp.Context()
                camera = gp.Camera()
                camera.init(c)
                camera_summary = camera.get_summary(c)
                serial =""
                for t in str(camera_summary).split("\n"):
                    if ("Serial Number:") in t:
                        serial = t.partition(":")[-1].strip()
                        # print(serial)
                        break
                camera.exit(c)
                discoverable.append({'name':name,'address':addr,'uid':serial, 'discovery': method,'lastseen':now})

        except Exception as ex:
            print(ex)
        return discoverable

    def slurp(self, device=None, container="glworb"):
        if device == '_':
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
            if 'file' in container:
                fname = "/tmp/{}.slurp".format(time.time())
                with open(fname,'wb+') as f:
                    f.write(slurped_bytes)
                slurped.append(fname)

            if 'blob' in container:
                slurped.append(slurped_bytes)

            if 'glworb' in container:
                blob_uuid = str(uuid.uuid4())
                blob_uuid = "binary:"+blob_uuid
                self.binary_r.set(blob_uuid, slurped_bytes)

                glworb = {}
                glworb['uuid'] = str(uuid.uuid4())
                glworb['slurp_source_uid'] = device['uid']
                glworb['slurp_method'] = "slurp_gphoto2"
                glworb['slurp_source_name'] =  device['name']
                glworb['binary_key'] = blob_uuid
                glworb['created'] = str(datetime.datetime.now())
                glworb_uuid = "glworb:{}".format(glworb['uuid'])
                self.redis_conn.hmset(glworb_uuid, glworb)
                slurped.append(glworb_uuid)

        return slurped

    def set_setting(self, device, setting, setting_value, dry_run=False):
        # device may have a 'scripts' field:
        #     'scripts' : 'chdkptp:propset_1'
        #                  ( chdkptp:propset_1 or chdkptp:propset:1? )
        #
        # lookup table somewhere? device:script_lookup
        #     Canon PowerShot G7 : chdkptp:propset_1
        #
        # a scripts hash of attribute and raw_string to be formatted with attribute
        #     scripts:chdkptp:propset_1   zoom: -eluar set_zoom({zoom})
        #                                 focus: -eluar set_focus({focus})
        # build lookup table and script hashes from an xml file using
        # a tool/xml files packaged with enn-ui: (a device gui and env setting gui)
        #
        # could also be embedded in device hash
        #
        # chdkptp note:
        # do not set record mode if shooting with gphoto2

        if not "scripts" in device:
            device["scripts"] = self.redis_conn.hget("device:script_lookup", device["name"])

        setting_call = self.redis_conn.hget("scripts:"+device["scripts"], setting).format_map({setting : setting_value})
        print(setting_call)

        if dry_run is True:
            print(setting_call)
        else:
            print(subprocess.check_output(['chdkptp',
                                     '-c"-s={uid}"'.format_map(device),
                                     setting_call
                                    ]))

    def set_raw(self, device, raw_string):
        # no formatting or lookups
        subprocess.check_output(['chdkptp',
                                 '-c"-s={uid}"'.format_map(device),
                                 raw_string
                                ])

    def slurpd(self, device):
        contents = b''
        try:
            context = gp.gp_context_new()
            camera = gp.Camera()

            cameras = gp.PortInfoList()
            cameras.load()
            camera_address = cameras.lookup_path(device['address'])
            camera.set_port_info(cameras[camera_address])
            gp.check_result(gp.gp_camera_init(camera, context))

            captured = gp.check_result(gp.gp_camera_capture(
                                                camera,
                                                gp.GP_CAPTURE_IMAGE,
                                                context))

            captured_file = gp.check_result(gp.gp_camera_file_get(
                                                camera,
                                                captured.folder,
                                                captured.name,
                                                gp.GP_FILE_TYPE_NORMAL,
                                                context))

            captured_file_data = gp.check_result(gp.gp_file_get_data_and_size(captured_file))
            container = io.BytesIO(memoryview(captured_file_data))
            container.seek(0)
            contents = container.read()

            gp.check_result(gp.gp_camera_exit(camera, context))
       
        except Exception as ex:
            print(ex)

        return contents
