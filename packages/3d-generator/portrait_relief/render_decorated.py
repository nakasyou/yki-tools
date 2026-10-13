"""Blender background render of the actual decorated STL, from the display side."""
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2] / 'outputs/3d'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.wm.stl_import(filepath=str(ROOT/'B661_E83A_normal_portrait_rim.stl'))
medal=bpy.context.object
medal.name='B661_E83A_Normal_Portrait_Rim'
material=bpy.data.materials.new('Silver gray')
material.diffuse_color=(.54,.57,.60,1)
material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Base Color'].default_value=(.54,.57,.60,1)
bsdf.inputs['Metallic'].default_value=.25
bsdf.inputs['Roughness'].default_value=.48
medal.data.materials.append(material)

def aim(obj,target=(0,0,0)):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

bpy.ops.object.camera_add(location=(0,0,-85))
camera=bpy.context.object
aim(camera)
camera.data.type='ORTHO';camera.data.ortho_scale=47
bpy.context.scene.camera=camera
for pos,power,size in [((-30,35,-35),65000,18),((30,-10,-45),18000,30)]:
    bpy.ops.object.light_add(type='AREA',location=pos)
    lamp=bpy.context.object;lamp.data.energy=power;lamp.data.shape='DISK';lamp.data.size=size;aim(lamp)
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.world.color=(.35,.35,.35)
scene.render.film_transparent=True
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
scene.render.filepath=str(ROOT/'B661_E83A_normal_portrait_rim.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'B661_E83A_normal_portrait_rim.blend'))
bpy.ops.render.render(write_still=True)
