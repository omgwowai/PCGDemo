# city_plan.json Schema（Phase 3 产出，Phase 4 唯一输入）

所有长度单位：**厘米**（UE 单位），便于直接进 PCG。文档 md 里用米/公里叙述。

```jsonc
{
  "meta": {
    "name": "Riverside",             // 城市名，也用作资产命名前缀
    "style": "modern_single_center", // 访谈 Q3+Q4 的组合
    "created": "2026-09-05",
    "confirmed_by_user": true         // Phase 2 确认过才能为 true
  },
  "extent": {
    "half_size_cm": 61000,           // TOWN_EXT：半边长
    "block_pitch_cm": 6000,          // BLOCK：路网间距
    "area_km2": 1.49                 // 冗余字段，供文档引用
  },
  "road_network": {
    "type": "grid",                  // grid | radial | organic
    "road_width_cm": 280,
    "main_road_every_n_blocks": 3    // 主干道加宽（可选）
  },
  "districts": [                     // 分区：从中心向外的环 or 显式矩形
    {
      "name": "CBD",
      "kind": "commercial",
      "shape": {"type": "radial_band", "r0_frac": 0.0, "r1_frac": 0.42},
      // 或 {"type": "rect", "min": [x,y], "max": [x,y]}（cm，城市中心为原点）
      "params": {"tower_height_range_cm": [150000, 450000], "lot_step_cm": 750}
    },
    {
      "name": "Residential",
      "kind": "residential",
      "shape": {"type": "radial_band", "r0_frac": 0.42, "r1_frac": 1.0},
      "params": {"keep_ratio": 0.7, "jitter_cm": 130, "yaw_jitter_deg": 14,
                  "mesh_mix": {"SM_HouseGable": 3, "SM_HouseFlat": 2}}
    }
  ],
  "facilities": [                    // 公共配套：整块街区占地
    {"name": "School",   "count": 4, "placement": "random_block",
     "mesh": "SM_SchoolL",       "plot": true},
    {"name": "Hospital", "count": 2, "placement": "random_block",
     "mesh": "SM_HospitalCross", "plot": true}
  ],
  "street_furniture": [              // 路边组件：沿路网线性分布
    {"name": "Light",      "every_cm": 1500, "side": 1,  "mesh": "SM_LampPost",
     "face": "road"},
    {"name": "StreetTree", "every_cm": 1500, "side": -1, "phase_cm": 750,
     "mesh_mix": {"SM_TreeConifer": 3, "SM_TreeRound": 1}},
    {"name": "Bench", "every_cm": 3000, "side": 1, "keep_ratio": 0.45,
     "mesh": "SM_Bench", "face": "road"}
  ],
  "render": {
    "mode_switch": true,             // 图内 debug/mesh 开关（默认 true）
    "default_mode": "meshes",
    "debug_colors": {"commercial": "Orange", "residential": "Red"}  // 与 SVG 一致
  },
  "output": {
    "graph_path": "/Game/<Name>/PCG_<Name>Graph",
    "level_path": "/Game/<Name>/Lvl_<Name>",
    "mesh_dir":  "/Game/<Name>/Meshes"       // 复用 /Game/Town/Meshes 时留空
  }
}
```

## 约束

- `confirmed_by_user` 必须在用户明确认可规划图后才置 true；Phase 4 开始前检查它
- 新增 mesh（schema 里引用了 /Game/Town/Meshes 没有的名字）→ Phase 4 先扩
  `build_town_meshes.py` 生成，再建图
- `city_plan.md` 与 json 同步产出：分区表格、配套清单、每项参数的"来源"
  （访谈答案 or 默认值）一列
