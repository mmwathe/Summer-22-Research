from arena import *
import random

scene = Scene(host="arena.andrew.cmu.edu", realm="realm", scene="test", network_loop_interval=10)

def click(scene, evt, msg):
    if evt.type == "mousedown":
        print( "Click!" )
        start = evt.data.clickPos
        end = evt.data.position
        start.y=start.y-.1
        start.x=start.x-.1
        start.z=start.z-.1
        line = ThickLine(path=(start, end), color=(255, 0, 0), lineWidth=5, ttl=1)
        scene.add_object(line)
        ball = Sphere(
            position=end,
            scale = (0.05,0.05,0.05),
            material=Material(color=(255,0,0)),
            ttl=1)
        scene.add_object(ball)

@scene.run_once
def main():
    objs = scene.get_persisted_objs()
    for obj_id,obj in objs.items():
        obj.update_attributes(clickable=True)
        obj.update_attributes(evt_handler=click, scale=(1,1,1))
        scene.update_object(obj)

scene.run_tasks()