# 虫洞时间轴图谱主视图 —— 一比一复刻提示词文档

> 用途：把本文档完整喂给任意大模型，即可生成与 Career Galaxy 主视图行为一致的可运行实现。
> 文档包含：创意构思 → 完整提示词 → 精确技术规格（参数/公式/算法）→ 验收清单。
> 来源：Career Galaxy（Three.js 0.160.0，ES Modules + Import Map，零构建工具）。

---

## 一、创意构思（设计隐喻）

**"虫洞 + 年轮"（Wormhole & Growth Rings）**：

- **时间 = 深度（Z 轴）**。把时间轴立起来沿 Z 轴负向延伸，形成纵向"时间虫洞"。每个时间切片（年/月/日/小时）是一个垂直于 Z 轴的圆形平面，相机斜上方俯视，如俯瞰时间隧道。
- **岗位 = 星球**。每个岗位是发着分类颜色光辉的小球，悬浮在所属时间层平面上。
- **层级 = 年轮**。每层画三个同心圆环（内/中/外），节点按岗位层级落位：内环=核心管理/专家，中环=资深骨干，外环=基础/新兴。层层叠加呈"树木年轮"，直观表达岗位生态的生长。
- **氛围 = 深空**。暗色宇宙背景 `#050510` + 指数雾 + 2000 颗星点 + 中央双螺旋泛光粒子带，营造"在时间虫洞中航行"的沉浸感。

---

## 二、主提示词（可直接喂给 LLM）

````text
请用 Three.js 0.160.0（ES Modules + Import Map 从 unpkg CDN 加载，零构建工具，
浏览器直接运行）实现一个"虫洞时间轴 3D 知识图谱主视图"。交付 4 个文件：
index.html、css/style.css、js/config.js、js/scene.js、js/visualization.js、
js/data.js、js/interaction.js、js/animation.js、js/main.js。严格遵循以下规格：

【1. index.html 骨架】
- <script type="importmap"> 映射：
  "three" → "https://unpkg.com/three@0.160.0/build/three.module.js"
  "three/addons/" → "https://unpkg.com/three@0.160.0/examples/jsm/"
- DOM 结构（ID 必须一字不差，JS 硬引用）：
  #loading（初始化提示文本）
  #canvas-container（渲染器挂载点，绝对定位铺满全屏，z-index:1）
  #ui-layer（覆盖全屏的 UI 层，z-index:2，pointer-events:none，
    子元素按需 pointer-events:auto）内含：
    header > h1 标题 + .subtitle 副标题 + select#year-filter
      （首项 <option value="all">全部年份</option>）
    #info-panel > #panel-title,#panel-year,#panel-category,#panel-ring,
      #panel-meta(默认 display:none 内含 #panel-company/#panel-location/
      #panel-salary),#panel-desc,#panel-tags
    #controls > .time-display#current-year-display +
      input#time-slider(type=range,min=0,max=100,step=0.1,value=0) +
      时间轴起止标签
- <script type="module" src="js/main.js">

【2. CSS 要点】
- CSS 变量：--primary-color:#00f3ff; --secondary-color:#bc13fe;
  --bg-color:#050510; --panel-bg:rgba(10,20,40,0.85)
- body 溢出隐藏、暗底白字、无 margin
- h1 用 90deg 线性渐变（#00f3ff→#bc13fe）+ background-clip:text
- #info-panel 固定右上（top:80px,right:20px,width:280px），默认
  transform:translateX(120%) 隐藏，.active 类滑入（transition 0.3s）
- 滑块 thumb 圆形 20px、青色、box-shadow 发光；disabled 时 opacity 0.3

【3. config.js — 全部参数集中，禁止魔法数字】
export const CONFIG = {
  startYear: 2018, endYear: 2026,
  timeMode: 'monthly',            // yearly|monthly|daily|hourly，由数据自动检测
  realDataStartYear: 2025,
  layerHeight: 40,                // yearly 层 Z 间距
  monthLayerHeight: 8, dayLayerHeight: 12, hourLayerHeight: 15,
  ringRadius: { inner: 20, middle: 32, outer: 45 },
  ringProbabilities: { outer: 0.7, middle: 0.2, inner: 0.1 },
  nodeColor: 0x00f3ff, linkColor: 0x555555, timeLineColor: 0xbc13fe,
  bgColor: 0x050510,
  nodeCount: { min: 15, max: 25 },          // mock 每层节点数
  linkDistanceThreshold: 16,                // 同层连线距离阈值
  starCount: 2000, starSpread: 600,
  nodeSphere: { radius: 0.8, segments: 8 }, // 低多边形
  nodeScale: { inner: 1.4, middle: 1.0, outer: 0.6 },
  cameraPosition: { x: 60, y: 40, z: 60 },
  skillChild: {
    orbitRadius: 4.5, segments: 12,
    maxVisibleParents: 2, maxSkillsDisplay: 8, coreCount: 4,
    labelOffset: 0.75, labelScale: 3.2,
    core:      { sphereRadius: 0.5,  scale: 1.6, edgeColor: 0xffffff, edgeOpacity: 0.8 },
    secondary: { sphereRadius: 0.28, scale: 0.8, edgeColor: 0x666677, edgeOpacity: 0.25 },
  },
  skillColors: { ai:0xff9f43, lang:0x54a0ff, db:0x2ed573, devops:0x00d2d3,
                 tool:0xa29bfe, embedded:0xf0c040, default:0xffc8d6 },
  skillColorMap: { 'Python':'ai', 'PyTorch':'ai', 'Java':'lang', 'C++':'lang',
                   'MySQL':'db', 'Redis':'db', 'Docker':'devops', 'Linux':'devops',
                   'Vue':'tool', 'React':'tool', 'STM32':'embedded', /* ...可按需扩充 */ },
};
- 分类色板：研发 0x38bdf8 / 产品 0xfb7185 / 设计 0xc084fc / 运营 0xfacc15 /
  数据 0x4ade80；未知分类返回白色。getCategoryColor(category) 导出。
- RING_NAMES = { inner:'核心管理/专家', middle:'资深骨干', outer:'基础/新兴' }
- 导出 getLayerHeight()（按 timeMode 返回对应层高）、getTimelineLayers()
  （返回 [{index,year,month,day,hour,label,isReal}]，hourly 用 Date 逐小时步进，
  label 格式 'YYYY-MM-DD HH:00'；monthly 为 'YYYY-MM'；yearly 为 'YYYY 年'；
  isReal = year >= realDataStartYear）、detectTimeMode(jobs)（采样前 100 条，
  优先级 _hour→hourly、_day→daily、_month→monthly、_year→yearly，
  并据数据回填 CONFIG 起止时间）。

【4. scene.js — initScene()】
- Scene：background=0x050510；fog=FogExp2(0x050510, 0.008)
- PerspectiveCamera(60, aspect, 0.1, 1000)，位置取 CONFIG.cameraPosition
- WebGLRenderer({antialias:true, alpha:true})，setSize 全屏，
  setPixelRatio(devicePixelRatio)，domElement 挂到 #canvas-container
- OrbitControls：enableDamping=true，dampingFactor=0.05，maxDistance=200
- 灯光：AmbientLight(0xffffff, 0.6) + PointLight(0xffffff, 1) at (0,100,0)
- 返回 { scene, camera, renderer, controls, raycaster, mouse }
  （raycaster=new Raycaster()，mouse=new Vector2()）

【5. visualization.js — 3D 元素工厂，几何体/材质全部模块级单例缓存】
(a) 泛光纹理单例 getGlowTexture()：32×32 canvas，径向渐变 stops：
    0:'rgba(255,255,255,1)' 0.15:'0.9' 0.4:'0.4' 0.7:'0.05' 1:'0'，
    包成 CanvasTexture。
(b) 节点几何单例：SphereGeometry(0.8, 8, 8)。
(c) 节点材质缓存 Map<category, MeshBasicMaterial({color})>（自发光，不用光照材质）。
(d) 年轮几何单例：3 个 RingGeometry(r,r,64) 各取 EdgesGeometry（r=20/32/45）。
(e) createStarField(scene)：2000 个随机点（每坐标 (Math.random()-0.5)*600），
    PointsMaterial{color:0x888888, size:0.8, transparent, opacity:0.8}。
(f) createTimelineParticles(scene)（虫洞）：
    - 双螺旋：两臂相位差 π；每臂 600 点；半径 3；turns=max(总层数/12,1)；
      t=i/600，angle=t*turns*2π+phase，z 从 startZ=层高*0.5 线性到
      endZ=-(总层数-0.5)*层高；x=cos(angle)*3, y=sin(angle)*3。
    - 层标记环：每层 z=-i*层高 处 20 点圆环（半径 3）。
    - 合成一个 Points：PointsMaterial{color:0xffffff, size:0.9,
      map:泛光纹理, blending:AdditiveBlending, depthWrite:false,
      opacity:0.85, transparent:true}。返回该 Points（动画模块要旋转它）。
(g) createRingFloor(group, label)：3 个 LineLoop（共享年轮几何 +
    LineBasicMaterial{0x444455, transparent, opacity:0.3}），
    rotation.x=-π/2 放平；再加时间标签 Sprite：256×128 canvas 白字居中
    （字号 hourly 28 / monthly 42 / yearly 60 Bold Arial），
    SpriteMaterial{map, transparent, opacity:0.8}，
    scale 按粒度 (10,5)/(14,7)/(20,10)，position (0, 2或3或5, 0)。
(h) createNodeMeshes(nodes, group)：每节点 new Mesh(共享球几何, 分类材质)，
    position.set(node.x, node.y, 0)，scale=CONFIG.nodeScale[node.ringType]，
    把 baseScale 写回 node 并整体存入 mesh.userData={...node, nodeType:'job'}。
(i) createIntraLinks(nodes, group)（空间哈希 O(n)）：
    cellSize=linkDistanceThreshold；把节点按 (floor(x/cell),floor(y/cell))
    分桶到 Map；每节点只查自身+相邻 8 格，配对条件 j>i 且
    dx²+dy² < cell²；命中则两点 push 进数组；最后合成一个
    LineSegments（LineBasicMaterial 白色 transparent opacity 0.15）。
(j) createSkillChildNodes(parentNode, parentMesh, layerGroup)：
    - skills 超过 maxSkillsDisplay(8) 截断（保留前 4 核心 + 随后次要）。
    - 建 childGroup：position 复制父 mesh，visible=false，加入 layerGroup。
    - 第 i 个技能：angle=(i/n)*2π，cx=cos*4.5，cy=sin*4.5；
      i<4 为核心（球半径 0.5、scale 1.6、白色连线 opacity 0.8），
      否则次要（0.28、0.8、0x666677、0.25）；球体独立
      MeshBasicMaterial，颜色查 skillColorMap→skillColors；
      userData={nodeType:'skill', skillName, isCore, parentId,
      parentName, parentCategory, parentRingType, parentYear, baseScale}。
    - 每技能一条 Line（父中心→子位置）+ 一个文字标签 Sprite
      （256×64 canvas，Bold 36px，颜色同技能色，position 在子节点上方
      0.75，scale (3.2, 0.8, 1)，depthTest:false）。标签纹理按
      `${skillName}_${color}` 缓存。
    - 返回 { childGroup, childMeshes, edgeLines }；skills 为空返回 null。

【6. data.js — 节点布局（纯数据，不依赖 Three.js）】
- generateNodesForYear(year, month, day, hour)（mock）：
  count = 15~25 随机；每个节点：rand=Math.random()，
  rand>0.7→middle(半径 32±3)，rand>0.9→inner(半径 20±2)，否则
  outer(45±2.5)；angle 随机 2π；x=cos*r, y=sin*r；
  category 从 ['研发','产品','设计','运营','数据'] 随机；
  id=`node-${year}-${month||'00'}-${i}`。
- generateNodesFromRealData(year, jobs, month, day, hour)：
  先按时间字段（_year/_month/_day/_hour）过滤；再按 ringType 分桶
  （默认 outer）；每桶内 baseAngle=(i/桶内数量)*2π，
  angle=baseAngle+(Math.random()-0.5)*0.4，半径=环半径±jitter/2
  （inner jitter 4 / middle 6 / outer 5），极坐标转直角坐标；
  节点携带 id,year,name,category,ringType,x,y 及真实数据扩展字段
  company,location,salary,experience,education,description,skills,
  isRealData:true。

【7. interaction.js — initInteractions(state)】
state={layers, allMeshes, childFactoryMap, camera, renderer, raycaster,
mouse, controls, timelineParticles}，layers/allMeshes 是与 main.js
共享的数组引用（闭包捕获，外部原地突变即可同步）。
(a) 时间滑块：#time-slider input 事件 → percent→
    index=min(floor(percent/100*(可见层数-1)), 可见层数-1)；
    #current-year-display 显示该层 label；相机缓动到
    pos(40, 40, 层zPos+20)、lookAt(0,0,层zPos)。
    相机缓动 animateCamera：600ms，easeInOutQuad
    （t<0.5 ? 2t² : -1+(4-2t)t），rAF 逐帧 lerp position 与 controls.target。
(b) 年份筛选 #year-filter change：
    value='all'→全部层 visible=true、虫洞粒子显示、滑块启用、
    恢复旋转（LEFT:ROTATE/MIDDLE:DOLLY/RIGHT:PAN）、相机回 3D 视角；
    否则只显示匹配层（按 year/month/day/hour 匹配 value 格式
    YYYY / YYYY-MM / YYYY-MM-DD / YYYY-MM-DDTHH），隐藏虫洞粒子、
    禁用滑块、禁旋转（LEFT:PAN/MIDDLE:DOLLY），相机切 2D 顶视：
    distance=max(d, d/aspect)，其中 d=(outerR*1.06)/tan(fov/2 弧度)，
    相机 (0,0,层z+distance)，target (0,0,层z)。
(c) 点击（必须区分拖拽，避免 OrbitControls 误触发）：
    pointerdown 记 mouseMoved=false；pointermove 置 true；
    pointerup 时若 mouseMoved 则忽略，否则执行拾取。
    拾取池 = allMeshes.concat(活跃子节点meshes)；
    取第一个 object.parent.visible 的命中。
    命中岗位节点：懒创建实体子节点（首次点击才调 createSkillChildNodes，
    结果缓存进 Map<parentMesh, childData>），再次点击切换显隐；
    展开用 FIFO 队列，同时最多 maxVisibleParents(2) 个父节点展开，
    超出隐藏最早者；命中技能子节点→信息面板显示技能详情；
    未命中→隐藏信息面板。
(d) 悬停（rAF 节流）：mousemove 只存 pendingEvent，
    requestAnimationFrame 内统一拾取；命中新对象时旧的恢复 baseScale、
    新的放大 1.5 倍、cursor:pointer、显示信息面板；未命中恢复并隐藏面板。
(e) 信息面板 showInfoPanel(userData)：填 #panel-title/year/category/ring
    （ring 用 RING_NAMES 映射）；isRealData 时填 description、
    company/location/salary（#panel-meta 显示），skills 渲染成
    span.tag（前 coreCount 个加 .core 类）；panel.classList.add('active')。
(f) window resize：更新 camera.aspect + updateProjectionMatrix +
    renderer.setSize。
返回清理函数 { clearEntityCache, rebuildSkillList } 供视图切换调用。

【8. animation.js — startAnimation({scene,camera,renderer,controls,wormholeParticles})】
rAF 循环：controls.update()；若虫洞粒子存在则 rotation.z += 0.002；
renderer.render(scene, camera)。

【9. main.js — 启动流程（顺序必须一致）】
1. initScene()
2. 加载岗位数据（本地 ES Module 或 mock 生成 2000 条）
3. detectTimeMode(jobs) 自动检测时间粒度
4. createStarField(scene)；timelineParticles=createTimelineParticles(scene)
5. buildMainGraph：遍历 getTimelineLayers()，第 i 层：
   layerGroup.position.z=-i*层高 → 加入主容器 Group（name='graph-main'）；
   createRingFloor(group, label)；
   isReal&&有真实数据 ? generateNodesFromRealData : generateNodesForYear；
   createNodeMeshes → meshes 推入共享 allMeshes；
   每个 mesh 注册 childFactoryMap.set(mesh, {node, layerGroup})；
   createIntraLinks；
   层对象 {year,month,day,hour,label,zPos,nodes,meshes,group} 推入共享 layers。
6. 填充 #year-filter 选项（monthly 模式按年 optgroup 分组）
7. initInteractions(传入共享数组引用)
8. 隐藏 #loading；默认视图=节点数最多的层：找到 bestIdx，
   slider.value=bestIdx/(层数-1)*100 并 dispatch 'input' 事件
9. startAnimation({..., wormholeParticles: timelineParticles})

【10. 性能红线（必须遵守）】
- 几何体/材质/纹理一律模块级单例，循环内禁止 new Geometry/Material。
- 球体 segments=8（视觉无损，顶点数减少 73%）。
- 连线必须空间哈希，禁止 O(n²) 双重循环。
- 同层连线合并为单个 LineSegments（一次 draw call）。
- 技能子节点懒创建，同时最多展开 2 组。
- 目标规模：7000+ 节点 × 119 个小时级时间层流畅运行。

【11. 数据 schema】
岗位对象：{ id, name, category, ringType:'inner'|'middle'|'outer',
_year, _month, _day, _hour, company, location, salary, experience,
education, description, skills:string[] }
分类 ∈ ['研发','产品','设计','运营','数据']。
````

---

## 三、精确技术规格（复刻核对用）

### 3.1 坐标系与时间→空间映射

| 项 | 值 / 公式 |
|----|-----------|
| 层 Z 坐标 | `zPos = -i * layerHeight`（第 0 层在原点，向 -Z 延伸） |
| 层高 | yearly 40 / monthly 8 / daily 12 / hourly 15 |
| 虫洞螺旋 | 半径 3，两臂相位差 π，`turns = max(层数/12, 1)`，z 从 `层高*0.5` 到 `-(层数-0.5)*层高` |
| 层标记环 | 每层 20 点，半径 3，z = -i×层高 |
| 年轮半径 | inner 20 / middle 32 / outer 45 |
| 环层概率 | outer 0.7 / middle 0.2 / inner 0.1（mock 数据） |
| 真实数据布局 | 桶内 `baseAngle = (i/n)*2π`，角偏移 ±0.2rad，半径抖动 inner±2 / middle±3 / outer±2.5 |
| 节点缩放 | inner ×1.4 / middle ×1.0 / outer ×0.6 |

### 3.2 相机机位速查

| 场景 | position | target | 控制 |
|------|----------|--------|------|
| 初始 3D | (60, 40, 60) | (0, 0, -90) | 旋转+缩放+平移 |
| 滑块穿梭 | (40, 40, 层z+20) | (0, 0, 层z) | 同上 |
| 2D 顶视单层 | (0, 0, 层z+distance) | (0, 0, 层z) | 禁旋转，左键平移 |

**2D 距离公式**（所有 2D 机位共用）：
```
vFovHalf = (camera.fov / 2) * π / 180
dist     = (outerR * 1.06) / tan(vFovHalf)
distance = max(dist, dist / aspect)      // 保证窄屏也能装下外环
```

### 3.3 关键算法伪代码

**空间哈希连线（O(n)）**
```
cell = threshold (16)
for each node: grid["fx,fy"].push({node, idx})   // fx=floor(x/cell)
for each node i:
  for dx,dy in [-1,0,1]²:
    for {other, j} in grid[fx+dx, fy+dy]:
      if j <= i: continue
      if (x-ox)² + (y-oy)² < cell²: addSegment(node, other)
```

**滑块 → 层索引**
```
index = min(floor(percent/100 * (visibleCount-1)), visibleCount-1)
```

**点击与拖拽区分**
```
pointerdown → mouseMoved=false
pointermove → mouseMoved=true
pointerup   → if (!mouseMoved) handleClick(e)
```

**悬停节流**
```
mousemove: pendingEvent = e; if (!rafId) rafId = rAF(() => { processHover(pendingEvent); rafId=null })
命中: scale = baseScale*1.5, cursor=pointer, 显示面板
未命中: 恢复 baseScale, cursor=default, 隐藏面板
```

**相机缓动（easeInOutQuad，600ms）**
```
t = raw<0.5 ? 2*raw² : -1+(4-2*raw)*raw
camera.position.lerpVectors(start, targetPos, t)
controls.target.lerpVectors(startTarget, lookAt, t)
```

**虫洞自转**：每帧 `wormholeParticles.rotation.z += 0.002`

### 3.4 共享状态模式（视图可扩展的关键）

`main.js` 拥有三个数组，`interaction.js` 通过闭包引用捕获：
- `sharedLayers` — `[{year,month,day,hour,label,zPos,nodes,meshes,group}]`
- `sharedMeshes` — 全部节点 Mesh 的扁平数组
- `sharedChildFactoryMap` — `Map<Mesh, {node, layerGroup}>` 懒创建工厂

切换视图时**原地突变**（`length=0` 后 `push(...)`），绝不重新赋值，交互闭包零成本感知新数据。

### 3.5 缓存清单（模块级单例）

| 缓存 | 内容 |
|------|------|
| `_nodeGeometry` | SphereGeometry(0.8, 8, 8) |
| `_nodeMaterials` | Map<分类, MeshBasicMaterial> |
| `_glowTexture` | 32×32 径向渐变 CanvasTexture |
| `_ringGeometries` | 3 个 EdgesGeometry（20/32/45） |
| `_ringLineMaterial` | LineBasicMaterial 0x444455 op=0.3 |
| `_intraLinkMaterial` | LineBasicMaterial 白色 op=0.15 |
| `_childCoreGeom` / `_childSecondaryGeom` | 技能子节点球体 0.5 / 0.28 |
| `_skillLabelTextures` | Map<`name_color`, CanvasTexture> |

### 3.6 色板

| 用途 | 颜色 |
|------|------|
| 研发 / 产品 / 设计 / 运营 / 数据 | `#38bdf8` `#fb7185` `#c084fc` `#facc15` `#4ade80` |
| 技能：AI/语言/数据库/DevOps/工具/嵌入式/默认 | `#ff9f43` `#54a0ff` `#2ed573` `#00d2d3` `#a29bfe` `#f0c040` `#ffc8d6` |
| UI 主色 / 辅色 / 背景 | `#00f3ff` `#bc13fe` `#050510` |
| 年轮线 / 同层连线 / 演化连线 | `#444455`(op.3) / 白(op.15) / `#bc13fe`(op.3) |

---

## 四、验收清单（复刻后逐条核对）

- [ ] 页面加载后看到星空背景 + 中央白色双螺旋泛光虫洞 + 沿 Z 轴排列的发光圆环层
- [ ] 虫洞粒子持续绕 Z 轴缓慢自转
- [ ] 每层三个同心圆环 + 层中央白色时间标签
- [ ] 节点按分类着色、按环层有不同大小，落在对应环带附近
- [ ] 同层近距节点间有淡白色连线
- [ ] 拖动时间滑块，相机缓动穿梭到对应层，顶部时间显示同步更新
- [ ] 年份筛选选择具体时间点：切换为 2D 顶视单层、禁用旋转、隐藏虫洞；选"全部年份"恢复 3D
- [ ] 悬停节点放大 1.5 倍 + 手型光标 + 右侧信息面板滑出
- [ ] 点击岗位节点展开技能卫星子节点（核心 4 个大而亮，次要小而暗，带彩色文字标签）；再点收起；展开第 3 个父节点时最早展开的自动收起
- [ ] 拖拽旋转视角不会误触发节点点击
- [ ] 窗口缩放时画面自适应
- [ ] 7000 节点规模下交互流畅（Chrome DevTools Performance 无长任务掉帧）

---

## 五、常见复刻错误预警

1. **`node --check` 不能验证 ESM**：`.js` 文件按 CommonJS 解析，查不出重复 `const`、TDZ 等 ESM 错误；需复制为 `.mjs` 再检查，或直接在浏览器控制台验证。
2. **OrbitControls 与点击冲突**：必须用 pointerdown/pointermove/pointerup 三事件组合区分拖拽，否则每次旋转视角都会误展开节点。
3. **循环内 new 材质/几何体**：7000 节点会直接卡死，务必使用模块级缓存。
4. **RingGeometry 直接用会有填充面**：要取 `EdgesGeometry` 得到纯线框圆环。
5. **虫洞粒子 depthWrite 必须为 false** 且用 AdditiveBlending，否则泛光会遮挡节点。
6. **共享数组重新赋值会导致交互失灵**：必须 `length=0; push(...)` 原地突变。
7. **2D 顶视相机距离要考虑 aspect**：窄屏时 `dist/aspect` 补偿，否则外环被裁剪。
