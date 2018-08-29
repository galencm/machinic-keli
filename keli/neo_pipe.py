# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import redis
import pathlib
import os
import fnmatch
from ma_cli import data_models
import fold_ui.keyling as keyling

# slurp_gphoto2 is an edited version from machinic-image
# machinic-image also has slurp_webcam and slurp_primitve_generic
# may make sense to move slurp to a separate package / cli
# use a more flexible approach to loading slurp_ prefixed files
# to allo neo_slurpif and neo_slurp a wider range of discovery / slurping
import keli.slurp_gphoto2 as sg

class keli_neo(object):

    def __init__(self, db_host=None, db_port=None):
        self.db_host = db_host
        self.db_port = db_port
        if db_port is None:
            r_ip, r_port = data_models.service_connection()
        else:
            r_ip, r_port = db_host, db_port

        self.binary_r = redis.StrictRedis(host=r_ip, port=r_port)
        self.redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)

    def neo_prune(self, context):
        #  context["uuid"] is a pattern glworb:*
        # context["key"] is a pattern binary:*
        
        hashes = list(self.redis_conn.scan_iter(match=context["uuid"]))
        is_referenced = set(list(self.redis_conn.scan_iter(match=context["key"])))

        for h in hashes:
            contents = self.redis_conn.hgetall(h)
            for k, v in contents.items():
                if v in is_referenced:
                    is_referenced.remove(v)

        for not_referenced in is_referenced:
            self.redis_conn.delete(not_referenced)

    def neo_slurpif(self, context):
        # use context["uuid"] for device uid using pattern matching
        # for example "*" will match all devices
        # this is  messy since it expects keli_cli parsing behavior
        slurp_thing = sg.SlurpGphoto2(binary_r=self.binary_r, redis_conn=self.redis_conn)
        env_var_key = "machinic:env:{}:{}".format(self.db_host, self.db_port)
        env_vars = self.redis_conn.hgetall(env_var_key)
        print("env vars:", env_vars)
        # conditional keys example

        # to make device-specific add device into key names
        # and slurp all devices if a name is not present
        # example:
        # settings:pre:<name>:<device?>:<host>:<port>

        # keys:
        # settings:pre:foo:127.0.0.1:6379 #list of keyling scripts
        # settings:set:foo:127.0.0.1:6379 #hash of key:values to set
        # settings:post:foo:127.0.0.1:6379 #list of keyling scripts
        found_devices = slurp_thing.discover()
        devices = []
        print("found devices", found_devices)
        # use underscore to match all
        if context["uuid"] == "_":
            context["uuid"] = "*"
        # lookup and get device dict to pass to slurp
        for d in found_devices:
            if fnmatch.fnmatch(d["uid"], context["uuid"]):
                devices.append(d)

        print("using devices:", devices)
        for device in devices:
            pre_conditions = list(self.redis_conn.scan_iter(match="settings:pre:*:{}:{}:{}".format(device["uid"], self.db_host, self.db_port)))
            for c in pre_conditions:
                conditions = self.redis_conn.lrange(c, 0, -1)
                all_satisfied = []
                for condition in conditions:
                    model = keyling.model(condition)
                    satisfied = keyling.parse_lines(model, env_vars, env_var_key, allow_shell_calls=True)
                    if not satisfied:
                        print("not satisfied {}:".format(condition))
                    all_satisfied.append(satisfied)
                # A None means a condition / keyling script was not satisfied
                # and did not return a dictionary
                if not None in all_satisfied:
                    print(all_satisfied)

                    # settings could be a list of raw strings or a dictionary
                    # or use a raw_ prefix on key to specify raw string to use set_raw()
                    # settings = self.redis_conn.lrange(c.replace("pre", "set"), 0, -1)
                    settings = self.redis_conn.hgetall(c.replace("pre", "set"))
                    devices = slurp_thing.discover()
                    # set settings
                    for setting, setting_value in settings.items():
                        print(device, setting)
                        slurp_thing.set_setting(device, setting, setting_value)

                    # slurp returns a list of keys for hashes
                    # for now this only calls slurp, but it may be useful
                    # to make other calls such as adjusting servos for device positioning
                    # or that could be done using shell calls at the tail of the preconditions
                    slurped = slurp_thing.slurp()
                    print(slurped)
                    post_conditions = self.redis_conn.lrange(c.replace("pre", "post"), 0, -1)

                    # get hashes and feed them into post_conditions keyling scripts
                    for s in slurped:
                        s_dict = self.redis_conn.hgetall(s)
                        for post_condition in post_conditions:
                            postmodel = keyling.model(post_condition)
                            s_result = keyling.parse_lines(postmodel, s_dict, s, allow_shell_calls=True)

    def neo_slurpst(self, context, state_template=None):
        # slurpstate
        # use context["uuid"] for device uid using pattern matching
        # for example "*" will match all devices
        # this is  messy since it expects keli_cli parsing behavior
        slurp_thing = sg.SlurpGphoto2(binary_r=self.binary_r, redis_conn=self.redis_conn)

        found_devices = slurp_thing.discover()
        devices = []
        # lookup and get device dict to pass to slurp
        for d in found_devices:
            if fnmatch.fnmatch(d["uid"], context["uuid"]):
                devices.append(d)

        for device in devices:
            if state_template is None:
                state_template = "device:state:{uid}"

            # get state settings
            state = self.redis_conn.hgetall(state_template.format_map(device))

            if state:
                settings = state
            else:
                settings = {}

            for setting, setting_value in settings.items():
                slurp_thing.set_setting(device, setting, setting_value)

            print("\n".join(slurp_thing.slurp()))

    def neo_slurp(self, context):
        s = sg.SlurpGphoto2(binary_r=self.binary_r, redis_conn=self.redis_conn)
        print("\n".join(s.slurp()))

    def neo_discover(self, context):
        s = sg.SlurpGphoto2(binary_r=self.binary_r, redis_conn=self.redis_conn)
        print(s.discover())
