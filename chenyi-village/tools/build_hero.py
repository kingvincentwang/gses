"""用 Blender 建主角（依 images/hero.png）並匯出含動畫的 glb。
用法："<blender.exe>" -b --factory-startup -P tools/build_hero.py -- <專案資料夾>
座標：Blender Z 朝上、角色面向 +Y（匯出 +Y Up 後即 three.js 的 -Z），腳底在原點，身高約 1.5 m。
每個部位整塊綁到一根骨頭（權重 1），屬於玩具公仔式的關節。動作：Idle、Walk、Run、Wave、Cheer、Surprise、Sit。"""
import sys, math, pathlib
import bpy
from mathutils import Vector, Quaternion, Matrix

root = pathlib.Path(sys.argv[sys.argv.index("--") + 1]).resolve()
SRC = root / "models" / "src"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24

# ---------- 材質 ----------
MATS = {}
def mat(name, rgb, rough=.7, tex=None):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*[(c / 255) ** 2.2 for c in rgb], 1)  # sRGB 轉線性
    bsdf.inputs["Roughness"].default_value = rough
    if tex:
        n = m.node_tree.nodes.new("ShaderNodeTexImage"); n.image = bpy.data.images.load(str(SRC / tex))
        m.node_tree.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
    MATS[name] = m; return m
def srgb(h): return ((h >> 16) & 255, (h >> 8) & 255, h & 255)
SKIN = mat("skin", srgb(0xf9d3b4), .6); SHIRT = mat("shirt", srgb(0x6db4ef)); SLEEVE = mat("sleeve", srgb(0x2750d8))
PANTS = mat("pants", srgb(0x4ca2ee)); WHITE = mat("white", srgb(0xffffff), .8); ORANGE = mat("orange", srgb(0xf08a24), .55)
HAIR = mat("hair", srgb(0x19161a), .4); PUPIL = mat("pupil", srgb(0x3f2312), .3); DARK = mat("dark", srgb(0x20181a), .5)
BLUSH = mat("blush", srgb(0xf6a8a0), .8); MOUTH = mat("mouth", srgb(0xcc4b4f), .6); TONGUE = mat("tongue", srgb(0xf58a8a), .6)
LOGO = mat("logo", (255, 255, 255), .8, "logo.png"); CHEST = mat("chest", (255, 255, 255), .8, "chest.png")

# ---------- 建模工具（參數用 three.js 座標寫，轉成 Blender：x, -z, y） ----------
def B(x, y, z): return Vector((x, -z, y))
PARTS = []
def finish(o, m, bone, smooth=True, bevel=0):
    o.data.materials.append(m)
    if smooth:
        for p in o.data.polygons: p.use_smooth = True
    if bevel:
        bm = o.modifiers.new("bev", "BEVEL"); bm.width = bevel; bm.segments = 3
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier="bev")
    PARTS.append((o, bone)); return o
def sphere(r, m, pos, bone, scale=(1, 1, 1), seg=24, ring=14):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=ring, location=pos)
    o = bpy.context.active_object; o.scale = (scale[0], scale[2], scale[1]); return finish(o, m, bone)
def cyl(r1, r2, h, m, pos, bone, seg=24, rot=None):
    bpy.ops.mesh.primitive_cone_add(radius1=r2, radius2=r1, depth=h, vertices=seg, location=pos)
    o = bpy.context.active_object
    if rot: o.rotation_euler = rot
    return finish(o, m, bone, smooth=True)
def cube(size, m, pos, bone, bevel=.012, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos); o = bpy.context.active_object
    o.scale = (size[0], size[2], size[1])
    if rot: o.rotation_euler = rot
    bpy.context.view_layer.objects.active = o; bpy.ops.object.transform_apply(scale=True, rotation=True, location=False)
    return finish(o, m, bone, smooth=False, bevel=bevel)
def cone(r, h, m, pos, bone, rot):
    bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=0, depth=h, vertices=10, location=pos)
    o = bpy.context.active_object; o.rotation_euler = rot; return finish(o, m, bone)
def plane(w, h, m, pos, normal, bone):
    bpy.ops.mesh.primitive_plane_add(size=1, location=pos); o = bpy.context.active_object
    o.scale = (w, h, 1)
    o.rotation_mode = "QUATERNION"; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(normal.normalized()) @ Quaternion((0, 0, 1), math.pi)  # 轉 180° 讓字不左右顛倒
    return finish(o, m, bone, smooth=False)

# 身體（Spine）
cyl(.19, .25, .4, SHIRT, B(0, .63, 0), "Spine", seg=32)
cyl(.11, .13, .03, SLEEVE, B(0, .84, 0), "Spine")
plane(.32, .16, CHEST, B(0, .67, -.232), Vector((0, 1, -.12)), "Spine")
# 短褲（Hips）
cyl(.24, .27, .2, PANTS, B(0, .36, 0), "Hips", seg=32)
# 頭（Head）
HY = 1.14
sphere(.36, SKIN, B(0, HY, 0), "Head", (1.08, .98, 1), 40, 24)
for s in (-1, 1):
    sphere(.075, SKIN, B(s * .385, HY - .03, 0), "Head", (.7, 1, 1), 16, 10)
    e = sphere(.078, WHITE, B(s * .15, HY - .03, -.312), "Head", (.95, 1.18, .5), 20, 12)
    sphere(.06, PUPIL, B(s * .15, HY - .035, -.338), "Head", (1, 1.18, .45), 20, 12)
    sphere(.02, WHITE, B(s * .13, HY + .005, -.368), "Head", (1, 1, .6), 10, 6)
    sphere(.012, WHITE, B(s * .168, HY - .065, -.366), "Head", (1, 1, .6), 8, 6)
    cube((.13, .024, .02), DARK, B(s * .155, HY + .08, -.34), "Head", bevel=.008, rot=(0, -s * .14, 0))
    sphere(.06, BLUSH, B(s * .235, HY - .125, -.265), "Head", (1, .7, .32), 16, 8)
sphere(.066, MOUTH, B(0, HY - .175, -.326), "Head", (1.35, .62, .4), 20, 10)
sphere(.04, TONGUE, B(0, HY - .19, -.349), "Head", (1.3, .45, .3), 14, 8)
sphere(.017, SKIN, B(0, HY - .075, -.362), "Head", (1, 1, 1), 10, 6)
# 頭髮
bpy.ops.mesh.primitive_uv_sphere_add(radius=.375, segments=32, ring_count=18, location=B(0, HY + .03, .03))
hr = bpy.context.active_object; hr.scale = (1.08, 1.02, 1)
import bmesh
bm = bmesh.new(); bm.from_mesh(hr.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -.04 or (v.co.y > .2 and v.co.z < .2)], context="VERTS")
bm.to_mesh(hr.data); bm.free(); sol = hr.modifiers.new("s", "SOLIDIFY"); sol.thickness = .02
bpy.context.view_layer.objects.active = hr; bpy.ops.object.modifier_apply(modifier="s"); finish(hr, HAIR, "Head")
for i in range(15):
    a = i / 15 * math.tau
    if math.cos(a) < -.7: continue
    p = B(math.sin(a) * .37, HY - .02, math.cos(a) * .35 + .02)
    cone(.08, .22, HAIR, p, "Head", (math.pi + math.cos(a) * .6, 0, math.sin(a) * .6) if False else (math.pi - math.cos(a) * .55, math.sin(a) * .55, 0))
for x in (-.19, -.06, .07, .19):
    cone(.085, .19, HAIR, B(x, HY + .11 - abs(x) * .1, -.32), "Head", (math.pi - .7, 0, -x * 1.2))
# 帽子：橘色帽頂、白帽簷、帽徽（整頂帽子歪向右前方）
cap_rot = Matrix.Rotation(-.32, 4, "Z") @ Matrix.Rotation(.08, 4, "Y")
cap_pivot = B(0, HY + .03, 0)
cap_objs = []
bpy.ops.mesh.primitive_uv_sphere_add(radius=.39, segments=40, ring_count=20, location=(0, 0, 0))
dome = bpy.context.active_object; bm = bmesh.new(); bm.from_mesh(dome.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -.01], context="VERTS"); bm.to_mesh(dome.data); bm.free()
dome.scale = (1.07, 1.07, .84); dome.location = (0, -.02, .08); cap_objs.append(finish(dome, ORANGE, "Head"))
cap_objs.append(sphere(.05, ORANGE, Vector((0, -.02, .4)), "Head"))
bpy.ops.mesh.primitive_cylinder_add(radius=.32, depth=.03, vertices=40, location=(0, .33, .09))
brim = bpy.context.active_object; brim.scale = (1.05, 1.1, 1); brim.rotation_euler = (.3, 0, 0); brim.location = Matrix.Rotation(-.55, 4, "Z") @ brim.location; brim.rotation_euler.z = -.55; cap_objs.append(finish(brim, WHITE, "Head"))  # 帽簷偏向右前方
cap_objs.append(plane(.2, .19, LOGO, Matrix.Rotation(.42, 4, "Z") @ Vector((0, .35, .28)), Matrix.Rotation(.42, 4, "Z") @ Vector((0, .82, .57)), "Head"))  # 帽徽在左前方
for o in cap_objs:
    bpy.context.view_layer.update()
    o.matrix_world = Matrix.Translation(cap_pivot) @ cap_rot @ o.matrix_world
# 手臂
for s, bone in ((-1, "ArmL"), (1, "ArmR")):
    sphere(.1, SLEEVE, B(s * .225, .75, 0), bone, (1, 1.15, 1), 20, 12)
    cyl(.058, .066, .26, SKIN, B(s * .245, .58, 0), bone, seg=16)
    sphere(.072, SKIN, B(s * .255, .43, 0), bone, (1, 1.05, 1), 16, 10)
# 腿
for s, bone in ((-1, "LegL"), (1, "LegR")):
    cyl(.07, .065, .14, SKIN, B(s * .115, .2, 0), bone, seg=16)
    cyl(.066, .07, .09, WHITE, B(s * .115, .1, 0), bone, seg=16)
    cube((.15, .08, .26), ORANGE, B(s * .115, .035, -.035), bone, bevel=.03)
    cube((.11, .05, .14), SLEEVE, B(s * .115, .085, -.06), bone, bevel=.015)

# ---------- 骨架 ----------
bpy.ops.object.armature_add(location=(0, 0, 0)); arm = bpy.context.active_object; arm.name = "HeroRig"; arm.data.name = "HeroRig"
bpy.ops.object.mode_set(mode="EDIT"); eb = arm.data.edit_bones; eb.remove(eb[0])
def bone(name, head, tail, parent=None):
    b = eb.new(name); b.head = head; b.tail = tail; b.roll = 0
    if parent: b.parent = eb[parent]; b.use_connect = False
bone("Hips", (0, 0, .42), (0, 0, .58)); bone("Spine", (0, 0, .58), (0, 0, .86), "Hips")
bone("Head", (0, 0, .88), (0, 0, 1.3), "Spine")
for s, n in ((-1, "L"), (1, "R")):
    bone("Arm" + n, (s * .22, 0, .8), (s * .25, 0, .42), "Spine")
    bone("Leg" + n, (s * .115, 0, .3), (s * .115, 0, .02), "Hips")
bpy.ops.object.mode_set(mode="OBJECT")

# 合併部位並綁定骨頭（權重 1）
for o, bn in PARTS:
    vg = o.vertex_groups.new(name=bn); vg.add(list(range(len(o.data.vertices))), 1.0, "REPLACE")
bpy.ops.object.select_all(action="DESELECT")
for o, _ in PARTS: o.select_set(True)
bpy.context.view_layer.objects.active = PARTS[0][0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.join(); body = bpy.context.active_object; body.name = "Hero"
body.parent = arm; md = body.modifiers.new("rig", "ARMATURE"); md.object = arm

# ---------- 動作 ----------
POSE = arm.pose.bones
for pb in POSE: pb.rotation_mode = "QUATERNION"
def wq(pb, *rots):
    """以世界軸（three 座標名稱：x 右、y 上、z 前後）組合旋轉，轉成骨頭本地四元數。"""
    q = Quaternion()
    for axis, ang in rots:
        ax = {"x": (1, 0, 0), "y": (0, 0, 1), "z": (0, 1, 0)}[axis]
        q = Quaternion(ax, ang) @ q
    rest = pb.bone.matrix_local.to_quaternion()
    return rest.inverted() @ q @ rest
def key(pose, f):
    for name, rots in pose.items():
        if name == "_loc":
            continue
        pb = POSE[name]
        pb.rotation_quaternion = wq(pb, *rots); pb.keyframe_insert("rotation_quaternion", frame=f)
    hz = pose.get("_loc", 0)
    POSE["Hips"].location = (0, hz, 0); POSE["Hips"].keyframe_insert("location", frame=f)
def action(name, frames):
    a = bpy.data.actions.new(name); a.use_fake_user = True
    arm.animation_data_create(); arm.animation_data.action = a
    for pb in POSE:
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    for f, pose in frames: key(pose, f)
    track = arm.animation_data.nla_tracks.new(); track.name = name
    track.strips.new(name, int(frames[0][0]), a); arm.animation_data.action = None
ALL = ["Hips", "Spine", "Head", "ArmL", "ArmR", "LegL", "LegR"]
def P(**kw):
    d = {b: [] for b in ALL}; d.update({k: v for k, v in kw.items()}); return d
# x 軸正向：手腳往前擺；z 軸（前後軸）：手往外側舉
def walk(amp, arm_amp, bob, lean, n):
    q = n // 4
    return [(0, P(LegL=[("x", amp)], LegR=[("x", -amp)], ArmL=[("x", -arm_amp), ("z", .12)], ArmR=[("x", arm_amp), ("z", -.12)], Spine=[("x", lean)], _loc=0)),
            (q, P(LegL=[("x", 0)], LegR=[("x", 0)], ArmL=[("z", .12)], ArmR=[("z", -.12)], Spine=[("x", lean)], _loc=bob)),
            (2 * q, P(LegL=[("x", -amp)], LegR=[("x", amp)], ArmL=[("x", arm_amp), ("z", .12)], ArmR=[("x", -arm_amp), ("z", -.12)], Spine=[("x", lean)], _loc=0)),
            (3 * q, P(LegL=[("x", 0)], LegR=[("x", 0)], ArmL=[("z", .12)], ArmR=[("z", -.12)], Spine=[("x", lean)], _loc=bob)),
            (n, P(LegL=[("x", amp)], LegR=[("x", -amp)], ArmL=[("x", -arm_amp), ("z", .12)], ArmR=[("x", arm_amp), ("z", -.12)], Spine=[("x", lean)], _loc=0))]
action("Idle", [(0, P(ArmL=[("z", .1)], ArmR=[("z", -.1)], Head=[("z", .04)], _loc=0)),
                (24, P(ArmL=[("z", .16)], ArmR=[("z", -.16)], Spine=[("x", -.03)], Head=[("z", -.04), ("y", .08)], _loc=.012)),
                (48, P(ArmL=[("z", .1)], ArmR=[("z", -.1)], Head=[("z", .04)], _loc=0))])
action("Walk", walk(.55, .55, .035, .05, 24))
action("Run", walk(.95, 1.0, .07, .2, 16))
wave_up = lambda a: P(ArmR=[("z", -2.25 + a), ("x", .55)], ArmL=[("z", .12)], Head=[("z", -.12)], Spine=[("z", -.05)])
action("Wave", [(0, wave_up(0)), (8, wave_up(.35)), (16, wave_up(0)), (24, wave_up(.35)), (32, wave_up(0))])
action("Cheer", [(0, P(_loc=0)), (6, P(LegL=[("x", .5)], LegR=[("x", .5)], ArmL=[("z", .6)], ArmR=[("z", -.6)], _loc=-.06)),
                 (12, P(ArmL=[("z", 2.0), ("x", .35)], ArmR=[("z", -2.0), ("x", .35)], Head=[("x", -.2)], _loc=.22)),
                 (18, P(ArmL=[("z", 1.8), ("x", .3)], ArmR=[("z", -1.8), ("x", .3)], _loc=.05)), (26, P(ArmL=[("z", .12)], ArmR=[("z", -.12)], _loc=0))])
action("Surprise", [(0, P(_loc=0)), (5, P(ArmL=[("z", 1.5), ("x", .5)], ArmR=[("z", -1.5), ("x", .5)], Spine=[("x", -.22)], Head=[("x", -.25)], _loc=.06)),
                    (18, P(ArmL=[("z", 1.3), ("x", .4)], ArmR=[("z", -1.3), ("x", .4)], Spine=[("x", -.15)], Head=[("x", -.15)], _loc=.02)),
                    (26, P(ArmL=[("z", .12)], ArmR=[("z", -.12)], _loc=0))])
action("Sit", [(0, P(LegL=[("x", 1.45)], LegR=[("x", 1.45)], ArmL=[("x", .5), ("z", .1)], ArmR=[("x", .5), ("z", -.1)], _loc=-.27)),
               (24, P(LegL=[("x", 1.45)], LegR=[("x", 1.45)], ArmL=[("x", .55), ("z", .1)], ArmR=[("x", .55), ("z", -.1)], Head=[("y", .1)], _loc=-.265))])

out = root / "models" / "hero.glb"
bpy.ops.object.select_all(action="DESELECT"); arm.select_set(True); body.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
                          export_animations=True, export_animation_mode="NLA_TRACKS", export_image_format="AUTO",
                          export_texcoords=True, export_normals=True, export_skins=True)
print("EXPORTED", out, round(out.stat().st_size / 1024), "KB", "verts", len(body.data.vertices))
