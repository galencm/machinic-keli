# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import redis
import pathlib
import os
import fnmatch
import importlib
import importlib.util
import inspect
from ma_cli import data_models
import fold_ui.keyling as keyling


class keli_neo(object):
    def __init__(self, db_host=None, db_port=None):
        self.db_host = db_host
        self.db_port = db_port
        if db_port is None:
            r_ip, r_port = data_models.service_connection()
        else:
            r_ip, r_port = db_host, db_port

        self.binary_r = redis.StrictRedis(host=r_ip, port=r_port)
        self.redis_conn = redis.StrictRedis(
            host=r_ip, port=r_port, decode_responses=True
        )

        # discover slurp_* files and load Slurp* classes
        self.slurp_classes = {}
        self.slurp_default_class = "gphoto2"
        package_path = pathlib.Path(pathlib.Path(__file__).parents[0])
        if package_path.is_dir():
            slurp_files = list(
                x for x in package_path.iterdir() if x.is_file() and "slurp_" in str(x)
            )
        for file in slurp_files:
            # load modules using full path
            spec = importlib.util.spec_from_file_location(pathlib.Path(file).stem, file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            clsmembers = inspect.getmembers(module, inspect.isclass)
            # create a dictionary of names that will be callable with
            # the --slurp-method parameter
            #
            # ('SlurpGphoto2', <class 'slurp_gphoto2.SlurpGphoto2'>)
            # will be used as
            # {"gphoto2" : <class 'slurp_gphoto2.SlurpGphoto2'>}
            #
            self.slurp_classes.update(
                {
                    key.lower()[5:]: value
                    for (key, value) in clsmembers
                    if key.startswith("Slurp")
                }
            )
        # set a default if --slurp-method is not used
        self.slurp_classes["default"] = self.slurp_classes[self.slurp_default_class]

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

    def neo_slurpif(self, context, **kwargs):
        # use context["uuid"] for device uid using pattern matching
        # for example "*" will match all devices
        # this is  messy since it expects keli_cli parsing behavior
        slurp_class = self.slurp_classes["default"]
        if "slurp_method" in kwargs:
            try:
                slurp_class = self.slurp_classes[kwargs["slurp_method"]]
            except KeyError as ex:
                print(ex)
        slurp_thing = slurp_class(binary_r=self.binary_r, redis_conn=self.redis_conn)

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
            pre_conditions = list(
                self.redis_conn.scan_iter(
                    match="settings:pre:*:{}:{}:{}".format(
                        device["uid"], self.db_host, self.db_port
                    )
                )
            )
            for c in pre_conditions:
                conditions = self.redis_conn.lrange(c, 0, -1)
                all_satisfied = []
                for condition in conditions:
                    model = keyling.model(condition)
                    satisfied = keyling.parse_lines(
                        model, env_vars, env_var_key, allow_shell_calls=True
                    )
                    if not satisfied:
                        print("not satisfied {}:".format(condition))
                    all_satisfied.append(satisfied)
                # A None means a condition / keyling script was not satisfied
                # and did not return a dictionary
                if None not in all_satisfied:
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
                    post_conditions = self.redis_conn.lrange(
                        c.replace("pre", "post"), 0, -1
                    )

                    # get hashes and feed them into post_conditions keyling scripts
                    for s in slurped:
                        s_dict = self.redis_conn.hgetall(s)
                        for post_condition in post_conditions:
                            postmodel = keyling.model(post_condition)
                            keyling.parse_lines(
                                postmodel, s_dict, s, allow_shell_calls=True
                            )

    def neo_slurpst(self, context, state_template=None, **kwargs):
        # slurpstate
        # use context["uuid"] for device uid using pattern matching
        # for example "*" will match all devices
        # this is  messy since it expects keli_cli parsing behavior
        slurp_class = self.slurp_classes["default"]
        if "slurp_method" in kwargs:
            try:
                slurp_class = self.slurp_classes[kwargs["slurp_method"]]
            except KeyError as ex:
                print(ex)
        slurp_thing = slurp_class(binary_r=self.binary_r, redis_conn=self.redis_conn)

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

    def neo_slurp(self, context, **kwargs):
        slurp_class = self.slurp_classes["default"]
        if "slurp_method" in kwargs:
            try:
                slurp_class = self.slurp_classes[kwargs["slurp_method"]]
            except KeyError as ex:
                print(ex)
        slurp_thing = slurp_class(binary_r=self.binary_r, redis_conn=self.redis_conn)
        print("\n".join(slurp_thing.slurp()))

    def neo_discover(self, context, **kwargs):
        slurp_class = self.slurp_classes["default"]
        if "slurp_method" in kwargs:
            try:
                slurp_class = self.slurp_classes[kwargs["slurp_method"]]
            except KeyError as ex:
                print(ex)

        slurp_thing = slurp_class(binary_r=self.binary_r, redis_conn=self.redis_conn)
        print(slurp_thing.discover())

    def neo_discovery(self, context, **kwargs):
        # runs discover on all slurp classes
        for name, slurp_class in self.slurp_classes.items():
            print("{}:".format(name))
            slurp_thing = slurp_class(
                binary_r=self.binary_r, redis_conn=self.redis_conn
            )
            print(slurp_thing.discover())
