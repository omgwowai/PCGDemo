---
name: city-planning
description: 城市/城镇规划与建设技能——通过问答访谈确认需求，生成可视化规划图（SVG 分区图 Artifact）供用户确认，产出结构化规划文档（占地面积、空间分区、路网、建筑清单、公共配套），最后将规划转化为 UE 里可生成的 PCG Graph。当用户提到城市规划、城镇生成、城市建设、造城、city planning、town generation、urban layout、想在 UE/PCG 里生成城市或城镇、修改城市布局/分区/配套时，务必使用本技能——即使用户没有明确说"规划"二字，只要意图是"从需求出发生成一座城"就适用。
---

# City Planning → PCG

把一句"我想要一座 XX 风格的城"变成：确认过的规划图 → 结构化规划文档 → UE 里跑通的 PCG Graph。

## 总体流程（四阶段，顺序执行）

```
Phase 1 需求访谈  →  Phase 2 规划图确认  →  Phase 3 规划文档  →  Phase 4 PCG 转化
   (问答收敛)      (SVG 图 + 修改循环)     (city_plan.json)      (图/关卡/验证)
```

每个阶段结束都有明确产出物；Phase 2 未经用户确认不要进入 Phase 4——返工一张 SVG 比返工一张 110 节点的 PCG 图便宜得多。

## Phase 1 — 需求访谈

用 AskUserQuestion 工具做结构化问答（每轮最多 4 题，通常 2 轮收敛）。
问题清单、选项设计、追问策略见 `references/interview-guide.md`。

必须收敛的维度：
1. **规模**：占地面积（边长/半径）、街区尺寸、预期建筑量级
2. **风格与结构**：网格/放射/有机路网，单中心/多中心，密度梯度
3. **分区**：商业/住宅/工业/绿地比例，特色区域
4. **公共配套**：学校、医院、公园、广场、交通设施等种类与数量级
5. **展示方式**：debug 点 / 真实 mesh / 两者可切换（默认做成图内开关）

用户答不上来的维度给出建议默认值并明说"用了默认值，可随时改"。

## Phase 2 — 规划图确认（关键环节）

把访谈结果画成一张 2D 规划图给用户看，**图比文字省沟通**：

1. 按 `references/plan-visualization.md` 生成 SVG 分区图（路网 + 色块分区 + 配套图标 + 图例 + 关键数字表）
2. 用 Artifact 工具发布成页面，把链接给用户
3. 明确问："这张规划符合预期吗？要调整哪里？"
4. 用户提修改 → 改图 → 重新发布（同一 file_path 原地更新）→ 再确认，直到点头

## Phase 3 — 规划文档

确认后产出两个文件（放在项目 `Plans/` 目录）：
- `city_plan.json` — 结构化参数，是 Phase 4 的唯一输入。Schema 见 `references/plan-format.md`
- `city_plan.md` — 人类可读摘要：占地面积、分区比例表、建筑/配套清单、设计说明

JSON 里每个数字都必须能追溯到访谈答案或明示的默认值。

## Phase 4 — 转化为 PCG Graph

**先加载 `driving-unreal-via-mcp` skill**（内省→验证→写脚本的纪律 + 编辑器连接检查），
再按 `references/pcg-conversion.md` 的配方执行。概要：

1. **Mesh 资产**：用 GeometryScript（`unreal.GeometryScript_*`）程序化构建，**绝不用 OBJ 导入**（UE 5.7 Interchange 会崩编辑器）。已有可复用模板：`Content/Python/build_town_meshes.py`
2. **建图**：每个类别一条分支，统一模式 `点生成 → 空间筛选 → 随机化 → AddTags → Branch(模式开关) → A: Debug点 / B: StaticMeshSpawner`。可复用模板：`Content/Python/create_town_pcg_graph_v4.py`（110 节点全套）
3. **关卡**：新建或复用 Level，放 PCGVolume 挂图，GenerateOnLoad
4. **验证闭环**：点数统计（tagged_data）+ ISM 实例统计 + SceneCapture 截图，三者都过才算完成
5. **交付**：把截图路径、资产路径、开关脚本用法报告给用户

## 正式使用方式：TownActor（Details 面板工作流）

面向用户的入口是 **`ATownActor`**（C++，`Source/PCGGame/Town/`，继承 PCGVolume）：
往关卡里摆一个、挂上城镇图，之后所有调参都在 Details 面板：
- **Town|Layout**: `TownHalfSize`（半边长 cm）、`bUseSplineRoads`（样条路开关）
- **Town|Render**: `bRenderMeshes`（debug 点/真实 mesh）、`Style`（风格 DataAsset）
- 面板改属性即自动推参数进图并重生成（PostEditChangeProperty），也有
  `RegenerateTown` 按钮（CallInEditor）手动触发
- Actor 把值写进图内命名参数节点（MODE SWITCH 等，按 node_title 匹配）——
  所以**新城图必须沿用 v5 的参数节点命名**，否则面板失灵（会打 Warning 日志）

## Mesh 资产策略（重要）

**当前 mesh 全部是临时占位资产**（GeometryScript 程序化生成的简模）。美术风格与
mesh 资源解耦为 **`UTownStyleData` 蓝图资产**（`/Game/Town/Styles/DA_TownStyle_*`）：
类别名 → 加权 mesh 列表（TSoftObjectPtr<UStaticMesh>）。
- 正式美术资产到位后：Content Browser 里新建 TownStyleData 资产（或复制现有的），
  填正式 mesh，在 TownActor 的 Details 面板换 `Style` 即整城换装——不改图不改代码
- `Plans/town_styles.json` 仍是脚本化批量建风格资产的源数据
  （`setup_town_actor.py` 从它生成 DataAsset），两边同步维护
- 规划新城时 city_plan.json 的 mesh 字段应引用 style 类别名而非硬编码资产路径
- 正式资产的轴心/朝向约定需与占位资产一致：Z-up、底部轴心、+X 为"面向道路"方向；
  不一致时在 style 条目里记录偏移并在图里用 TransformPoints 校正

## 现成资产索引（本项目已验证可复用）

| 资产/脚本 | 用途 |
|---|---|
| `ATownActor` / `UTownStyleData` (C++) | 正式入口：摆 Actor + Details 面板调参 + 风格 DataAsset |
| `/Game/Town/Styles/DA_TownStyle_*` | 风格 DataAsset 实例（Prototype / NorthernVillage） |
| `Content/Python/setup_town_actor.py` | 从 json 批量建风格资产 + 部署 TownActor |
| `Content/Python/test_town_actor_properties.py` | 模拟 Details 面板改属性（验证用） |
| `/Game/Town/PCG_TownGraph` | 12 类别全套图（v5：模式/尺寸/路源/风格全可配），新城可复制改参 |
| `Plans/town_styles.json` | 美术风格注册表（style→类别→加权 mesh，DataAsset 的源数据） |
| `/Game/Town/Meshes/SM_*` (13 个) | 占位建筑/道具 mesh（prototype 风格） |
| `Content/Python/build_town_meshes.py` | GeometryScript 建 mesh 模板 |
| `Content/Python/create_town_pcg_graph_v5.py` | 建图模板（分支+参数节点+双路源+按配置装配 spawner） |
| `Content/Python/set_town_render_mode.py` | 切换 debug点/mesh 模式 |
| `Content/Python/set_town_size.py` | 改城镇尺寸（half_size cm，同步缩放 Volume/地板并重生成） |
| `Content/Python/set_town_road_source.py` | 道路源切换：程序网格 ↔ 场景 spline actor（tag=TownRoad） |
| `Content/Python/spawn_town_road_splines.py` | 生成示例道路 spline actor |
| `Content/Python/set_town_style.py` | 按 town_styles.json 换装全部 spawner |
| `Content/Python/regen_town.py` | 强制重生成 + 分类点数统计 |
| `Content/Python/verify_town_instances.py` | ISM 实例统计 |
| `Content/Python/force_clean_town.py` | 清理叠加残留实例后干净重生成 |
| `Content/Python/capture_town_view.py` | SceneCapture 截图（不受编辑器后台节流影响） |

## 红线

| 想法 | 现实 |
|---|---|
| "需求很明确了，跳过规划图直接建图" | 图内 110+ 节点，返工成本高。SVG 确认一轮只要几分钟。 |
| "用 AssetImportTask 导 OBJ 更快" | UE 5.7.4 直接崩编辑器（TaskGraph 断言）。用 GeometryScript。 |
| "凭记忆写 unreal API" | 先内省。本项目的坑都记录在 pcg-conversion.md，先读它。 |
| "生成完了就算完成" | 必须跑验证闭环：点数 + 实例数 + 截图。 |
