# city_plan.json → PCG Graph 转化配方（Phase 4）

前置：已加载 `driving-unreal-via-mcp` skill；编辑器已连接（工具报
"not connected" 就停下让用户开编辑器，别盲试）。

## 步骤

### 0. 预检
- 确认 `city_plan.json` 的 `meta.confirmed_by_user == true`
- 确认 PCG / GeometryScripting 插件已启用（`.uproject` 里查）
- 读一遍本文件末尾的"已验证的坑"

### 1. Mesh 资产
plan 里引用的 mesh 名若已在 `/Game/Town/Meshes` 全部存在 → 跳过。
否则复制 `Content/Python/build_town_meshes.py` 的 Builder 类扩新 mesh：
- 全部 Z-up、底部轴心（origin=BASE）、厘米尺度
- 每个部件独立材质槽：enable_material_i_ds → 记录 append 前后三角形数 →
  convert_index_array_to_mesh_selection → set_material_id_for_mesh_selection
- 材质用 `M_TownColor` 母材质 + set_material_instance_vector_parameter_value

### 2. 建图（以 create_town_pcg_graph_v4.py 为模板）
每个 district / facility / street_furniture 条目 = 一条分支，统一骨架：

```
点生成 → 空间筛选 → 随机化 → AddTags(类别名) → Branch ┬ A: BoundsModifier+debug材质（点模式）
                                                      └ B: StaticMeshSpawner（mesh模式）
```

- **模式开关**：一个 CreateAttributeSet 节点（node_title 含 "MODE SWITCH"），
  bool 属性名 `bOutputToB`，Out 连每个 Branch 的 `bOutputToB` 参数 pin。
  True=mesh，False=debug 点
- **点生成**：
  - 路网 grid：两个 CreatePointsGrid（NS: cell=[BLOCK, step, 100]，EW 反之）+ Union
  - radial 路网：环形 = CreatePointsSphere 或極坐标 Transform 近似；实现成本高，
    确认用户真的需要再做
  - 街区中心：CreatePointsGrid cell=[BLOCK, BLOCK]
  - 城市中心参照点：CreatePointsSettings + points_to_create=[PCGPoint()]
- **空间筛选**：Distance(set_density=True) + DensityFilter 切环/带；
  facility 占地块用 BoundsModifier(SET) 放大 + Difference(BINARY) 从其他候选中挖除
- **随机化**：DensityNoise(SET)+DensityFilter=随机剔除；TransformPoints=抖动/朝向/缩放。
  radial_band 的 r0_frac/r1_frac 直接映射 DensityFilter 的 lower/upper bound
- **朝向**：路边组件 NS/EW 两路各自 TransformPoints(absolute_rotation) 定死 yaw 再 Union
- **Spawner**：set_mesh_selector_type(PCGMeshSelectorWeighted)，
  mesh_selector_instance.mesh_entries = [PCGMeshSelectorWeightedEntry...]
  （weight + descriptor.static_mesh，descriptor 要写回）

### 3. 关卡
```python
les.new_level_from_template(level_path, "/Engine/Maps/Templates/Template_Default")
vol = eas.spawn_actor_from_class(unreal.PCGVolume, ...)
vol.set_actor_scale3d(...)          # 覆盖 extent（默认 brush 200cm 立方）
pcg = vol.get_editor_property("pcg_component")
pcg.set_graph(graph); pcg.generate(True)
pcg.set_editor_property("generation_trigger", unreal.PCGComponentGenerationTrigger.GENERATE_ON_LOAD)
les.save_current_level()
```
放大模板 Floor 到城市大小，避免物件悬空。

### 4. 验证闭环（三项都过才算完成）
1. **分类点数**：`get_generated_graph_output().tagged_data` 每个 tag 的
   get_num_points() > 0（模板脚本 regen_town.py）
2. **实例数**：mesh 模式下 vol 的 InstancedStaticMeshComponent 实例统计与点数吻合
   （verify_town_instances.py）
3. **截图**：capture_town_view.py（SceneCapture2D 路线）俯瞰 + 街景各一张，
   Read 图片确认与规划图一致——分区位置、配套数量对得上 SVG

### 5. 交付
- 报告：资产路径、各类别点数/实例数、截图路径、开关用法
  （set_town_render_mode.py args {"meshes": true|false}）
- 更新 city_plan.md 附上实际生成统计

## v5 图的可配置机制（新城建图直接沿用）

- **参数节点模式**：CreateAttributeSet 节点输出属性名 = 目标节点参数 pin 名，连线即覆盖。
  已用于：`bOutputToB`（渲染模式 Branch）、`bUseInputB`（路源 BooleanSelect）、
  `GridExtents`（CreatePointsGrid）、`MaximumDistance`（Distance）。图参数
  (User Parameters) 的 Python API 无效，别走那条路
- **尺寸**：三个 SIZE GridExtents 节点（Full/Cand/Block）+ SIZE MaxDistance；
  set_town_size.py 按 node_title 找到并改值，同时缩放 PCGVolume 和地板
- **路源**：Grid 路（两网格+Union+SelfPruning 去重）和 Spline 路
  （GetSpline(tag=TownRoad) → SplineSampler(ON_SPLINE, DISTANCE)）都进
  BooleanSelect；下游 Distance 引用 select 后的结果，建筑随路源自动重排。
  spline actor = 普通 Actor + SubobjectDataSubsystem 加 SplineComponent + tag
- **风格**：spawner 的 mesh_entries 全部从 Plans/town_styles.json 装配
  （建图时读 active_style；set_town_style.py 可随时重装配）。正式美术资产 =
  json 里新增 style 条目，不动图

## 防重叠配方（v6 已审计通过，新城建图必做）

- **异类互斥**：把"障碍物分支"的点用 BoundsModifier(SET) 膨胀成禁区
  （节点命名 "OBSTACLE ..."），下游分支用 Difference(BINARY) 减掉。
  **关键坑**：Difference 会连 Source 点自身 bounds 碰到禁区的也吃掉——
  减之前必须先把 Source 缩成 ±10 的小标记点（见 v6 的 `clear_against()`），
  否则宽走廊会把整类建筑清空（实测 Commercial 归零）
- **同类间距**：BoundsModifier 设成真实占地 + SelfPruning(LARGE_TO_SMALL)；
  路网格自身用 REMOVE_DUPLICATES 去路口重复点
- **沿路组件相位**：共享同一 1500 晶格的系列（灯/树/椅/桶）必须错开
  phase，且注意 phase 对 3000（路距）取模——选错会正好落在横路路面上
- **验收**：跑 `audit_town_overlaps_3d.py`（树干/树冠分层判定 + 白名单）
  必须零冲突；设计允许项 = 路面板对缝相接、公共建筑站自家地块、树冠悬垂路面上空

## 已验证的坑（UE 5.7.4，绕开它们）

1. **OBJ 导入崩编辑器**（Interchange TaskGraph 断言）→ 只用 GeometryScript
2. GeometryScript 的 Python 库名是 `unreal.GeometryScript_*`，不是 `GeometryScriptLibrary_*`
3. `PCGAddTagSettings.tags_to_add` 是逗号分隔字符串，不是数组
4. Union 输出直接进 DensityNoise 报 `$Density not found` → 中间加 ConvertToPointData
5. 两个 DensityNoise 默认种子相同 → 同点位噪声完全一样，叠加分流时给第二个设独立 seed
6. `PCGGraph.remove_nodes()` 无参；清图用循环 `remove_node(n)`；原地重建优于删资产重建
   （删除后同名重建会因内存残留包失败）
7. `PCGComponent.cleanup(True)` 后再 `generate(True)` 才是干净重生成
8. selector 结构体（PCGAttributePropertyOutputSelector 等）的 set_attribute_name
   不生效时用 `import_text('(Selection=Attribute,AttributeName="X")')`
9. 编辑器后台节流时视口截图静默失败 → 用 SceneCapture2D + export_render_target
10. 编辑器崩溃重启后会卡在恢复模态框（握手超时）→ 删
    `Saved/Autosaves/PackageRestoreData.json` 再启动；重启后记得 load_level
11. `extra_names` 等 selector 字段 Python 不可写；分支参数 pin 靠
    CreateAttributeSet 输出属性名与 pin 名一致（如 bOutputToB）自动绑定
12. MaterialInstanceConstantFactoryNew 无 parent 参数 → 创建后
    MaterialEditingLibrary.set_material_instance_parent
