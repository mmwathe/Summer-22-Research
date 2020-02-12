# balls.py
#
# spray a bunch of spheres into the scene, test physics

import json
import random
import time

import paho.mqtt.publish as publish

HOST = "oz.andrew.cmu.edu"
TOPIC = "realm/s/balls"


def randrot():
    # return str("{0:0.3f}".format(random.random() * 2 - 1))
    return "0"


def randy():
    return str("{0:0.3f}".format(random.random() * 2 - 1))


def randcolor():
    return "%06x" % random.randint(0, 0xFFFFFF)


counter = 0
while True:
    obj_id = str(counter)
    name = "sphere" + "_" + obj_id
    counter += 1

    MESSAGE = {
        "object_id": name,
        "action": "create",
        "ttl": 40,
        "data": {
            "dynamic-body": {"type": "dynamic"},
            "object_type": "sphere",
            "position": {"x": randy(), "y": "{0:0.3f}".format(0), "z": randy(),},
            "rotation": {
                "x": randrot(),
                "y": randrot(),
                "z": randrot(),
                "w": randrot(),
            },
            "color": "#" + randcolor(),
        },
    }
    MESSAGE_string = json.dumps(MESSAGE)
    print(MESSAGE_string)

    publish.single(TOPIC + "/" + name, MESSAGE_string, hostname=HOST, retain=False)
    time.sleep(0.1)
