"""Headless gold preview render with Blender (Cycles).

blender -b -P render.py -- out.png [--tilt=58] metal.stl[+stone.stl] [metal2.stl[+stone2.stl] ...]
One item: shown from 3 angles side by side. Several items: one 3/4 view each.
"""
import math, sys
from pathlib import Path
import bpy

png, *items = sys.argv[sys.argv.index("--") + 1:]
tilt = float(items.pop(0).split("=")[1]) if items[0].startswith("--tilt=") else 58  # hero view tilt, degrees
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def material(name, color, metallic, roughness, transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = 2.42
    return m


gold, stone = material("gold", (1.0, 0.66, 0.22), 1.0, 0.14), material("stone", (1, 1, 1), 0.0, 0.0, 1.0)
hero = (math.radians(tilt), 0, math.radians(32))
views = [(hero, it) for it in items] if len(items) > 1 else \
    [(hero, items[0]), ((0, 0, 0), items[0]), ((math.radians(90), 0, 0), items[0])]  # 3/4, along finger, top

x, right, tall = 0.0, 0.0, 0.0
for rot, item in views:
    empty = bpy.data.objects.new("item", None)
    scene.collection.objects.link(empty)
    for f, mat in zip(item.split("+"), (gold, stone)):
        bpy.ops.wm.stl_import(filepath=f)
        o = bpy.context.selected_objects[0]
        o.data.materials.append(mat)
        bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        o.parent = empty
    empty.rotation_euler = rot
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ v.co for o in empty.children for v in o.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    empty.location = (x - lo[0], -(lo[1] + hi[1]) / 2, -(lo[2] + hi[2]) / 2)
    right, tall = x + hi[0] - lo[0], max(tall, hi[2] - lo[2])
    x += (hi[0] - lo[0]) * 1.15

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = "ORTHO"
cam.data.ortho_scale = max(right, tall) * 1.1
cam.location = (right / 2, -500, 0)
cam.rotation_euler = (math.radians(90), 0, 0)
cam.data.clip_end = 2000
scene.render.resolution_x = 1600
scene.render.resolution_y = int(1600 * min(1.0, (tall * 1.1 + 2) / (right * 1.1)))

# Lighting: Blender's bundled studio HDRI for reflections, flat light grey for the camera background.
world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
nt = world.node_tree
env = nt.nodes.new("ShaderNodeTexEnvironment")
env.image = bpy.data.images.load(str(next(Path(bpy.utils.system_resource("DATAFILES")).glob("studiolights/world/studio.exr"))))
hdr, flat, mix, path = (nt.nodes.new(t) for t in ("ShaderNodeBackground", "ShaderNodeBackground", "ShaderNodeMixShader", "ShaderNodeLightPath"))
flat.inputs["Color"].default_value = (0.62, 0.62, 0.64, 1)
hdr.inputs["Strength"].default_value = 2.2
nt.links.new(env.outputs["Color"], hdr.inputs["Color"])
nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
nt.links.new(hdr.outputs[0], mix.inputs[1])
nt.links.new(flat.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs["Surface"])

scene.render.engine = "CYCLES"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.view_settings.view_transform = "Standard"
scene.render.filepath = str(Path(png).resolve())
bpy.ops.render.render(write_still=True)
