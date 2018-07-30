# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import argparse
import inspect
import keli.img_pipe
import keli.src_pipe

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="command")
    parser.add_argument("key", nargs="?", default=None, help="db key")
    parser.add_argument("field", nargs="?", default=None, help="key field")
    parser.add_argument("--db-host",  default="127.0.0.1", help="db host ip")
    parser.add_argument("--db-port", default=None, help="db port")
    parser.add_argument("--verbose", action="store_true", help="")
    args, unknown_args = parser.parse_known_args()
    args = vars(args)

    # unkown args assumed to be list of --key value pairs that will be
    # passed as kwargs to function
    unknown_args = dict(zip(unknown_args[:-1:2], unknown_args[1::2]))
    unknown_args = {k.replace("--","").replace("-","_") :v for k, v in unknown_args.items()}
    # try to convert values to int
    for k, v in unknown_args.items():
        try:
            unknown_args[k] = int(v)
        except:
            pass

    if args["command"] == "list":
        # list available commands
        for c in [keli.img_pipe.keli_img, keli.src_pipe.keli_src]:
            for method in [method[0] for method in inspect.getmembers(c(), predicate=inspect.ismethod) if not method[0].startswith("__")]:
                print(method.replace("_", "-"))
                #print(inspect.getargspec(getattr(img_pipe.keli_img, method)))
    elif args["key"] is None and args["field"] is None:
        # show command signature
        for c in [keli.img_pipe.keli_img, keli.src_pipe.keli_src]:
            print(inspect.getargspec(getattr(c, args["command"].replace("-", "_"))))
    else:
        # run command
        for c in [keli.img_pipe.keli_img, keli.src_pipe.keli_src]:
            try:
                getattr(c(db_host=args["db_host"], db_port=args["db_port"]), args["command"].replace("-", "_"))({"uuid" : args["key"], "key" : args["field"]}, **unknown_args)
            except AttributeError:
                pass
if __name__ == "__main__":
    main()
