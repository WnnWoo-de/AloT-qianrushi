# ============================================================
# sim2d_mvp_2.1
# 2D 双车 + Anchor-UWB 后端数值仿真（NLOS + UWB鲁棒核版）
#
# 【本版本目标】
# 在 2.0 的 NLOS 受损基线基础上，
# 引入仅作用于 UWB 因子的鲁棒处理，
# 用于验证：
# 1) 当一部分 anchor-range 测量带有 NLOS 正偏置时，
#    仅通过 UWB 因子的鲁棒核，是否就能显著缓解后端估计退化；
# 2) 在不引入 switchable constraints、异常剔除、
#    统一可靠性建模的前提下，简单鲁棒核的改进上限有多大；
# 3) 为后续更强的鲁棒图优化与可靠性建模提供中间对照版本。
#
# ------------------------------------------------------------
# 【本版本新增能力】
# 1. 保留 2.0 的 LOS / NLOS 混合测距模型；
# 2. 保留 anchor 部分可见模型；
# 3. 新增仅作用于 UWB 因子的 Huber 鲁棒核；
# 4. 鲁棒核作用在白化后的 UWB 残差上，
#    即先按 sigma_uwb 归一化，再判断是否降权；
# 5. 终端输出中新增鲁棒配置：
#    - 是否启用 UWB 鲁棒
#    - 鲁棒核类型
#    - 鲁棒阈值（sigma 域 / 米制阈值）
#
# ------------------------------------------------------------
# 【本版本仿真的内容】
# 1. 仿真二维世界中的两台机器人真值轨迹
# 2. 仿真两台机器人的局部 odom 测量（高斯噪声 + 固定偏置）
# 3. 仿真两台机器人到 anchors 的 UWB 测距
# 4. 支持 anchor LOS 部分可见
# 5. 支持 UWB LOS / NLOS 混合测距
# 6. 后端优化融合：
#    - Robot1 odom
#    - Robot2 odom
#    - Robot1 到 anchors 的 UWB range
#    - Robot2 到 anchors 的 UWB range
#    - Robot1 第一帧全局强先验
#    - Robot2 可选弱先验 / 无先验
# 7. 仅对 UWB range 因子施加鲁棒核，
#    odom 与先验仍保持普通二次项
# 8. 输出优化前后 RMSE，并绘制轨迹图
#
# ------------------------------------------------------------
# 【本版本鲁棒处理的设计】
# 1. 鲁棒对象：
#    仅 UWB anchor-range 因子
# 2. 鲁棒前残差：
#    e_uwb = (r_pred - r_meas) / sigma_uwb
# 3. 鲁棒核：
#    当前实现为 Huber
# 4. 阈值解释：
#    delta 以“白化后的 sigma 倍数”给出，
#    例如 delta = 2.0 表示
#    |r_pred - r_meas| > 2 * sigma_uwb 时开始降权
# 5. 设计动机：
#    NLOS 测量通常表现为正偏置大残差，
#    其影响应被抑制；
#    LOS 正常测量应尽量保留二次项精度
#
# ------------------------------------------------------------
# 【本版本考虑到的误差/不完美因素】
# 1. Robot1 odom 高斯噪声
# 2. Robot1 odom 固定偏置
# 3. Robot2 odom 高斯噪声
# 4. Robot2 odom 固定偏置
# 5. UWB LOS 高斯测距噪声
# 6. LOS 条件下 anchor 观测缺失
# 7. UWB NLOS 正偏置
# 8. UWB 因子在后端仅具备有限鲁棒能力，
#    并未显式识别或关闭坏边
#
# ------------------------------------------------------------
# 【本版本仍未考虑的内容】
# 1. switchable constraints
# 2. 基于残差的一致性检测与异常剔除
# 3. UWB / LIO / VIO 统一可靠性建模
# 4. 车车相对约束
# 5. 时间偏置 Δt
# 6. 原始相机 / 雷达 / IMU 数据与地图生成
#
# ------------------------------------------------------------
# 【本版本意义】
# 本版本是“有 NLOS，且后端已具备基础鲁棒能力”的中间版本。
# 它应优于 2.0 的无鲁棒基线，
# 但通常仍劣于 1.3 的纯 LOS 基线。
# 该版本用于说明：
# 简单鲁棒核能够有效缓解 NLOS 破坏，
# 但尚不足以完全替代更强的鲁棒图优化与可靠性建模。
# ============================================================
import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares


# 轨迹长度
NUM_STEPS_1 = 60
NUM_STEPS_2 = 60

# Anchor 坐标（世界系）
ANCHORS = np.array([
    [0.0, 0.0],
    [10.0, 0.0],
    [10.0, 8.0],
    [0.0, 8.0]
])

# Robot1 真值轨迹参数
GT1_CENTER_X = 4.0
GT1_CENTER_Y = 4.0
GT1_RADIUS_X = 2.5
GT1_RADIUS_Y = 1.5
GT1_PHASE = 0.0

# Robot2 真值轨迹参数
GT2_CENTER_X = 5.2
GT2_CENTER_Y = 3.0
GT2_RADIUS_X = 2.0
GT2_RADIUS_Y = 1.2
GT2_PHASE = 0.5

# Robot1 odom 测量误差参数
ODOM1_SIGMA_XY = 0.03
ODOM1_SIGMA_YAW = 0.01
ODOM1_BIAS_XY = (0.004, -0.002)
ODOM1_BIAS_YAW = 0.0015

# Robot2 odom 测量误差参数
ODOM2_SIGMA_XY = 0.04
ODOM2_SIGMA_YAW = 0.015
ODOM2_BIAS_XY = (0.006, 0.003)
ODOM2_BIAS_YAW = -0.002

# UWB LOS 测距误差参数
UWB_SIGMA_R = 0.15

# 优化中使用的残差权重参数（对应标准差）
SIGMA_PRIOR_XY = 0.02
SIGMA_PRIOR_YAW = 0.02
SIGMA_ODOM_XY = 0.05
SIGMA_ODOM_YAW = 0.03
SIGMA_UWB = UWB_SIGMA_R

# =========================
# 1.2 版新增：更真实的先验设置
# =========================

# Robot2 的优化初值（注意：这是 initial guess，不是先验约束）
# 它故意不等于 gt2[0]，表示车2一开始并不知道自己的真实全局位置
ROBOT2_INIT_GUESS = np.array([1.0, 1.0, 0.2])

# 是否给 Robot2 一个很弱的先验
# 1.2 严格版建议设为 False
USE_ROBOT2_WEAK_PRIOR = False

# 如果你将来想测试“车2有一个很弱的粗先验”，可以打开上面的开关，
# 并使用下面两个参数
SIGMA_WEAK_PRIOR2_XY = 5.0
SIGMA_WEAK_PRIOR2_YAW = 1.5



# =========================
# 1.3 版新增：baseline / 消融开关
# =========================

# 可选模式：
# 1) "odom_only"
# 2) "dual_prior_all_anchors"
# 3) "single_prior_all_anchors"
# 4) "single_prior_partial_anchors"
BASELINE_MODE = "single_prior_partial_anchors"

# 是否启用 UWB（由 baseline_mode 自动决定，通常不手动改）
# 这里只保留给你调试时备用
FORCE_USE_UWB = None   # None 表示跟随 BASELINE_MODE；True/False 表示强制覆盖



# 部分可见时，每个时刻可见 anchor 数范围
MIN_VISIBLE_ANCHORS = 2
MAX_VISIBLE_ANCHORS = 4




# =========================
# 2.0 版新增：NLOS 配置
# =========================

# UWB 测量误差模式：
# "los"        -> 纯 LOS（即 1.3 行为）
# "mixed_nlos" -> LOS + NLOS 混合
UWB_ERROR_MODE = "mixed_nlos"

# 每条“可见的”UWB 测量成为 NLOS 的概率
NLOS_PROB = 0.30

# NLOS 正偏置大小（单位：m）
# 推荐先做中等强度，不要一上来太极端
NLOS_BIAS_MEAN = 1.2
NLOS_BIAS_STD = 0.35

# 为避免出现负偏置或过大偏置，做截断
NLOS_BIAS_MIN = 0.4
NLOS_BIAS_MAX = 2.5

# =========================
# 2.0 版新增：可重复随机源
# 目的：让 1.3 / 2.0 在同一可见性 realization 下严格对比
# =========================
SEED_MAIN = 42          # 保留给 odom 等未拆分随机项
SEED_VIS_R1 = 1001
SEED_VIS_R2 = 1002
SEED_UWB_LOS_R1 = 2001
SEED_UWB_LOS_R2 = 2002
SEED_UWB_NLOS_R1 = 3001
SEED_UWB_NLOS_R2 = 3002



# =========================
# 2.1 版新增：UWB 鲁棒处理配置
# 说明：
# - 只对 UWB 因子做鲁棒核
# - odom / prior 保持普通二次项
# =========================
USE_ROBUST_UWB = True

# 当前先实现 Huber
ROBUST_KERNEL = "huber"

# Huber 阈值，单位不是米，而是“白化后的 sigma 倍数”
# delta = 2.0 表示：|r_pred-r_meas| > 2*sigma_uwb 时开始降权
ROBUST_DELTA_UWB = 2.0



# =========================
# 基础工具函数
# =========================
def wrap_angle(theta):
    """将角度限制到 [-pi, pi]"""
    return (theta + np.pi) % (2 * np.pi) - np.pi


def pose_compose(pose, delta):
    """
    2D位姿复合
    pose:  [x, y, yaw]
    delta: [dx_body, dy_body, dyaw]
    """
    x, y, yaw = pose
    dx, dy, dyaw = delta

    c = np.cos(yaw)
    s = np.sin(yaw)

    x_new = x + c * dx - s * dy
    y_new = y + s * dx + c * dy
    yaw_new = wrap_angle(yaw + dyaw)

    return np.array([x_new, y_new, yaw_new])


def relative_pose(pose_i, pose_j):
    """
    根据世界系下两个位姿，计算 i->j 的相对位姿（以 i 的 body 系表示）
    """
    xi, yi, thi = pose_i
    xj, yj, thj = pose_j

    dx = xj - xi
    dy = yj - yi

    c = np.cos(thi)
    s = np.sin(thi)

    dx_body = c * dx + s * dy
    dy_body = -s * dx + c * dy
    dth = wrap_angle(thj - thi)

    return np.array([dx_body, dy_body, dth])


def sample_truncated_gaussian(mean, std, vmin, vmax, rng):
    """
    从截断高斯中采样，确保偏置为正且落在合理范围内
    """
    for _ in range(100):
        x = rng.normal(loc=mean, scale=std)
        if vmin <= x <= vmax:
            return x
    return np.clip(mean, vmin, vmax)


def generate_visibility_schedule(num_steps, num_anchors,
                                 visibility_mode="all",
                                 min_visible=2,
                                 max_visible=4,
                                 rng_vis=None):
    """
    预生成每一帧的可见 anchor 集合。
    这样 1.3 和 2.0 就能复用同一套 visibility realization。
    """
    if rng_vis is None:
        rng_vis = np.random.default_rng()

    visible_ids_per_step = []

    for _ in range(num_steps):
        if visibility_mode == "all":
            visible_ids = np.arange(num_anchors, dtype=int)

        elif visibility_mode == "partial_random":
            max_visible_eff = min(max_visible, num_anchors)
            min_visible_eff = min(min_visible, max_visible_eff)
            n_visible = rng_vis.integers(min_visible_eff, max_visible_eff + 1)
            visible_ids = rng_vis.choice(num_anchors, size=n_visible, replace=False)
            visible_ids = np.array(visible_ids, dtype=int)

        else:
            raise ValueError(f"Unknown visibility_mode: {visibility_mode}")

        visible_ids_per_step.append(visible_ids)

    return visible_ids_per_step

# =========================
# 生成两车真值轨迹
# =========================
def generate_truth_traj(center_x, center_y, radius_x, radius_y, phase, N):
    traj = []
    for k in range(N):
        t = 2.0 * np.pi * k / N + phase
        x = center_x + radius_x * np.cos(t)
        y = center_y + radius_y * np.sin(t)

        t2 = 2.0 * np.pi * ((k + 1) % N) / N + phase
        x2 = center_x + radius_x * np.cos(t2)
        y2 = center_y + radius_y * np.sin(t2)
        yaw = np.arctan2(y2 - y, x2 - x)

        traj.append([x, y, yaw])

    return np.array(traj)


# =========================
# 模拟里程计测量
# =========================
def simulate_odom(traj, sigma_xy=0.03, sigma_yaw=0.01,
                  bias_xy=(0.0, 0.0), bias_yaw=0.0):
    """
    输入真值轨迹，输出相邻帧 odom 测量
    """
    zs = []
    for k in range(len(traj) - 1):
        z = relative_pose(traj[k], traj[k + 1]).copy()

        # 加系统偏置（让漂移更明显）
        z[0] += bias_xy[0]
        z[1] += bias_xy[1]
        z[2] += bias_yaw

        # 加高斯噪声
        z[0] += np.random.randn() * sigma_xy
        z[1] += np.random.randn() * sigma_xy
        z[2] += np.random.randn() * sigma_yaw
        z[2] = wrap_angle(z[2])

        zs.append(z)

    return np.array(zs)


# =========================
# 模拟 UWB anchor-range 测量
# =========================
def simulate_uwb(traj, anchors, sigma_r=0.08,
                 error_mode="los",
                 nlos_prob=0.0,
                 nlos_bias_mean=1.2,
                 nlos_bias_std=0.35,
                 nlos_bias_min=0.4,
                 nlos_bias_max=2.5,
                 visible_ids_per_step=None,
                 rng_los=None,
                 rng_nlos=None):
    """
    对每个时刻生成 UWB anchor-range 测量

    visible_ids_per_step[k] 给定第 k 帧哪些 anchor 可见

    返回:
        (k, anchor_id, measured_range, is_nlos, nlos_bias)
    """
    if visible_ids_per_step is None:
        raise ValueError("visible_ids_per_step must be provided for reproducible experiments.")

    if rng_los is None:
        rng_los = np.random.default_rng()
    if rng_nlos is None:
        rng_nlos = np.random.default_rng()

    measurements = []

    for k in range(len(traj)):
        px, py, _ = traj[k]
        p = np.array([px, py])
        visible_ids = visible_ids_per_step[k]

        for m in visible_ids:
            a = anchors[m]
            r_true = np.linalg.norm(p - a)

            # LOS 基础测距噪声
            r_meas = r_true + rng_los.normal(loc=0.0, scale=sigma_r)

            # NLOS 污染
            is_nlos = False
            nlos_bias = 0.0

            if error_mode == "mixed_nlos":
                if rng_nlos.random() < nlos_prob:
                    is_nlos = True
                    nlos_bias = sample_truncated_gaussian(
                        mean=nlos_bias_mean,
                        std=nlos_bias_std,
                        vmin=nlos_bias_min,
                        vmax=nlos_bias_max,
                        rng=rng_nlos
                    )
                    r_meas += nlos_bias

            elif error_mode != "los":
                raise ValueError(f"Unknown error_mode: {error_mode}")

            measurements.append((k, int(m), r_meas, is_nlos, nlos_bias))

    return measurements



def summarize_uwb_measurements(measurements, name="UWB"):
    total = len(measurements)
    nlos_flags = [int(meas[3]) for meas in measurements]
    nlos_count = sum(nlos_flags)
    los_count = total - nlos_count

    nlos_biases = [meas[4] for meas in measurements if meas[3]]
    mean_bias = np.mean(nlos_biases) if len(nlos_biases) > 0 else 0.0

    print(f"\n[{name}] total measurements = {total}")
    print(f"[{name}] LOS count          = {los_count}")
    print(f"[{name}] NLOS count         = {nlos_count}")
    print(f"[{name}] NLOS ratio         = {nlos_count / total:.3f}" if total > 0 else f"[{name}] NLOS ratio         = 0.000")
    print(f"[{name}] mean NLOS bias     = {mean_bias:.3f} m")




def robustify_whitened_residual(e, use_robust=False, kernel="huber", delta=2.0):
    """
    输入:
        e: 白化后的标量残差（例如 e = (r_pred-r_meas)/sigma_uwb）

    输出:
        可直接送入 least_squares 的“等效残差”

    设计说明：
    - 若不启用鲁棒，直接返回 e
    - 若启用 Huber，则返回与 Huber 代价对应的等效残差
    - 这样 least_squares(loss="linear") 仍可使用，
      但 UWB 因子的代价函数已经被我们手工改成 Huber 了
    """
    if (not use_robust) or (kernel == "none"):
        return e

    a = abs(e)

    if kernel == "huber":
        # 小残差：保持二次项
        if a <= delta:
            return e

        # 大残差：转为线性增长
        # 这里返回的是“等效残差”，使 0.5 * f^2 对应 Huber 代价
        return np.sign(e) * np.sqrt(2.0 * delta * (a - 0.5 * delta))

    else:
        raise ValueError(f"Unknown robust kernel: {kernel}")




# =========================
# 从 odom 积分出初始轨迹
# =========================
def integrate_odom(odom, init_pose):
    traj = [init_pose.copy()]
    cur = init_pose.copy()

    for z in odom:
        cur = pose_compose(cur, z)
        traj.append(cur.copy())

    return np.array(traj)


# =========================
# 打包/解包状态
# =========================
def pack_states(traj1, traj2):
    return np.hstack([traj1.reshape(-1), traj2.reshape(-1)])


def unpack_states(x, N1, N2):
    traj1 = x[:3 * N1].reshape(N1, 3)
    traj2 = x[3 * N1:].reshape(N2, 3)
    return traj1, traj2


# =========================
# 构造残差函数
# =========================
def build_residual_function(
    N1, N2,
    odom1, odom2,
    uwb1, uwb2,
    anchors,
    prior1,
    prior2=None,
    use_robot2_prior=False,
    use_uwb=True,
    sigma_prior_xy=0.02,
    sigma_prior_yaw=0.02,
    sigma_prior2_xy=5.0,
    sigma_prior2_yaw=1.5,
    sigma_odom_xy=0.05,
    sigma_odom_yaw=0.03,
    sigma_uwb=0.15,
    use_robust_uwb=False,
    robust_kernel="huber",
    robust_delta_uwb=2.0
):
    """
    返回 least_squares 使用的残差函数
    """
    w_prior_xy = 1.0 / sigma_prior_xy
    w_prior_yaw = 1.0 / sigma_prior_yaw
    w_prior2_xy = 1.0 / sigma_prior2_xy
    w_prior2_yaw = 1.0 / sigma_prior2_yaw
    w_odom_xy = 1.0 / sigma_odom_xy
    w_odom_yaw = 1.0 / sigma_odom_yaw
    w_uwb = 1.0 / sigma_uwb

    def residual(x):
        traj1, traj2 = unpack_states(x, N1, N2)
        res = []

        # ---- Robot1 第一帧强先验：提供全局 gauge ----
        e1 = traj1[0] - prior1
        e1[2] = wrap_angle(e1[2])
        res.extend([w_prior_xy * e1[0], w_prior_xy * e1[1], w_prior_yaw * e1[2]])

        # ---- Robot2 默认不使用真值先验 ----
        # 如果将来想测试“弱先验”，可打开 use_robot2_prior
        if use_robot2_prior and (prior2 is not None):
            e2 = traj2[0] - prior2
            e2[2] = wrap_angle(e2[2])
            res.extend([w_prior2_xy * e2[0], w_prior2_xy * e2[1], w_prior2_yaw * e2[2]])

        # ---- Robot1 odom 因子 ----
        for k in range(N1 - 1):
            pred = relative_pose(traj1[k], traj1[k + 1])
            err = pred - odom1[k]
            err[2] = wrap_angle(err[2])
            res.extend([w_odom_xy * err[0], w_odom_xy * err[1], w_odom_yaw * err[2]])

        # ---- Robot2 odom 因子 ----
        for k in range(N2 - 1):
            pred = relative_pose(traj2[k], traj2[k + 1])
            err = pred - odom2[k]
            err[2] = wrap_angle(err[2])
            res.extend([w_odom_xy * err[0], w_odom_xy * err[1], w_odom_yaw * err[2]])

        if use_uwb:
            # ---- Robot1 UWB 因子（可选鲁棒）----
            for meas in uwb1:
                k, m, r_meas = meas[:3]
                px, py, _ = traj1[k]
                r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])

                # 先白化
                e_uwb = w_uwb * (r_pred - r_meas)

                # 再只对 UWB 残差施加鲁棒核
                e_uwb_robust = robustify_whitened_residual(
                    e_uwb,
                    use_robust=use_robust_uwb,
                    kernel=robust_kernel,
                    delta=robust_delta_uwb
                )
                res.append(e_uwb_robust)

            # ---- Robot2 UWB 因子（可选鲁棒）----
            for meas in uwb2:
                k, m, r_meas = meas[:3]
                px, py, _ = traj2[k]
                r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])

                # 先白化
                e_uwb = w_uwb * (r_pred - r_meas)

                # 再只对 UWB 残差施加鲁棒核
                e_uwb_robust = robustify_whitened_residual(
                    e_uwb,
                    use_robust=use_robust_uwb,
                    kernel=robust_kernel,
                    delta=robust_delta_uwb
                )
                res.append(e_uwb_robust)

        return np.array(res)

    return residual


# =========================
# 主程序
# =========================
def main():
    np.random.seed(SEED_MAIN)
    os.makedirs("figs", exist_ok=True)

    # =========================
    # 根据 BASELINE_MODE 自动配置
    # =========================
    if BASELINE_MODE == "odom_only":
        use_uwb = False
        use_robot2_prior = False
        prior2_for_opt = None
        sigma_prior2_xy = SIGMA_WEAK_PRIOR2_XY
        sigma_prior2_yaw = SIGMA_WEAK_PRIOR2_YAW
        anchor_visibility_mode = "all"

    elif BASELINE_MODE == "dual_prior_all_anchors":
        use_uwb = True
        use_robot2_prior = True
        prior2_for_opt = None   # 后面 gt2 生成后再替换为 gt2[0]
        sigma_prior2_xy = SIGMA_PRIOR_XY
        sigma_prior2_yaw = SIGMA_PRIOR_YAW
        anchor_visibility_mode = "all"

    elif BASELINE_MODE == "single_prior_all_anchors":
        use_uwb = True
        use_robot2_prior = USE_ROBOT2_WEAK_PRIOR
        prior2_for_opt = ROBOT2_INIT_GUESS if USE_ROBOT2_WEAK_PRIOR else None
        sigma_prior2_xy = SIGMA_WEAK_PRIOR2_XY
        sigma_prior2_yaw = SIGMA_WEAK_PRIOR2_YAW
        anchor_visibility_mode = "all"

    elif BASELINE_MODE == "single_prior_partial_anchors":
        use_uwb = True
        use_robot2_prior = USE_ROBOT2_WEAK_PRIOR
        prior2_for_opt = ROBOT2_INIT_GUESS if USE_ROBOT2_WEAK_PRIOR else None
        sigma_prior2_xy = SIGMA_WEAK_PRIOR2_XY
        sigma_prior2_yaw = SIGMA_WEAK_PRIOR2_YAW
        anchor_visibility_mode = "partial_random"

    else:
        raise ValueError(f"Unknown BASELINE_MODE: {BASELINE_MODE}")

    # 如果手动强制设置了 USE_UWB，就覆盖模式默认值
    if FORCE_USE_UWB is not None:
        use_uwb = FORCE_USE_UWB

    print("========== Simulation Config ==========")
    print(f"ODOM1_SIGMA_XY                 = {ODOM1_SIGMA_XY}")
    print(f"ODOM1_SIGMA_YAW                = {ODOM1_SIGMA_YAW}")
    print(f"ODOM1_BIAS_XY                  = {ODOM1_BIAS_XY}")
    print(f"ODOM1_BIAS_YAW                 = {ODOM1_BIAS_YAW}")
    print(f"ODOM2_SIGMA_XY                 = {ODOM2_SIGMA_XY}")
    print(f"ODOM2_SIGMA_YAW                = {ODOM2_SIGMA_YAW}")
    print(f"ODOM2_BIAS_XY                  = {ODOM2_BIAS_XY}")
    print(f"ODOM2_BIAS_YAW                 = {ODOM2_BIAS_YAW}")
    print(f"UWB_SIGMA_R(sim)               = {UWB_SIGMA_R}")
    print(f"SIGMA_UWB(opt)                 = {SIGMA_UWB}")
    print(f"ROBOT2_INIT_GUESS              = {ROBOT2_INIT_GUESS}")
    print(f"USE_ROBOT2_WEAK_PRIOR          = {USE_ROBOT2_WEAK_PRIOR}")
    print(f"BASELINE_MODE                  = {BASELINE_MODE}")
    print(f"EFFECTIVE_ANCHOR_VISIBILITY    = {anchor_visibility_mode}")
    print(f"EFFECTIVE_USE_UWB              = {use_uwb}")
    print(f"EFFECTIVE_USE_ROBOT2_PRIOR     = {use_robot2_prior}")
    print(f"MIN_VISIBLE_ANCHORS            = {MIN_VISIBLE_ANCHORS}")
    print(f"MAX_VISIBLE_ANCHORS            = {MAX_VISIBLE_ANCHORS}")
    print(f"UWB_ERROR_MODE                 = {UWB_ERROR_MODE}")
    print(f"NLOS_PROB                      = {NLOS_PROB}")
    print(f"NLOS_BIAS_MEAN                 = {NLOS_BIAS_MEAN}")
    print(f"NLOS_BIAS_STD                  = {NLOS_BIAS_STD}")
    print(f"NLOS_BIAS_MIN                  = {NLOS_BIAS_MIN}")
    print(f"NLOS_BIAS_MAX                  = {NLOS_BIAS_MAX}")
    print(f"USE_ROBUST_UWB                 = {USE_ROBUST_UWB}")
    print(f"ROBUST_KERNEL                  = {ROBUST_KERNEL}")
    print(f"ROBUST_DELTA_UWB[sigma]        = {ROBUST_DELTA_UWB}")
    print(f"ROBUST_THRESHOLD_UWB[m]        = {ROBUST_DELTA_UWB * UWB_SIGMA_R:.3f}")
    print("=======================================")

    # 1) anchor 坐标（世界系）
    anchors = ANCHORS

    # 2) 轨迹长度
    N1 = NUM_STEPS_1
    N2 = NUM_STEPS_2

    # 3) 生成两车真值轨迹
    gt1 = generate_truth_traj(
        center_x=GT1_CENTER_X,
        center_y=GT1_CENTER_Y,
        radius_x=GT1_RADIUS_X,
        radius_y=GT1_RADIUS_Y,
        phase=GT1_PHASE,
        N=N1
    )

    gt2 = generate_truth_traj(
        center_x=GT2_CENTER_X,
        center_y=GT2_CENTER_Y,
        radius_x=GT2_RADIUS_X,
        radius_y=GT2_RADIUS_Y,
        phase=GT2_PHASE,
        N=N2
    )

    # 4) 模拟 odom 测量（故意给车2更大漂移）
    odom1 = simulate_odom(
        gt1,
        sigma_xy=ODOM1_SIGMA_XY,
        sigma_yaw=ODOM1_SIGMA_YAW,
        bias_xy=ODOM1_BIAS_XY,
        bias_yaw=ODOM1_BIAS_YAW
    )

    odom2 = simulate_odom(
        gt2,
        sigma_xy=ODOM2_SIGMA_XY,
        sigma_yaw=ODOM2_SIGMA_YAW,
        bias_xy=ODOM2_BIAS_XY,
        bias_yaw=ODOM2_BIAS_YAW
    )

    # 5) 模拟 UWB 测距
    if use_uwb:
        vis_sched1 = generate_visibility_schedule(
            num_steps=len(gt1),
            num_anchors=len(anchors),
            visibility_mode=anchor_visibility_mode,
            min_visible=MIN_VISIBLE_ANCHORS,
            max_visible=MAX_VISIBLE_ANCHORS,
            rng_vis=np.random.default_rng(SEED_VIS_R1)
        )

        vis_sched2 = generate_visibility_schedule(
            num_steps=len(gt2),
            num_anchors=len(anchors),
            visibility_mode=anchor_visibility_mode,
            min_visible=MIN_VISIBLE_ANCHORS,
            max_visible=MAX_VISIBLE_ANCHORS,
            rng_vis=np.random.default_rng(SEED_VIS_R2)
        )

        uwb1 = simulate_uwb(
            gt1,
            anchors,
            sigma_r=UWB_SIGMA_R,
            error_mode=UWB_ERROR_MODE,
            nlos_prob=NLOS_PROB,
            nlos_bias_mean=NLOS_BIAS_MEAN,
            nlos_bias_std=NLOS_BIAS_STD,
            nlos_bias_min=NLOS_BIAS_MIN,
            nlos_bias_max=NLOS_BIAS_MAX,
            visible_ids_per_step=vis_sched1,
            rng_los=np.random.default_rng(SEED_UWB_LOS_R1),
            rng_nlos=np.random.default_rng(SEED_UWB_NLOS_R1)
        )

        uwb2 = simulate_uwb(
            gt2,
            anchors,
            sigma_r=UWB_SIGMA_R,
            error_mode=UWB_ERROR_MODE,
            nlos_prob=NLOS_PROB,
            nlos_bias_mean=NLOS_BIAS_MEAN,
            nlos_bias_std=NLOS_BIAS_STD,
            nlos_bias_min=NLOS_BIAS_MIN,
            nlos_bias_max=NLOS_BIAS_MAX,
            visible_ids_per_step=vis_sched2,
            rng_los=np.random.default_rng(SEED_UWB_LOS_R2),
            rng_nlos=np.random.default_rng(SEED_UWB_NLOS_R2)
        )

        summarize_uwb_measurements(uwb1, name="Robot1 UWB")
        summarize_uwb_measurements(uwb2, name="Robot2 UWB")

    else:
        uwb1, uwb2 = [], []
        print("\n[UWB] disabled in current baseline.")


    # 6) 由 odom 积分得到初始轨迹
    init1 = integrate_odom(odom1, gt1[0].copy())
    # 由 baseline 模式决定 Robot2 的初始轨迹起点
    if BASELINE_MODE == "dual_prior_all_anchors":
        init2 = integrate_odom(odom2, gt2[0].copy())
    else:
        init2 = integrate_odom(odom2, ROBOT2_INIT_GUESS.copy())

    # 7) 打包初值
    x0 = pack_states(init1, init2)

    # 8) 构造残差函数
    # dual prior 模式下，Robot2 的强先验要用 gt2[0]
    if BASELINE_MODE == "dual_prior_all_anchors":
        prior2_for_opt = gt2[0]

    residual_fn = build_residual_function(
        N1=N1,
        N2=N2,
        odom1=odom1,
        odom2=odom2,
        uwb1=uwb1,
        uwb2=uwb2,
        anchors=anchors,
        prior1=gt1[0],
        prior2=prior2_for_opt,
        use_robot2_prior=use_robot2_prior,
        use_uwb=use_uwb,
        sigma_prior_xy=SIGMA_PRIOR_XY,
        sigma_prior_yaw=SIGMA_PRIOR_YAW,
        sigma_prior2_xy=sigma_prior2_xy,
        sigma_prior2_yaw=sigma_prior2_yaw,
        sigma_odom_xy=SIGMA_ODOM_XY,
        sigma_odom_yaw=SIGMA_ODOM_YAW,
        sigma_uwb=SIGMA_UWB,
        use_robust_uwb=USE_ROBUST_UWB,
        robust_kernel=ROBUST_KERNEL,
        robust_delta_uwb=ROBUST_DELTA_UWB
    )

    # 9) 优化
    result = least_squares(
        residual_fn,
        x0,
        verbose=2,
        max_nfev=100,
        loss="linear"
    )

    est1, est2 = unpack_states(result.x, N1, N2)

    # 10) 计算初始与优化后的 RMSE
    init_rmse1 = np.sqrt(np.mean(np.sum((init1[:, :2] - gt1[:, :2]) ** 2, axis=1)))
    init_rmse2 = np.sqrt(np.mean(np.sum((init2[:, :2] - gt2[:, :2]) ** 2, axis=1)))

    est_rmse1 = np.sqrt(np.mean(np.sum((est1[:, :2] - gt1[:, :2]) ** 2, axis=1)))
    est_rmse2 = np.sqrt(np.mean(np.sum((est2[:, :2] - gt2[:, :2]) ** 2, axis=1)))

    print("\n========== RMSE ==========")
    print(f"Robot1 init position RMSE: {init_rmse1:.4f} m")
    print(f"Robot1 est  position RMSE: {est_rmse1:.4f} m")
    print(f"Robot2 init position RMSE: {init_rmse2:.4f} m")
    print(f"Robot2 est  position RMSE: {est_rmse2:.4f} m")

    # 11) 画图
    plt.figure(figsize=(9, 7))

    # anchors
    plt.scatter(anchors[:, 0], anchors[:, 1], marker='s', s=120, label='Anchors')

    # ground truth
    plt.plot(gt1[:, 0], gt1[:, 1], 'g-', linewidth=2, label='GT Robot1')
    plt.plot(gt2[:, 0], gt2[:, 1], 'b-', linewidth=2, label='GT Robot2')

    # initial from odom
    plt.plot(init1[:, 0], init1[:, 1], 'g--', alpha=0.7, label='Init Robot1')
    plt.plot(init2[:, 0], init2[:, 1], 'b--', alpha=0.7, label='Init Robot2')

    # optimized
    plt.plot(est1[:, 0], est1[:, 1], 'r-', linewidth=2.2, label='Optimized Robot1')
    plt.plot(est2[:, 0], est2[:, 1], 'm-', linewidth=2.2, label='Optimized Robot2')

    plt.axis('equal')
    plt.grid(True)
    plt.xlabel('x [m]')
    plt.ylabel('y [m]')
    plt.title(f'2D Two-Robot + Anchor-UWB Numerical Simulation (2.1, {BASELINE_MODE}, {UWB_ERROR_MODE}, {ROBUST_KERNEL})')
    plt.legend()
    plt.tight_layout()

    save_path = os.path.join(
        "figs",
        f"sim2d_mvp_2.1_{BASELINE_MODE}_{UWB_ERROR_MODE}_{ROBUST_KERNEL}.png"
    )
    plt.savefig(save_path, dpi=200)
    print(f"\nFigure saved to: {save_path}")

    plt.show()


if __name__ == "__main__":
    main()