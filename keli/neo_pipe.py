# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import redis
import pathlib
import os
from ma_cli import data_models

class keli_neo(object):

    def __init__(self, db_host=None, db_port=None):
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