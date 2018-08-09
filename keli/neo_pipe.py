# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import redis
import pathlib
import os
from ma_cli import data_models
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
        import fold_ui.keyling as keyling
        slurp_thing = sg.SlurpGphoto2(binary_r=self.binary_r, redis_conn=self.redis_conn)
        env_var_key = "machinic:env:{}:{}".format(self.db_host, self.db_port)
        env_vars = self.redis_conn.hgetall(env_var_key)
        # conditional keys example
        # settings:pre:foo:127.0.0.1:6379 #list of keyling scripts
        # settings:set:foo:127.0.0.1:6379 #hash of key:values to set
        # settings:post:foo:127.0.0.1:6379 #list of keyling scripts
        pre_conditions = list(self.redis_conn.scan_iter(match="settings:pre:*:{}:{}".format(self.db_host, self.db_port)))
        # devices are a list of dictionaries
        for c in pre_conditions:
            conditions = self.redis_conn.lrange(c, 0, -1)
            all_satisfied = []
            for condition in conditions:
                model = keyling.model(condition)
                satisfied = keyling.parse_lines(model, env_vars, env_var_key, allow_shell_calls=True)
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

                # for now same settings on all discovered devices
                # but addressing and setting devices conditionally should be possble
                for device in devices:
                    for setting, setting_value in settings.items():
                        print(device, setting)
                        slurp_thing.set(device, setting, setting_value)

                # slurp returns a list of keys for hashes
                slurped = slurp_thing.slurp()
                print(slurped)
                post_conditions = self.redis_conn.lrange(c.replace("pre", "post"), 0, -1)

                # get hashes and feed them into post_conditions keyling scripts
                for s in slurped:
                    s_dict = self.redis_conn.hgetall(s)
                    for post_condition in post_conditions:
                        postmodel = keyling.model(post_condition)
                        s_result = keyling.parse_lines(postmodel, s_dict, s, allow_shell_calls=True)

    def neo_slurp(self, context):
        s = sg.SlurpGphoto2(binary_r=self.binary_r, redis_conn=self.redis_conn)
        print("\n".join(s.slurp()))

    def neo_discover(self, context):
        s = sg.SlurpGphoto2(binary_r=self.binary_r, redis_conn=self.redis_conn)
        print(s.discover())
