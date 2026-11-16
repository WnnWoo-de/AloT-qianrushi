# AGENTS.md

本文件约束 Codex/自动化助手在本仓库中的工作方式。仓库是 FAST-LIVO2 创新路线下的 2D 双车 + Anchor-UWB 后端因子图数值仿真项目，不是 ROS 驱动、标定、实车部署或完整 FAST-LIVO2 工程仓库。

## 项目事实

- 当前仓库主体是一组按研究版本编号保存的单文件 Python 仿真脚本：`sim2d_mvp_1.0.py` 到 `sim2d_mvp_3.2.3.py`。
- 后处理/出图脚本包括 `make_triptych_3_2_2.py`、`make_triptych_3_2_3.py`、`make_summary_table_3_2_3.py`、`make_method_compare_3_2_3.py`。
- 结果与生成物主要放在 `figs/`，其中 `figs/summary_table_3_2_3/` 含当前方法的汇总 CSV、Markdown 表和 PNG 表。
- 当前目录未检测到有效 Git 仓库；不要假设可以提交、分支、回滚或查看历史。若后续出现 `.git`，先重新运行 `git status --short` 再做判断。
- 主要运行依赖来自脚本导入：`numpy`、`scipy`、`matplotlib`；`make_triptych_3_2_2.py` 还用 `PIL`，`figs/summary_table_3_2_3/plot_summary_figure.py` 用 `pandas`。

## 专利正文关键信息

用户提供的专利正文 Markdown 为 `一种基于UWB弱全局约束与可靠性感知鲁棒融合的双车异构协同建图方法及系统-正文.md`。该文件来自专利技术书/PDF文本层转换，公式和特殊数学符号可能存在转码异常；涉及公式、变量和函数实现时，应优先对照 `sim2d_mvp_3.2.3.py` 中的实际代码和用户确认后的专利正文，不要从乱码公式中臆造细节。

不要把专利正文中的发明人身份证号、联系方式、代理机构联系人等申报个人信息写入本仓库脚本、图注、公开说明或生成物。AGENTS.md 只保留技术上下文。

专利技术主题是“一种基于 UWB 弱全局约束与可靠性感知鲁棒融合的双车异构协同建图方法及系统”，技术领域为传感器融合与因子图优化。专利表述中的双车异构含义是：第一车辆可对应激光雷达里程计或激光雷达-惯性里程计，第二车辆可对应视觉里程计、视觉-惯性里程计或 RGB-D 里程计；UWB 锚点为环境中坐标已知的绝对参考节点，UWB 测距为车辆标签到锚点的飞行时间测距。

专利正文的核心问题表述：

- 室内 GPS 不可用时，单车里程计存在累积漂移，双车融合缺少统一全局观测会导致相对偏转和尺度失配。
- UWB 可提供弱全局约束，但受 LOS/NLOS 切换、多径和部分锚点可见影响，测距质量波动明显。
- 激光雷达在长走廊、开阔区域等几何退化环境中横向约束不足，里程计输出可能退化。
- 现有固定鲁棒核或独立校正方式缺少对里程计与 UWB 观测质量动态变化的统一感知和在线调节。

专利方法流程以权利要求和摘要中的 S1-S8 为主：

- S1：获取第一车辆里程计、第二车辆里程计、UWB 锚点坐标和 UWB 测距数据，构建基础观测集合。
- S2：构建统一后端因子图，包含第一车辆里程计因子、第二车辆里程计因子、UWB 测距因子和位姿先验因子；执行第一阶段基础优化得到初始双车轨迹。
- S3：基于 Stage-0 初始轨迹和观测数据生成里程计模态与 UWB 模态的诊断可靠性序列。
- S4：将诊断可靠性序列作为先验观测，引入图内显式可靠性状态变量，并通过 Sigmoid 或其他有界映射约束到 `[s_min, 1]`。
- S5：构建包含观测残差项、诊断可靠性先验项和可靠性状态时间平滑项的联合优化代价函数，使用可靠性状态自适应调节各模态约束贡献。
- S6：针对同一时刻单个 UWB 可靠性状态对应多条 UWB 测距边的情况，按该时刻 UWB 测距边数量的平方根增强 UWB 可靠性诊断先验项权重，抑制 UWB 可靠性状态异常塌缩。
- S7：对双车轨迹状态和各模态可靠性状态进行第二阶段联合优化，得到优化后的双车统一轨迹和时变可靠性状态序列。
- S8：根据优化后的双车统一轨迹，为双车局部地图或局部点云的统一坐标变换、拼接或增量更新提供位姿基准。

注意：专利正文的具体实施方式中局部标题可能把第二阶段联合优化和地图输出写成 S6/S7；后续整理专利正文或图注时，应以权利要求和摘要中的 S1-S8 主线统一编号，避免图1流程图和正文编号不一致。

专利系统模块包括：数据获取模块、因子图构建模块、第一阶段优化模块、可靠性诊断模块、可靠性状态建模模块、联合优化模块、平衡加权模块和输出模块。绘制系统或流程相关图时，模块名称应与这些表述保持一致。

专利核心机制与当前代码的对应关系：

- “统一后端因子图”对应当前仿真中的双车位姿节点、两类里程计因子、Anchor-UWB 测距因子和首帧位姿先验。
- “第一阶段基础优化”对应 `run_case()` 中 Stage-0：不引入图内显式可靠性状态变量，用于生成诊断可靠性所需的初始轨迹。
- “诊断可靠性序列”对应 `s_hat_lio`、`s_hat_rtab`、`s_hat_uwb1`、`s_hat_uwb2`；里程计诊断来自局部运动一致性/方差比，UWB 诊断来自 Stage-0 轨迹上的测距残差聚合，并可结合可见锚点数量修正。
- “图内显式可靠性状态变量”对应 `s_lio_opt`、`s_rtab_opt`、`s_uwb1_opt`、`s_uwb2_opt`，由原始变量经 `raw_to_reliability()` 映射到 `[RELIABILITY_FLOOR, 1]`。
- “可靠性状态时间平滑项”对应 `SIGMA_S_SMOOTH_LIO`、`SIGMA_S_SMOOTH_RTAB`、`SIGMA_S_SMOOTH_UWB` 控制的相邻时刻可靠性变化约束。
- “UWB 测距边数量平方根平衡加权”对应 `UWB_PRIOR_BALANCE_MODE = "sqrt_count"`，用于增强同一时刻多条 UWB 边共享同一个 UWB 可靠性状态时的诊断先验约束。

专利正文中的示例场景包括长走廊退化场景，以及 UWB 部分锚点可见且存在 NLOS 干扰场景。当前代码已经能直接支撑“UWB部分锚点可见 + NLOS”的 `uwb_only` 场景；长走廊退化场景尚未在当前仓库中实现，不能用现有椭圆轨迹场景直接冒名替代。

专利写作和出图时应保持以下边界：

- 本仓库只能直接证明数值仿真结果；不要把仿真图描述为实车、ROS、硬件部署或完整 FAST-LIVO2 系统实验。
- 不要宣称性能提升、稳定性提升、RMSE 或最大偏差，除非来自实际运行命令和输出文件。
- 图1至图3属于方法/模型/映射机理示意；图4至图9属于仿真实验或时序结果示意，应在图注中区分。

## 研究版本语义

版本号代表研究问题边界，不只是代码快照。修改时必须先确认自己是在做方法学变化、实验场景补齐、工程接口重构，还是纯绘图/汇总调整。

- `1.3`：LOS + 部分可见 baseline，是 2.x 与 3.x 的共同对照底座。
- `2.0`：UWB mixed NLOS，无鲁棒机制。
- `2.1`：在 2.0 基础上加入 UWB Huber robust loss。
- `2.2`：UWB-only switchable constraints，每条 UWB 边有显式开关。
- `3.0`：oracle-weighted unified graph，可靠性 `s` 由退化标签/仿真真值在图外给定。
- `3.1.3`：diagnostic-weighted unified graph 的冻结点，用可观测诊断量构造 `s_hat`，再做 weighted solve。
- `3.2`：graph-internal reliability state 初版，保留为 ablation/base。
- `3.2.1`：当前方法学正式点，加入 UWB prior balance 与更强 reliability state prior/smoothness。
- `3.2.2`：不是方法学跃迁；在 3.2.1 基础上补充 `normal_occ` 标准场景。
- `3.2.3`：不是方法学跃迁；在 3.2.2 基础上新增 `run_case()` 可调用接口，并统一单场景输出路径/标题版本号。默认把它作为当前可运行入口，但方法学表述应写为“3.2.1 正式方法的 3.2.3 工程重构实现”。

## 当前入口

优先使用 `sim2d_mvp_3.2.3.py` 做当前方案实验、批量统计和论文级作图，除非任务明确要求复现实验版本树中的旧版本。

`sim2d_mvp_3.2.3.py` 提供：

- `VERSION = "3.2.3"`
- `DEGRADATION_CASE = "normal_occ"` 默认场景
- `run_case(case_name=None, show=True, save_fig=True, return_dict=True, solver_verbose=2)`
- `get_single_case_figure_path(case_name=None, baseline_mode=None)`

有效场景名包括：

- `normal_occ`：正常遮蔽/部分可见 + LOS + 无 odom 退化。
- `uwb_only`：仅 UWB NLOS 退化。
- `lio_only`：仅 Robot1 odom/LIO 退化。
- `rtab_only`：仅 Robot2 odom/RTAB 退化。
- `dual_lio_uwb`：Robot1 odom + UWB 同时退化。
- `dual_rtab_uwb`：Robot2 odom + UWB 同时退化。
- `mixed_all`：Robot1 odom、Robot2 odom、UWB 全部混合退化。

不要把 `normal_occ` 改写成“完全理想全可见”。它在代码注释中的定义是部分可见/正常遮蔽，但没有额外传感器退化。

## 专利附图补齐计划

当前专利正文的附图说明引用图1至图9，摘要附图指定图1。后续补图时应保持图号、图名、正文引用和输出文件一一对应，不要在未修改专利正文的情况下删减或重排图号。

建议将专利附图输出到新的专用目录，例如 `figs/patent_figures/`，避免覆盖 `figs/` 中已有研究版本结果。若新增出图脚本，优先命名为 `make_patent_figures_3_2_3.py` 或按图号拆分为专利专用脚本；不要直接覆盖现有 `make_triptych_3_2_3.py`、`make_method_compare_3_2_3.py` 的论文实验语义。

当前专利附图状态（2026-06-08）：

- 图1、图2、图3、图8、图9 已完成绘制，可作为第一阶段已完成项。图1至图3仍按方法/模型/映射机理示意理解；图8和图9仍按 `uwb_only` 数值仿真场景理解。
- 图8和图9的技术来源应保持为同一次 `run_case("uwb_only", show=False, save_fig=False, return_dict=True, solver_verbose=0)` 运行结果；若后续重新出图，应继续避免不同随机种子或不同运行结果混搭。
- 图4、图5、图6、图7 尚未完成。下一步工作应聚焦长走廊退化场景补齐，而不是复用 `lio_only`、`mixed_all` 或 `odom_only` 等现有椭圆轨迹场景改名。
- 已新增第一阶段出图脚本 `make_patent_figures_3_2_3.py`，其输出目录为 `figs/patent_figures/`。若用户已手工重绘其中部分图，应以用户确认后的正式图稿为准，脚本输出可作为技术参考或备份。

第一阶段优先绘制不依赖新增仿真场景的图：

- 图1 方法流程图：根据专利步骤 S1-S8 绘制，作为摘要附图候选。该图是方法流程示意，不需要运行仿真。
- 图2 统一后端因子图模型结构示意图：根据 `sim2d_mvp_3.2.3.py` 中双车位姿节点、里程计因子、UWB测距因子、位姿先验因子、图内可靠性状态、诊断先验项和时间平滑项绘制。该图是模型结构示意，不应声称来自数值实验。
- 图3 诊断可靠性映射函数曲线示意图：可直接基于 `map_odom_error_series_to_reliability()`、`map_uwb_error_series_to_reliability()` 和 `raw_to_reliability()` 的映射关系采样绘制。若只画专利示意曲线，应标注为“映射关系示意”，不要当作实验结果。
- 图8 UWB部分锚点可见且存在NLOS干扰场景轨迹对比图：可直接调用 `run_case("uwb_only", show=False, save_fig=False, return_dict=True, solver_verbose=0)` 获取 `gt1`、`gt2`、`init1`、`init2`、`est1`、`est2`、`anchors` 后重绘。
- 图9 图8对应的UWB可靠性状态曲线：与图8使用同一次 `uwb_only` 运行结果，绘制 `s_hat_uwb1`、`s_hat_uwb2`、`s_uwb1_opt`、`s_uwb2_opt` 随时间变化。不要用不同随机种子或不同运行结果混搭图8和图9。

第二阶段补齐长走廊退化相关图：

- 图4 现有仅依赖里程计约束方法在长走廊退化场景下的轨迹对比图。
- 图5 本方法在长走廊退化场景下的轨迹对比图。
- 图6 图4对应的双车轨迹相对误差随时间变化曲线。
- 图7 图5对应的双车轨迹相对误差随时间变化曲线。

当前仓库没有 `long_corridor` / “长走廊”场景，`sim2d_mvp_3.2.3.py` 的真值轨迹由椭圆参数生成。因此，不要把现有 `lio_only`、`mixed_all` 或 `odom_only` 结果直接命名为“长走廊退化场景”。若要严格支撑图4至图7，应先新增受控的长走廊仿真问题。

长走廊场景建议作为专利专用补充实验实现，避免静默改变 3.2.3 当前研究入口的语义。可选实现方式：

- 首选：新增专利专用脚本，在脚本内复用 `sim2d_mvp_3.2.3.py` 的优化器、残差函数、可靠性映射和绘图风格，单独生成长走廊真值轨迹、锚点布设、里程计退化窗口和UWB测距数据。
- 备选：在用户明确要求后，受控扩展 `sim2d_mvp_3.2.3.py` 的场景枚举，新增 `long_corridor`。这属于实验场景定义变化，必须在汇报中明确说明，不得把它描述为 3.2.3 原有场景。

图4至图7的对照关系应固定同一长走廊真值、同一随机种子、同一锚点布设和同一退化窗口，只改变后端方法：

- 图4/图6：现有方法，优先实现为仅里程计约束或不使用UWB弱全局约束的基线。
- 图5/图7：本方法，使用 3.2.1 正式方法的 3.2.3 工程重构实现，即图内可靠性状态 + UWB prior balance + reliability prior/smoothness。

绘制图6和图7前必须先固定“相对误差”定义。推荐使用双车相对位移误差：

```text
e_rel(k) = || (p2_est(k) - p1_est(k)) - (p2_gt(k) - p1_gt(k)) ||_2
```

如果改用单车位置误差、相对位姿误差或RMSE滑窗曲线，必须同步更新图题、图注和专利正文描述，避免“相对误差”含义不一致。

专利附图生成后的最低验证要求：

- 文档/机理图：重新打开输出 PNG，确认图号、中文标注、箭头和节点关系清晰。
- 仿真图：记录命令、场景、随机种子、方法配置、输出路径和生成时间。
- 图8/图9：确认来自同一次 `uwb_only` 运行结果。
- 图4至图7：确认长走廊场景不是由 `lio_only`、`mixed_all` 等现有椭圆轨迹场景冒名替代。
- 若附图用于正式提交，优先另存一版黑白/灰度、线条清晰、少依赖颜色区分的版本。

## 修改规则

- 修改文件前，先说明要改哪些文件、为什么改、是否会改变实验语义。
- 不要静默修改实验语义、指标定义、有效性判据、随机种子、退化窗口、噪声/偏置参数、可靠性先验、平滑强度或场景定义。
- 尤其谨慎对待这些关键项：`BASELINE_MODE`、`UWB_ERROR_MODE`、`NLOS_PROB`、`NLOS_BIAS_*`、`SEED_*`、`DEGRADATION_CASE`、`LIO_DEGRADE_WINDOWS`、`RTAB_DEGRADE_WINDOWS`、`RELIABILITY_FLOOR`、`UWB_PRIOR_BALANCE_MODE`、`SIGMA_S_PRIOR_*`、`SIGMA_S_SMOOTH_*`、`STAGE0_MAX_NFEV`、`STAGE2_MAX_NFEV`。
- 若确实需要改变上述内容，必须在答复中明确说明它会影响哪些版本比较或图表结论。
- 保留历史版本脚本，不要直接把旧版本改成新方法。新研究问题应新增版本文件或在用户明确要求时做受控补丁。
- 不要删除、重命名或覆盖 `figs/` 中已有结果，除非用户明确要求重新生成对应结果。
- 不要编辑 `__pycache__/`。
- 本仓库中文注释较多，读写文件时使用 UTF-8。PowerShell 查看中文时可先设置：

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
```

## 常用命令

语法检查：

```powershell
python -m py_compile sim2d_mvp_3.2.3.py make_triptych_3_2_3.py make_summary_table_3_2_3.py make_method_compare_3_2_3.py
```

当前方案单场景运行：

```powershell
python sim2d_mvp_3.2.3.py
```

生成 3.2.3 干净版三联轨迹图：

```powershell
python make_triptych_3_2_3.py --src .\sim2d_mvp_3.2.3.py --out .\figs\triptych_3.2.3_clean_normal_lio_mixed.png
```

生成当前方法汇总表：

```powershell
python make_summary_table_3_2_3.py --src .\sim2d_mvp_3.2.3.py --out-dir .\figs\summary_table_3_2_3 --quiet
```

快速 smoke test，避免长时间批量运行：

```powershell
python make_summary_table_3_2_3.py --src .\sim2d_mvp_3.2.3.py --out-dir .\figs\summary_table_3_2_3_smoke --scenes normal_occ --num-seeds 1 --stage0-nfev 2 --stage2-nfev 2 --no-png --quiet
```

单场景三方法对照图：

```powershell
python make_method_compare_3_2_3.py --src .\sim2d_mvp_3.2.3.py --scene mixed_all --out .\figs\method_compare_mixed_all_2_0_2_1_3_2_3.png
```

## 验证要求

- 文档改动：至少重新读取目标文件，确认内容落盘且中文编码正常。
- 脚本改动：至少运行 `python -m py_compile` 覆盖被改脚本。
- 影响当前入口或接口时：至少跑一次 `run_case()` 或上面的 `summary_table_3_2_3_smoke`。
- 影响图表输出时：重新生成对应 PNG/CSV/Markdown，并检查输出路径和文件时间。
- 影响实验结论时：不要只跑单 seed 后宣称性能改善；必须说明 seed 数、场景、指标、阈值、命令和输出文件。

## 汇报规范

- 区分“代码确认事实”“从版本文档得出的背景”“当前假设”和“尚未验证结论”。
- 引用项目结论时写明对应文件或命令输出，例如 `sim2d_mvp_3.2.3.py` 顶部注释、`run_case()`、`figs/summary_table_3_2_3/summary_table.md`。
- 不要凭代码结构推断性能提升；性能、稳定性、RMSE、最大偏差必须来自实际输出。
- 若依赖缺失、求解耗时过长或环境不能运行，直接说明未完成验证，不要编造结果。
