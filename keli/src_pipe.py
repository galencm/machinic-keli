# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import redis
import pathlib
import os
from ma_cli import data_models
from lings import ruling


class keli_src(object):
    def __init__(self, db_host=None, db_port=None):
        if db_port is None:
            r_ip, r_port = data_models.service_connection()
        else:
            r_ip, r_port = db_host, db_port

        self.binary_r = redis.StrictRedis(host=r_ip, port=r_port)
        self.redis_conn = redis.StrictRedis(
            host=r_ip, port=r_port, decode_responses=True
        )

    def src_ruling_str(self, context, ruling_string, *args):
        db_item = self.redis_conn.hgetall(context["uuid"])
        rulings = ruling.rule_offline(ruling_string, glworb_dict=db_item)
        db_item.update(**rulings)
        self.redis_conn.hmset(context["uuid"], db_item)
        return context

    def src_artifact(self, context, filename, path="", *args):
        bytes_key = self.redis_conn.hget(context["uuid"], context["key"])
        artifact_bytes = self.binary_r.get(bytes_key)
        file_path = pathlib.Path(path, filename).expanduser().absolute()
        dir_path = pathlib.Path(path).expanduser().absolute()
        if not dir_path.is_dir():
            os.mkdir(dir_path)
        with open(file_path, "wb+") as file:
            file.write(artifact_bytes)

    def src_numerate_to_zero(
        self, context, structured_sequence, start_at=None, end_at=None, step=1, *args
    ):
        # accept either list or db key to list for structured_sequence
        # if start_at is None, try to use key/field value and decrement
        structured = self.redis_conn.lrange(structured_sequence, 0, -1)
        starting_position = structured.index(context["uuid"])
        if start_at is None:
            starting_value = int(self.redis_conn.hget(context["uuid"], context["key"]))
        else:
            starting_value = int(start_at)
        to_numerate = structured[
            starting_position - (starting_value) : starting_position
        ][::-1]
        for source_num, source in enumerate(to_numerate):
            # print(starting_value - source_num -1, self.redis_conn.hget(source, context["key"]))
            self.redis_conn.hset(
                source, context["key"], (starting_value - source_num - 1)
            )

    def src_numerate_to_one(
        self, context, structured_sequence, start_at=None, end_at=None, step=1, *args
    ):
        structured = self.redis_conn.lrange(structured_sequence, 0, -1)
        starting_position = structured.index(context["uuid"])
        if start_at is None:
            starting_value = int(self.redis_conn.hget(context["uuid"], context["key"]))
        else:
            starting_value = int(start_at)
        to_numerate = structured[
            starting_position - (starting_value - 1) : starting_position
        ][::-1]
        for source_num, source in enumerate(to_numerate):
            # print(starting_value - source_num -1, self.redis_conn.hget(source, context["key"]), source)
            self.redis_conn.hset(
                source, context["key"], (starting_value - source_num - 1)
            )

    def src_numerate_to(
        self, context, structured_sequence, start_at=None, end_at=None, step=1, *args
    ):
        # add 1 to be inclusive:
        if end_at >= 0:
            end_at += 1
        structured = self.redis_conn.lrange(structured_sequence, 0, -1)
        starting_position = structured.index(context["uuid"])
        if start_at is None:
            starting_value = int(self.redis_conn.hget(context["uuid"], context["key"]))
        else:
            starting_value = int(start_at)
        if end_at > starting_value:
            direction = 1
            to_numerate = structured[
                starting_position : starting_position + (end_at - starting_value)
            ]
        else:
            direction = -1
            if end_at < 0:
                end_at = abs(end_at)
            to_numerate = structured[starting_position - (end_at) : starting_position][
                ::-1
            ]
        for source_num, source in enumerate(to_numerate):
            if direction < 1:
                source_num += 1
            # print((starting_value + (source_num * direction)), self.redis_conn.hget(source, context["key"]), source)
            self.redis_conn.hset(
                source, context["key"], (starting_value + (source_num * direction))
            )
