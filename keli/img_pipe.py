# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import redis
import io
import uuid
from contextlib import contextmanager
from PIL import Image, ImageDraw, ImageFont
from tesserocr import PyTessBaseAPI, PSM, image_to_text, OEM, RIL
from logzero import logger
from lings.routeling import route_broadcast

from ma_cli import data_models


@contextmanager
def open_image(uuid, key, redis_conn, binary_r):
    key_bytes = None
    bytes_key = redis_conn.hget(uuid, key)
    key_bytes = binary_r.get(bytes_key)
    file = io.BytesIO()
    file.write(key_bytes)
    image = Image.open(file)
    yield image
    file = io.BytesIO()
    image.save(file, image.format)
    image.close()
    file.seek(0)
    binary_r.set(bytes_key, file.read())
    file.close()


@contextmanager
def open_bytes(uuid, key, redis_conn, binary_r):
    key_bytes = None
    bytes_key = redis_conn.hget(uuid, key)
    key_bytes = binary_r.get(bytes_key)
    file = io.BytesIO()
    file.write(key_bytes)
    yield file
    file.seek(0)
    binary_r.set(bytes_key, file.read())
    file.close()


def write_bytes(
    hash_uuid, key, write_bytes, key_prefix="", redis_conn=None, binary_r=None
):
    bytes_key_uuid = str(uuid.uuid4())
    bytes_key = "{}{}".format(key_prefix, bytes_key_uuid)
    binary_r.set(bytes_key, write_bytes)
    redis_conn.hset(hash_uuid, key, bytes_key)


class keli_img(object):
    def __init__(self, db_host=None, db_port=None):
        if db_port is None:
            r_ip, r_port = data_models.service_connection()
        else:
            r_ip, r_port = db_host, db_port

        self.binary_r = redis.StrictRedis(host=r_ip, port=r_port)
        self.redis_conn = redis.StrictRedis(
            host=r_ip, port=r_port, decode_responses=True
        )

    # @route_broadcast(channel='{function}',message='context')
    def img_show(self, context, *args):
        """Display image

            Args:
                context(dict): dictionary of context info
                *args:

            Returns:
                dict
        """
        with open_image(
            context["uuid"], context["key"], self.redis_conn, self.binary_r
        ) as img:
            img.show()
        return context

    def img_overlay(self, context, text, x, y, fontsize, *args):
        """Overlay text

            Args:
                context(dict): dictionary of context info
                text(string): text to overlay
                x(int): x position of text
                y(int): y position of text
                *args:

            Returns:
                dict
        """
        text = str(text)

        with open_image(
            context["uuid"], context["key"], self.redis_conn, self.binary_r
        ) as img:
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("FreeSerif.ttf", fontsize)
                draw.text((x, y), text, (255, 255, 255), font=font)
            except Exception as ex:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf", fontsize
                )
                draw.text((x, y), text, (255, 255, 255), font=font)

        return context

    def img_rotate(self, context, rotation, *args):
        """Rotate in place

            Args:
                context(dict): dictionary of context info
                rotation(float): degrees of rotation
                *args:

            Returns:
                dict
        """

        # use open_bytes instead of open_image
        # because yielded image does not seem
        # to be mutated despite img = img.rotate

        with open_bytes(
            context["uuid"], context["key"], self.redis_conn, self.binary_r
        ) as img:
            image = Image.open(img)
            ext = image.format
            image = image.rotate(float(rotation), expand=True)
            img.seek(0)
            image.save(img, ext)

        # with open_image(context['uuid'],context['key']) as img:
        #     img = img.rotate(float(rotation),expand=True)

        return context

    def img_grid(
        self,
        context,
        xspacing=100,
        yspacing=100,
        r=255,
        g=255,
        b=255,
        a=127,
        label=True,
        *args,
        **kwargs
    ):
        """Grid over image

            Args:
                context(dict): dictionary of context info
                xspacing(int): column spacing
                yspacing(float): row spacing
                r(int): red
                g(int): green
                b(int): blue
                a(int): alpha
                label(str): label grid squares and intersections

                *args:
                **kwargs:
            Returns:
                dict
        """
        xspacing = int(xspacing)
        yspacing = int(yspacing)
        r = int(r)
        g = int(g)
        b = int(b)
        a = int(a)

        with open_image(
            context["uuid"], context["key"], self.redis_conn, self.binary_r
        ) as img:
            draw = ImageDraw.Draw(img)
            imgw, imgh = img.size

            for col in range(0, imgw, xspacing):
                draw.line((col, 0, col, imgh), fill=(r, g, b))

            for row in range(0, imgh, yspacing):
                draw.line((0, row, imgw, row), fill=(r, g, b))

            if label:
                grid_number = 0
                for col in range(0, imgw, xspacing):
                    for row in range(0, imgh, yspacing):
                        draw.text(
                            (col, row),
                            str("({}, {})".format(col, row)),
                            (255, 255, 255),
                        )
                        grid_label = str("{}".format(grid_number))
                        w, h = draw.textsize(grid_label)
                        tx = int(round(col + (xspacing / 2) - (w / 2)))
                        ty = int(round(row + (yspacing / 2) - (h / 2)))
                        draw.text((tx, ty), grid_label, (255, 255, 255))
                        grid_number += 1
        return context

    def img_crop_inplace(self, context, x1, y1, width, height, *args):
        """Crop in place

            Args:
                context(dict): dictionary of context info
                x1(float): starting x coordinate
                y1(float): starting y coordinate
                w(float): width
                h(float): height
                *args:

            Returns:
                dict
        """
        # left upper right lower
        x1 = float(x1)
        y1 = float(y1)
        width = float(width)
        height = float(height)

        with open_image(
            context["uuid"], context["key"], self.redis_conn, self.binary_r
        ) as img:
            if "scale" in args:
                width_size, height_size = img.size
                x1 *= width_size
                y1 *= height_size
                width *= width_size
                height *= height_size
            box = (x1, y1, x1 + width, y1 + height)
            img = img.crop(box)

        return context

    def img_crop_to_key(self, context, x1, y1, width, height, to_key, *args):
        """Crop selection from context to new key

            Args:
                context(dict): dictionary of context info
                x1(float): starting x coordinate
                y1(float):  starting y coordinate
                w(float): width
                h(float): height
                to_key: key to store crop
                *args:

            Returns:
                dict:
        """
        if "binary_prefix" not in context:
            context["binary_prefix"] = "binary:"

        x1 = float(x1)
        y1 = float(y1)
        width = float(width)
        height = float(height)

        with open_image(
            context["uuid"], context["key"], self.redis_conn, self.binary_r
        ) as img:
            if "scale" in args:
                width_size, height_size = img.size
                x1 *= width_size
                y1 *= height_size
                width *= width_size
                height *= height_size
            box = (x1, y1, x1 + width, y1 + height)
            region = img.crop(box)
            filelike = io.BytesIO()
            region.save(filelike, img.format)
            filelike.seek(0)
            write_bytes(
                context["uuid"],
                to_key,
                filelike.read(),
                key_prefix=context["binary_prefix"],
                redis_conn=self.redis_conn,
                binary_r=self.binary_r,
            )
            filelike.close()

        return context

    def img_orientation(self, context, *args):
        """Calculate text orientation using tesseract

            Args:
                context(dict): dictionary of context info
                *args:

            Returns:
                dict
        """
        with PyTessBaseAPI(psm=PSM.AUTO_OSD) as api:
            with open_image(
                context["uuid"], context["key"], self.redis_conn, self.binary_r
            ) as img:
                api.SetImage(img)
                api.Recognize()
                it = api.AnalyseLayout()
                orientation, direction, order, deskew_angle = it.Orientation()
                logger.info("Orientation: {:d}".format(orientation))
                logger.info("WritingDirection: {:d}".format(direction))
                logger.info("TextlineOrder: {:d}".format(order))
                logger.info("Deskew angle: {:.4f}".format(deskew_angle))

        # LSTM_ONLY needs 4.0
        # https://github.com/tesseract-ocr/tesseract/wiki/4.0-with-LSTM
        return context

    def img_ocr_fan_in(self, context, to_key, write_empty=False, *args):
        # For multiple ocr regions written to a single key
        # write: if ocr result is empty and to_key does not exist
        # do not write: if ocr result is empty and key exists
        psm = 6
        with open_image(
            context["uuid"], context["key"], self.redis_conn, self.binary_r
        ) as img:
            logger.info(image_to_text(img, psm=psm))
            # r redis conn basically global
            ocr_result = image_to_text(img, psm=psm).strip()
            print(self.redis_conn.hget(context["uuid"], to_key))
            if (
                not ocr_result
                and not write_empty
                and self.redis_conn.hget(context["uuid"], to_key) is not None
            ):
                print("passing")
                pass
            else:
                self.redis_conn.hset(context["uuid"], to_key, ocr_result)
        return context

    def img_ocr(self, context, to_key, *args):
        """Optical Character Recognition(OCR) using tesseract

            Args:
                context(dict): dictionary of context info
                to_key(str): key to store ocr results
                *args:

            Returns:
                dict
        """
        # set PSM (Page Segmentation Mode) to 6 to handle
        # images containing only numerals
        psm = 6
        with open_image(
            context["uuid"], context["key"], self.redis_conn, self.binary_r
        ) as img:
            logger.info(image_to_text(img, psm=psm))
            # r redis conn basically global
            self.redis_conn.hset(
                context["uuid"], to_key, image_to_text(img, psm=psm).strip()
            )
        return context

    def img_ocr_key(self, context, key, to_key, *args):
        """Optical Character Recognition(OCR) using tesseract

            Args:
                context(dict): dictionary of context info
                key: key to use to ocr
                to_key(str): key to store ocr results
                *args:

            Returns:
                dict
        """
        # set PSM (Page Segmentation Mode) to 6 to handle
        # images containing only numerals
        psm = 6
        with open_image(context["uuid"], key, self.redis_conn, self.binary_r) as img:
            logger.info(image_to_text(img, psm=psm))
            # r redis conn basically global
            # set PSM (Page Segmentation Mode) to 6 to handle
            # images containing only numerals
            self.redis_conn.hset(
                context["uuid"], to_key, image_to_text(img, psm=psm).strip()
            )
        return context

    def img_ocr_rectangle(self, context, to_key, left, top, width, height, *args):
        with PyTessBaseAPI() as api:
            with open_image(
                context["uuid"], context["key"], self.redis_conn, self.binary_r
            ) as img:
                api.SetImage(img)
                api.SetRectangle(left, top, width, height)
                result = api.GetUTF8Text()
                logger.info(result)
                self.redis_conn.hset(context["uuid"], to_key, result)
                logger.info(
                    "setting {} field {} to {}".format(context["uuid"], to_key, result)
                )
                # store rectangle information in separate
                # key to allow reconstruction of geometry
                # of the ocr region
                ocr_info_key = "region_ocr-rectangle_{key}".format(key=to_key)
                ocr_geometry = ",".join([str(s) for s in [left, top, width, height]])
                self.redis_conn.hset(context["uuid"], ocr_info_key, ocr_geometry)
                logger.info(
                    "setting {} field {} to {}".format(
                        context["uuid"], ocr_info_key, ocr_geometry
                    )
                )

    def img_ocr_boxes(self, context, to_key, *args):
        with PyTessBaseAPI() as api:
            with open_image(
                context["uuid"], context["key"], self.redis_conn, self.binary_r
            ) as img:
                api.SetImage(img)
                boxes = api.GetComponentImages(RIL.TEXTLINE, True)
                for i, (im, box, _, _) in enumerate(boxes):
                    api.SetRectangle(box["x"], box["y"], box["w"], box["h"])
                    ocrResult = api.GetUTF8Text()
                    conf = api.MeanTextConf()
                    logger.info(
                        "Box[{0}]: x={x}, y={y}, w={w}, h={h}, confidence: {1}, text: {2}".format(
                            i, conf, ocrResult, **box
                        )
                    )
        return context
