"""Generate simple town-prop OBJ meshes (Z-up, cm units, base pivot at Z=0).
Each part gets a usemtl group so UE creates material slots we can fill."""
import math, os

OUT = os.path.dirname(os.path.abspath(__file__))

class Obj:
    def __init__(self):
        self.v = []
        self.f = []  # (mtl, [idx...])
    def add_box(self, mtl, cx, cy, z0, sx, sy, sz):
        x0, x1 = cx - sx / 2, cx + sx / 2
        y0, y1 = cy - sy / 2, cy + sy / 2
        z1 = z0 + sz
        b = len(self.v)
        self.v += [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                   (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
        quads = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        for q in quads:
            self.f.append((mtl, [b + i + 1 for i in q]))
    def add_prism_x(self, mtl, cx, cy, z0, sx, sy, sz):
        """Triangular prism (gable roof) ridge along X."""
        x0, x1 = cx - sx / 2, cx + sx / 2
        y0, y1 = cy - sy / 2, cy + sy / 2
        z1 = z0 + sz
        ym = cy
        b = len(self.v)
        self.v += [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                   (x0,ym,z1),(x1,ym,z1)]
        self.f.append((mtl, [b+1, b+2, b+6, b+5]))      # south slope
        self.f.append((mtl, [b+3, b+4, b+5, b+6]))      # north slope
        self.f.append((mtl, [b+4, b+1, b+5]))           # west gable
        self.f.append((mtl, [b+2, b+3, b+6]))           # east gable
        self.f.append((mtl, [b+1, b+4, b+3, b+2]))      # bottom
    def add_cylinder(self, mtl, cx, cy, z0, r, h, seg=12, r_top=None):
        r2 = r if r_top is None else r_top
        z1 = z0 + h
        b = len(self.v)
        for z, rr in ((z0, r), (z1, r2)):
            for i in range(seg):
                a = 2 * math.pi * i / seg
                self.v.append((cx + rr * math.cos(a), cy + rr * math.sin(a), z))
        for i in range(seg):
            j = (i + 1) % seg
            self.f.append((mtl, [b+i+1, b+j+1, b+seg+j+1, b+seg+i+1]))
        self.f.append((mtl, [b + i + 1 for i in range(seg)][::-1]))          # bottom
        self.f.append((mtl, [b + seg + i + 1 for i in range(seg)]))          # top
    def add_cone(self, mtl, cx, cy, z0, r, h, seg=12):
        z1 = z0 + h
        b = len(self.v)
        for i in range(seg):
            a = 2 * math.pi * i / seg
            self.v.append((cx + r * math.cos(a), cy + r * math.sin(a), z0))
        self.v.append((cx, cy, z1))
        top = b + seg + 1
        for i in range(seg):
            j = (i + 1) % seg
            self.f.append((mtl, [b+i+1, b+j+1, top]))
        self.f.append((mtl, [b + i + 1 for i in range(seg)][::-1]))
    def add_sphere(self, mtl, cx, cy, cz, r, seg=10, rings=7):
        b = len(self.v)
        self.v.append((cx, cy, cz - r))
        for ri in range(1, rings):
            phi = math.pi * ri / rings - math.pi / 2
            for i in range(seg):
                a = 2 * math.pi * i / seg
                self.v.append((cx + r * math.cos(phi) * math.cos(a),
                               cy + r * math.cos(phi) * math.sin(a),
                               cz + r * math.sin(phi)))
        self.v.append((cx, cy, cz + r))
        top = b + 1 + (rings - 1) * seg + 1
        for i in range(seg):
            j = (i + 1) % seg
            self.f.append((mtl, [b+1, b+1+j+1, b+1+i+1]))
        for ri in range(rings - 2):
            r0, r1 = b + 1 + ri * seg, b + 1 + (ri + 1) * seg
            for i in range(seg):
                j = (i + 1) % seg
                self.f.append((mtl, [r0+i+1, r0+j+1, r1+j+1, r1+i+1]))
        last = b + 1 + (rings - 2) * seg
        for i in range(seg):
            j = (i + 1) % seg
            self.f.append((mtl, [last+i+1, last+j+1, top]))
    def save(self, name):
        path = os.path.join(OUT, name + ".obj")
        with open(path, "w") as fp:
            fp.write(f"o {name}\n")
            for x, y, z in self.v:
                fp.write(f"v {x:.3f} {y:.3f} {z:.3f}\n")
            cur = None
            for mtl, idx in self.f:
                if mtl != cur:
                    fp.write(f"usemtl {mtl}\n")
                    cur = mtl
                fp.write("f " + " ".join(str(i) for i in idx) + "\n")
        print("wrote", path, len(self.v), "verts")

# ---- axis/scale probe: box 100 x 200 x 300 ----
o = Obj(); o.add_box("probe", 0, 0, 0, 100, 200, 300); o.save("SM_AxisProbe")

# ---- road plate 250x250x15 ----
o = Obj(); o.add_box("road", 0, 0, 0, 250, 250, 15); o.save("SM_RoadPlate")

# ---- civic plot plate 2600x2600x20 ----
o = Obj(); o.add_box("pavement", 0, 0, 0, 2600, 2600, 20); o.save("SM_PlotPlate")

# ---- tower: body 350x350x2000 + roof box ----
o = Obj()
o.add_box("glass", 0, 0, 0, 350, 350, 2000)
o.add_box("roofgray", 0, 0, 2000, 360, 360, 30)
o.save("SM_Tower")

# ---- gabled house: walls 320x260x180, roof prism to 300 ----
o = Obj()
o.add_box("wall", 0, 0, 0, 320, 260, 180)
o.add_prism_x("roof", 0, 0, 180, 340, 300, 120)
o.save("SM_HouseGable")

# ---- flat-roof house: walls 300x300x240 + parapet ----
o = Obj()
o.add_box("wall", 0, 0, 0, 300, 300, 240)
o.add_box("roof", 0, 0, 240, 310, 310, 20)
o.save("SM_HouseFlat")

# ---- school: L-shape wings 1500x500 + 500x900, flat roofs ----
o = Obj()
o.add_box("wall", 0, -200, 0, 1500, 500, 380)
o.add_box("wall", -500, 250, 0, 500, 900, 380)
o.add_box("roof", 0, -200, 380, 1520, 520, 25)
o.add_box("roof", -500, 250, 380, 520, 920, 25)
o.save("SM_SchoolL")

# ---- hospital: cross shape, taller core ----
o = Obj()
o.add_box("wall", 0, 0, 0, 1300, 450, 700)
o.add_box("wall", 0, 0, 0, 450, 1300, 700)
o.add_box("wall", 0, 0, 700, 500, 500, 250)
o.add_box("roof", 0, 0, 950, 520, 520, 20)
o.save("SM_HospitalCross")

# ---- round tree: trunk + sphere canopy ----
o = Obj()
o.add_cylinder("trunk", 0, 0, 0, 14, 160, seg=8)
o.add_sphere("canopy", 0, 0, 270, 140, seg=10, rings=7)
o.save("SM_TreeRound")

# ---- conifer: trunk + two cones ----
o = Obj()
o.add_cylinder("trunk", 0, 0, 0, 12, 110, seg=8)
o.add_cone("canopy", 0, 0, 100, 130, 200, seg=10)
o.add_cone("canopy", 0, 0, 240, 95, 180, seg=10)
o.save("SM_TreeConifer")

# ---- lamp post: base, pole, arm +X, head ----
o = Obj()
o.add_cylinder("pole", 0, 0, 0, 12, 25, seg=10)
o.add_cylinder("pole", 0, 0, 25, 6, 355, seg=8)
o.add_box("pole", 40, 0, 370, 80, 8, 8)
o.add_box("lamphead", 75, 0, 360, 45, 16, 12)
o.save("SM_LampPost")

# ---- bench: seat, back (+Y), 4 legs; length along X ----
o = Obj()
o.add_box("wood", 0, 0, 40, 140, 45, 6)
o.add_box("wood", 0, 24, 46, 140, 6, 40)
for lx in (-60, 60):
    for ly in (-16, 16):
        o.add_box("metal", lx, ly, 0, 8, 8, 40)
o.save("SM_Bench")

# ---- bin: cylinder + lid ----
o = Obj()
o.add_cylinder("binbody", 0, 0, 0, 22, 70, seg=10)
o.add_cylinder("metal", 0, 0, 70, 24, 8, seg=10)
o.save("SM_Bin")

# ---- bus shelter: 2 posts, roof, back panel; length along X, open side +Y ----
o = Obj()
o.add_box("metal", -140, -50, 0, 12, 12, 230)
o.add_box("metal", 140, -50, 0, 12, 12, 230)
o.add_box("shelterroof", 0, 0, 230, 320, 140, 12)
o.add_box("glasspanel", 0, -55, 20, 300, 6, 200)
o.save("SM_BusShelter")

print("all meshes generated")
