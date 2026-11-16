# ============================================================
# sim2d_mvp_3.2
# 2D 双车 + Anchor-UWB 后端数值仿真
# （图内可靠性状态版：diagnostic prior + temporal smoothness）
#
# 【本版本目标】
# 在 3.1.3 的 diagnostic-weighted graph 基础上，
# 将原本“图外给定”的 reliability 序列
#   s_lio_hat(k), s_rtab_hat(k), s_uwb1_hat(k), s_uwb2_hat(k)
# 升级为“图内显式优化变量”：
#   s_lio(k), s_rtab(k), s_uwb1(k), s_uwb2(k)
#
# 3.1.3 中：
# 1) 轨迹是优化变量
# 2) reliability 由 diagnostic 模块计算后直接送入残差
# 3) residual = sqrt(s_hat) * e
#
# 3.2 中：
# 1) 轨迹仍然是优化变量
# 2) reliability 也成为优化变量
# 3) diagnostic 输出的 s_hat 只作为“观测先验”
# 4) 最终送入残差的是优化后的 s，而不是直接用 s_hat
#
# ------------------------------------------------------------
# 【本版本核心思想】
# 3.2 采用三步流程：
#
# Stage-0:
#   先做一遍基础图优化（不加 reliability weighting）
#   得到初步轨迹估计。
#
# Stage-1:
#   用 3.1.3 的 diagnostic 模块，根据 stage-0 轨迹与观测，
#   构造模态级 reliability 观测：
#   - s_lio_hat(k)
#   - s_rtab_hat(k)
#   - s_uwb1_hat(k)
#   - s_uwb2_hat(k)
#
# Stage-2:
#   将 reliability 作为图内显式状态变量，与轨迹一起联合优化。
#   优化目标同时包含：
#   1) 加权后的 odom / UWB 残差
#   2) reliability 对 diagnostic 输出的先验项
#   3) reliability 的时间平滑项
#
# ------------------------------------------------------------
# 【本版本图模型】
# 1. 优化变量包括：
#    - traj1
#    - traj2
#    - raw_lio
#    - raw_rtab
#    - raw_uwb1
#    - raw_uwb2
#
# 2. 通过有界化映射得到真正的 reliability：
#    s = floor + (1 - floor) * sigmoid(raw)
#
# 3. 加权残差仍采用：
#    r = sqrt(s) * e
#
# 4. 新增两类 reliability 约束：
#    - diagnostic prior:
#        (s - s_hat)
#    - temporal smoothness:
#        (s(k+1) - s(k))
#
# ------------------------------------------------------------
# 【本版本希望验证】
# 1) 图内 reliability state 是否能比 3.1.3 的图外权重更平滑；
# 2) 在单模态 / 双模态 / 混合退化下，
#    图内 reliability state 是否仍保持正确的模态选择性；
# 3) 在不显式使用 oracle 标签的前提下，
#    3.2 是否能比 3.1.3 更稳定地组织多模态融合。
#
# ------------------------------------------------------------
# 【本版本与 3.1.3 的区别】
# 1. 3.1.3：s_hat 是图外权重，直接用于加权残差
# 2. 3.2：s 是图内状态，s_hat 只作为 prior
# 3. 3.1.3：没有 reliability state smoothness
# 4. 3.2：有 explicit temporal smoothness
#
# ------------------------------------------------------------
# 【本版本意义】
# 3.2 是从 diagnostic-weighted baseline
# 走向 graph-internal reliability model 的第一版正式实现。
# 它为后续更复杂的多模态 reliability 建模提供直接代码骨架。
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
# 3.2 版新增：graph-internal reliability state 配置
# =========================
USE_RELIABILITY_WEIGHTING = True

# reliability 下界，避免权重接近 0 导致数值不稳
RELIABILITY_FLOOR = 0.10

# 3.2 的实验场景（仍然只决定“如何注入退化”）
# "uwb_only"
# "lio_only"
# "rtab_only"
# "dual_lio_uwb"
# "dual_rtab_uwb"
# "mixed_all"
DEGRADATION_CASE = "uwb_only"

# 车1 odom ≈ LIO（仅用于数据注入）
LIO_DEGRADE_WINDOWS = [(18, 30)]
LIO_SIGMA_SCALE_DEG = 4.0
LIO_BIAS_SCALE_DEG = 3.0

# 车2 odom ≈ RTAB（仅用于数据注入）
RTAB_DEGRADE_WINDOWS = [(22, 36)]
RTAB_SIGMA_SCALE_DEG = 5.0
RTAB_BIAS_SCALE_DEG = 3.0

# ---------- 求解流程 ----------
# Stage-0: 无 reliability weighting 的基础优化
STAGE0_MAX_NFEV = 300

# Stage-2: 图内 reliability state 联合优化
STAGE2_MAX_NFEV = 1200

# ---------- 3.1.3 诊断映射参数（保留） ----------
# odom 方差比诊断参数
ODOM_REF_PREFIX_LEN = 12
ODOM_VAR_HALF_WINDOW = 5
ODOM_VAR_RATIO_YAW_WEIGHT = 1.0
ODOM_VAR_DEADZONE = 0.20
ODOM_VAR_DROP_POWER = 2.0

# 时序平滑窗口
DIAG_SMOOTH_WIN = 5

# UWB 更敏感诊断参数
DIAG_MAD_SCALE_UWB = 2.8
UWB_DEADZONE_Z = 0.15
UWB_DROP_SHARPNESS = 1.60

# UWB 几何覆盖度混合系数
UWB_GEOM_BLEND = 0.20

# LOS 场景关闭 UWB 几何惩罚
DISABLE_UWB_GEOM_PENALTY_IN_LOS = True

# ---------- 3.2 新增：reliability prior / smoothness 参数 ----------
# s_hat prior 强度（越小越强）
SIGMA_S_PRIOR_LIO = 0.20
SIGMA_S_PRIOR_RTAB = 0.20
SIGMA_S_PRIOR_UWB = 0.18

# 时间平滑强度（越小越强）
SIGMA_S_SMOOTH_LIO = 0.12
SIGMA_S_SMOOTH_RTAB = 0.12
SIGMA_S_SMOOTH_UWB = 0.10

# 是否打印 stage-0 RMSE
PRINT_STAGE0_RMSE = True

# 是否打印 stage-2 优化后的 reliability 统计
PRINT_STAGE2_STATE_STATS = True



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
                  bias_xy=(0.0, 0.0), bias_yaw=0.0,
                  sigma_scale_series=None,
                  bias_scale_series=None):
    """
    输入真值轨迹，输出相邻帧 odom 测量
    支持时变退化：sigma / bias 可按时间段放大
    """
    zs = []
    for k in range(len(traj) - 1):
        z = relative_pose(traj[k], traj[k + 1]).copy()

        sigma_scale = 1.0 if sigma_scale_series is None else sigma_scale_series[k]
        bias_scale = 1.0 if bias_scale_series is None else bias_scale_series[k]

        # 时变偏置
        z[0] += bias_xy[0] * bias_scale
        z[1] += bias_xy[1] * bias_scale
        z[2] += bias_yaw * bias_scale

        # 时变噪声
        z[0] += np.random.randn() * sigma_xy * sigma_scale
        z[1] += np.random.randn() * sigma_xy * sigma_scale
        z[2] += np.random.randn() * sigma_yaw * sigma_scale
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


def fill_windows(length, windows, normal_val, degraded_val):
    arr = np.full(length, normal_val, dtype=float)
    for a, b in windows:
        a = max(0, a)
        b = min(length, b)
        arr[a:b] = degraded_val
    return arr


def fill_windows_scale(length, windows, normal_scale, degraded_scale):
    arr = np.full(length, normal_scale, dtype=float)
    for a, b in windows:
        a = max(0, a)
        b = min(length, b)
        arr[a:b] = degraded_scale
    return arr


def summarize_reliability_series(series, name="Reliability"):
    if len(series) == 0:
        print(f"\n[{name}] empty")
        return

    print(f"\n[{name}] mean      = {np.mean(series):.3f}")
    print(f"[{name}] min       = {np.min(series):.3f}")
    print(f"[{name}] max       = {np.max(series):.3f}")
    print(f"[{name}] <0.5 cnt  = {np.sum(series < 0.5)}")
    print(f"[{name}] <0.3 cnt  = {np.sum(series < 0.3)}")


def configure_degradation_case():
    if DEGRADATION_CASE == "uwb_only":
        return "mixed_nlos", [], []

    elif DEGRADATION_CASE == "lio_only":
        return "los", LIO_DEGRADE_WINDOWS, []

    elif DEGRADATION_CASE == "rtab_only":
        return "los", [], RTAB_DEGRADE_WINDOWS

    elif DEGRADATION_CASE == "dual_lio_uwb":
        return "mixed_nlos", LIO_DEGRADE_WINDOWS, []

    elif DEGRADATION_CASE == "dual_rtab_uwb":
        return "mixed_nlos", [], RTAB_DEGRADE_WINDOWS

    elif DEGRADATION_CASE == "mixed_all":
        return "mixed_nlos", LIO_DEGRADE_WINDOWS, RTAB_DEGRADE_WINDOWS

    else:
        raise ValueError(f"Unknown DEGRADATION_CASE: {DEGRADATION_CASE}")


def smooth_series(series, win=5):
    series = np.asarray(series, dtype=float)
    if win <= 1 or len(series) == 0:
        return series.copy()

    kernel = np.ones(win, dtype=float) / float(win)
    pad = win // 2
    padded = np.pad(series, (pad, pad), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="valid")
    return smoothed[:len(series)]

def local_std_series(values, half_window=5, eps=1e-6):
    """
    计算一维序列在每个时刻的局部窗口标准差
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    out = np.full(n, np.nan, dtype=float)

    for k in range(n):
        a = max(0, k - half_window)
        b = min(n, k + half_window + 1)
        win = values[a:b]

        if len(win) < 3:
            continue

        out[k] = max(np.std(win), eps)

    if np.any(np.isfinite(out)):
        fill_val = np.nanmedian(out)
        out[~np.isfinite(out)] = fill_val
    else:
        out[:] = eps

    return out

def local_robust_abs_deviation_series(values, half_window=4, eps=1e-6):
    """
    对一维序列做局部 robust 偏离度计算：
    score[k] = |x_k - local_median| / local_MAD
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    score = np.zeros(n, dtype=float)

    for k in range(n):
        a = max(0, k - half_window)
        b = min(n, k + half_window + 1)
        win = values[a:b]

        if len(win) < 3:
            score[k] = 0.0
            continue

        med = np.median(win)
        mad = np.median(np.abs(win - med))
        mad = max(mad, eps)

        score[k] = abs(values[k] - med) / mad

    return score


def robust_median_mad(values, eps=1e-6):
    values = np.asarray(values, dtype=float)
    med = np.median(values)
    mad = np.median(np.abs(values - med))
    mad = max(mad, eps)
    return med, mad


def compute_odom_self_consistency_series(odom,
                                         ref_prefix_len=12,
                                         half_window=5,
                                         yaw_weight=1.0,
                                         eps=1e-6):
    """
    3.1.3 新版：
    用“局部窗口方差 / 健康参考方差”的比值来诊断 odom。

    设计动机：
    - 3.1.2 的局部 median/MAD 偏离度更适合检测尖峰异常
    - 但对“连续一段噪声放大 + 偏置放大”的退化段不够敏感
    - 3.1.3 改为检测局部方差是否相对健康基线显著升高
    """
    odom = np.asarray(odom, dtype=float)
    n = len(odom)

    if n == 0:
        return np.zeros(0, dtype=float)

    # 平移增量模长
    trans_norm = np.linalg.norm(odom[:, :2], axis=1)

    # 角增量绝对值
    yaw_abs = np.abs(np.array([wrap_angle(v) for v in odom[:, 2]]))

    # 当前局部窗口方差
    trans_std_local = local_std_series(
        trans_norm, half_window=half_window, eps=eps
    )
    yaw_std_local = local_std_series(
        yaw_abs, half_window=half_window, eps=eps
    )

    # 用最前面一段作为“健康参考区间”
    ref_end = min(max(ref_prefix_len, 3), n)

    ref_trans_std = np.median(trans_std_local[:ref_end])
    ref_yaw_std = np.median(yaw_std_local[:ref_end])

    ref_trans_std = max(ref_trans_std, eps)
    ref_yaw_std = max(ref_yaw_std, eps)

    # 方差比，只关心“比参考更坏”的部分
    ratio_trans = np.maximum(trans_std_local / ref_trans_std - 1.0, 0.0)
    ratio_yaw = np.maximum(yaw_std_local / ref_yaw_std - 1.0, 0.0)

    err = np.sqrt(
        ratio_trans**2 +
        yaw_weight * ratio_yaw**2
    )

    err = smooth_series(err, win=3)
    return err


def compute_uwb_factor_error_series(traj, uwb_meas, anchors, sigma_uwb=0.15):
    """
    3.1.2 新版：
    计算每一帧 UWB 因子的白化残差聚合量，
    采用“均值 + 最大值”的更敏感聚合，而不是单纯 mean abs residual。

    返回:
        step_err: shape = [num_steps]
        step_cnt: shape = [num_steps]
    """
    w_uwb = 1.0 / sigma_uwb
    num_steps = len(traj)

    grouped = [[] for _ in range(num_steps)]
    cnt = np.zeros(num_steps, dtype=int)

    for meas in uwb_meas:
        k, m, r_meas = meas[:3]
        px, py, _ = traj[k]
        r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])

        e = abs(w_uwb * (r_pred - r_meas))
        grouped[k].append(e)
        cnt[k] += 1

    step_err = np.full(num_steps, np.nan, dtype=float)

    for k in range(num_steps):
        if cnt[k] == 0:
            continue

        vals = np.asarray(grouped[k], dtype=float)

        if len(vals) == 1:
            step_err[k] = vals[0]
        else:
            mean_e = np.mean(vals)
            max_e = np.max(vals)

            # 更敏感：既看整体平均，也看最坏一条
            step_err[k] = 0.5 * mean_e + 0.5 * max_e

    return step_err, cnt



def compute_excess_z_series(errors, mad_scale=3.0):
    """
    统一的 robust excess z 计算：
    z = max((error - median) / (mad_scale * MAD), 0)
    """
    errors = np.asarray(errors, dtype=float)
    valid = np.isfinite(errors)

    z = np.zeros(len(errors), dtype=float)
    if np.sum(valid) == 0:
        return z, valid

    med, mad = robust_median_mad(errors[valid])

    z[valid] = np.maximum((errors[valid] - med) / (mad_scale * mad), 0.0)
    z[~valid] = np.nan
    return z, valid


def map_odom_error_series_to_reliability(errors,
                                         floor=0.10,
                                         smooth_win=5,
                                         deadzone=0.20,
                                         drop_power=2.0):
    """
    3.1.3 新版：
    odom 的 errors 已经是“方差比 error”，
    因此不再做 robust z 归一化，
    直接对 error 本身施加 dead-zone。
    """
    errors = np.asarray(errors, dtype=float)
    valid = np.isfinite(errors)

    s = np.ones(len(errors), dtype=float)
    if np.sum(valid) > 0:
        e_eff = np.maximum(errors[valid] - deadzone, 0.0)
        s[valid] = 1.0 / (1.0 + e_eff**drop_power)

    s[~valid] = floor
    s = smooth_series(s, win=smooth_win)
    s = np.clip(s, floor, 1.0)
    return s


def map_uwb_error_series_to_reliability(errors,
                                        floor=0.10,
                                        mad_scale=2.8,
                                        smooth_win=5,
                                        deadzone_z=0.15,
                                        drop_sharpness=1.60):
    """
    3.1.2 新版：
    UWB 使用更敏感的映射。
    dead-zone 很小，只要残差超过正常范围就较快下降。
    """
    z, valid = compute_excess_z_series(errors, mad_scale=mad_scale)

    s = np.ones(len(errors), dtype=float)
    if np.sum(valid) > 0:
        z_eff = np.maximum(z[valid] - deadzone_z, 0.0)
        s[valid] = np.exp(-drop_sharpness * z_eff)

    s[~valid] = floor
    s = smooth_series(s, win=smooth_win)
    s = np.clip(s, floor, 1.0)
    return s


def build_diagnostic_reliability_series(
    traj1, traj2,
    odom1, odom2,
    uwb1, uwb2,
    anchors,
    sigma_odom_xy=0.05,
    sigma_odom_yaw=0.03,
    sigma_uwb=0.15,
    reliability_floor=0.10,
    mad_scale_uwb=2.8,
    smooth_win=5,
    uwb_geom_blend=0.20,
    odom_ref_prefix_len=12,
    odom_var_half_window=5,
    odom_var_ratio_yaw_weight=1.0,
    odom_var_deadzone=0.20,
    odom_var_drop_power=2.0,
    uwb_deadzone_z=0.15,
    uwb_drop_sharpness=1.60,
    use_uwb_geom_penalty=True
):
    """
    3.1.3 的核心函数：
    - odom reliability: 方差比诊断 + dead-zone
    - UWB reliability : 更敏感残差聚合 + LOS 下可关闭几何惩罚
    """
    # =========================================================
    # 1) odom 模态：方差比诊断
    # =========================================================
    err_lio = compute_odom_self_consistency_series(
        odom1,
        ref_prefix_len=odom_ref_prefix_len,
        half_window=odom_var_half_window,
        yaw_weight=odom_var_ratio_yaw_weight
    )
    err_rtab = compute_odom_self_consistency_series(
        odom2,
        ref_prefix_len=odom_ref_prefix_len,
        half_window=odom_var_half_window,
        yaw_weight=odom_var_ratio_yaw_weight
    )

    s_lio = map_odom_error_series_to_reliability(
        err_lio,
        floor=reliability_floor,
        smooth_win=smooth_win,
        deadzone=odom_var_deadzone,
        drop_power=odom_var_drop_power
    )
    s_rtab = map_odom_error_series_to_reliability(
        err_rtab,
        floor=reliability_floor,
        smooth_win=smooth_win,
        deadzone=odom_var_deadzone,
        drop_power=odom_var_drop_power
    )

    # =========================================================
    # 2) UWB 模态：更敏感残差聚合 + LOS 可关闭几何惩罚
    # =========================================================
    err_uwb1, cnt_uwb1 = compute_uwb_factor_error_series(
        traj1, uwb1, anchors, sigma_uwb=sigma_uwb
    )
    err_uwb2, cnt_uwb2 = compute_uwb_factor_error_series(
        traj2, uwb2, anchors, sigma_uwb=sigma_uwb
    )

    s_uwb1 = map_uwb_error_series_to_reliability(
        err_uwb1,
        floor=reliability_floor,
        mad_scale=mad_scale_uwb,
        smooth_win=smooth_win,
        deadzone_z=uwb_deadzone_z,
        drop_sharpness=uwb_drop_sharpness
    )
    s_uwb2 = map_uwb_error_series_to_reliability(
        err_uwb2,
        floor=reliability_floor,
        mad_scale=mad_scale_uwb,
        smooth_win=smooth_win,
        deadzone_z=uwb_deadzone_z,
        drop_sharpness=uwb_drop_sharpness
    )

    num_anchors = len(anchors)
    geom1 = np.clip(cnt_uwb1 / max(num_anchors, 1), 0.0, 1.0)
    geom2 = np.clip(cnt_uwb2 / max(num_anchors, 1), 0.0, 1.0)

    if use_uwb_geom_penalty:
        geom_term1 = uwb_geom_blend + (1.0 - uwb_geom_blend) * (geom1 ** 2)
        geom_term2 = uwb_geom_blend + (1.0 - uwb_geom_blend) * (geom2 ** 2)
    else:
        geom_term1 = np.ones_like(geom1)
        geom_term2 = np.ones_like(geom2)

    s_uwb1 = s_uwb1 * geom_term1
    s_uwb2 = s_uwb2 * geom_term2

    s_uwb1[cnt_uwb1 == 0] = reliability_floor
    s_uwb2[cnt_uwb2 == 0] = reliability_floor

    s_uwb1 = np.clip(s_uwb1, reliability_floor, 1.0)
    s_uwb2 = np.clip(s_uwb2, reliability_floor, 1.0)

    return s_lio, s_rtab, s_uwb1, s_uwb2, err_lio, err_rtab, err_uwb1, err_uwb2



# =========================
# 3.2 新增：图内 reliability state 工具函数
# =========================
def sigmoid(x):
    x = np.clip(x, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-x))


def raw_to_reliability(raw, floor=0.10):
    """
    将无界 raw 映射到 [floor, 1) 区间
    """
    raw = np.asarray(raw, dtype=float)
    return floor + (1.0 - floor) * sigmoid(raw)


def reliability_to_raw(s, floor=0.10, eps=1e-6):
    """
    将 [floor, 1) 区间的 reliability 反变换到 raw
    用于初始化 3.2 的图内 reliability state
    """
    s = np.asarray(s, dtype=float)
    y = (np.clip(s, floor + eps, 1.0 - eps) - floor) / (1.0 - floor)
    y = np.clip(y, eps, 1.0 - eps)
    return np.log(y / (1.0 - y))


def pack_joint_states(traj1, traj2, raw_lio, raw_rtab, raw_uwb1, raw_uwb2):
    """
    3.2 联合状态打包：
    [traj1, traj2, raw_lio, raw_rtab, raw_uwb1, raw_uwb2]
    """
    return np.hstack([
        traj1.reshape(-1),
        traj2.reshape(-1),
        raw_lio.reshape(-1),
        raw_rtab.reshape(-1),
        raw_uwb1.reshape(-1),
        raw_uwb2.reshape(-1)
    ])


def unpack_joint_states(x, N1, N2):
    """
    3.2 联合状态解包
    """
    idx = 0

    traj1 = x[idx:idx + 3 * N1].reshape(N1, 3)
    idx += 3 * N1

    traj2 = x[idx:idx + 3 * N2].reshape(N2, 3)
    idx += 3 * N2

    raw_lio = x[idx:idx + (N1 - 1)]
    idx += (N1 - 1)

    raw_rtab = x[idx:idx + (N2 - 1)]
    idx += (N2 - 1)

    raw_uwb1 = x[idx:idx + N1]
    idx += N1

    raw_uwb2 = x[idx:idx + N2]

    return traj1, traj2, raw_lio, raw_rtab, raw_uwb1, raw_uwb2


def summarize_state_fit(s_hat, s_opt, name="s"):
    s_hat = np.asarray(s_hat, dtype=float)
    s_opt = np.asarray(s_opt, dtype=float)

    print(f"\n[{name}] hat mean   = {np.mean(s_hat):.3f}")
    print(f"[{name}] opt mean   = {np.mean(s_opt):.3f}")
    print(f"[{name}] mean |diff| = {np.mean(np.abs(s_opt - s_hat)):.3f}")
    print(f"[{name}] opt min    = {np.min(s_opt):.3f}")
    print(f"[{name}] opt max    = {np.max(s_opt):.3f}")


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
    idx = 0

    traj1 = x[idx:idx + 3 * N1].reshape(N1, 3)
    idx += 3 * N1

    traj2 = x[idx:idx + 3 * N2].reshape(N2, 3)

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
    s_lio=None,
    s_rtab=None,
    s_uwb1=None,
    s_uwb2=None,
    use_reliability_weighting=True,
    reliability_floor=0.10
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

    if s_lio is None:
        s_lio = np.ones(N1 - 1)
    if s_rtab is None:
        s_rtab = np.ones(N2 - 1)
    if s_uwb1 is None:
        s_uwb1 = np.ones(N1)
    if s_uwb2 is None:
        s_uwb2 = np.ones(N2)

    def residual(x):
        traj1, traj2 = unpack_states(x, N1, N2)
        res = []

        # ---- Robot1 第一帧强先验：提供全局 gauge ----
        e1 = traj1[0] - prior1
        e1[2] = wrap_angle(e1[2])
        res.extend([w_prior_xy * e1[0], w_prior_xy * e1[1], w_prior_yaw * e1[2]])

        # ---- Robot2 可选弱先验 ----
        if use_robot2_prior and (prior2 is not None):
            e2 = traj2[0] - prior2
            e2[2] = wrap_angle(e2[2])
            res.extend([w_prior2_xy * e2[0], w_prior2_xy * e2[1], w_prior2_yaw * e2[2]])

        # ---- Robot1 odom 因子：乘 sqrt(s_lio[k]) ----
        for k in range(N1 - 1):
            pred = relative_pose(traj1[k], traj1[k + 1])
            err = pred - odom1[k]
            err[2] = wrap_angle(err[2])

            alpha = 1.0
            if use_reliability_weighting:
                alpha = np.sqrt(np.clip(s_lio[k], reliability_floor, 1.0))

            res.extend([
                alpha * w_odom_xy * err[0],
                alpha * w_odom_xy * err[1],
                alpha * w_odom_yaw * err[2]
            ])

        # ---- Robot2 odom 因子：乘 sqrt(s_rtab[k]) ----
        for k in range(N2 - 1):
            pred = relative_pose(traj2[k], traj2[k + 1])
            err = pred - odom2[k]
            err[2] = wrap_angle(err[2])

            alpha = 1.0
            if use_reliability_weighting:
                alpha = np.sqrt(np.clip(s_rtab[k], reliability_floor, 1.0))

            res.extend([
                alpha * w_odom_xy * err[0],
                alpha * w_odom_xy * err[1],
                alpha * w_odom_yaw * err[2]
            ])

        if use_uwb:
            # ---- Robot1 UWB：同一时刻共享 s_uwb1[k] ----
            for meas in uwb1:
                k, m, r_meas = meas[:3]
                px, py, _ = traj1[k]
                r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])

                e_uwb = w_uwb * (r_pred - r_meas)

                alpha = 1.0
                if use_reliability_weighting:
                    alpha = np.sqrt(np.clip(s_uwb1[k], reliability_floor, 1.0))

                res.append(alpha * e_uwb)

            # ---- Robot2 UWB：同一时刻共享 s_uwb2[k] ----
            for meas in uwb2:
                k, m, r_meas = meas[:3]
                px, py, _ = traj2[k]
                r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])

                e_uwb = w_uwb * (r_pred - r_meas)

                alpha = 1.0
                if use_reliability_weighting:
                    alpha = np.sqrt(np.clip(s_uwb2[k], reliability_floor, 1.0))

                res.append(alpha * e_uwb)

        return np.array(res)

    return residual



# =========================
# 3.2 新增：图内 reliability state 联合残差函数
# =========================
def build_joint_reliability_residual_function(
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
    s_hat_lio=None,
    s_hat_rtab=None,
    s_hat_uwb1=None,
    s_hat_uwb2=None,
    sigma_s_prior_lio=0.20,
    sigma_s_prior_rtab=0.20,
    sigma_s_prior_uwb=0.18,
    sigma_s_smooth_lio=0.12,
    sigma_s_smooth_rtab=0.12,
    sigma_s_smooth_uwb=0.10,
    reliability_floor=0.10
):
    """
    3.2：
    联合优化轨迹 + reliability state
    """
    w_prior_xy = 1.0 / sigma_prior_xy
    w_prior_yaw = 1.0 / sigma_prior_yaw
    w_prior2_xy = 1.0 / sigma_prior2_xy
    w_prior2_yaw = 1.0 / sigma_prior2_yaw
    w_odom_xy = 1.0 / sigma_odom_xy
    w_odom_yaw = 1.0 / sigma_odom_yaw
    w_uwb = 1.0 / sigma_uwb

    w_s_prior_lio = 1.0 / sigma_s_prior_lio
    w_s_prior_rtab = 1.0 / sigma_s_prior_rtab
    w_s_prior_uwb = 1.0 / sigma_s_prior_uwb

    w_s_smooth_lio = 1.0 / sigma_s_smooth_lio
    w_s_smooth_rtab = 1.0 / sigma_s_smooth_rtab
    w_s_smooth_uwb = 1.0 / sigma_s_smooth_uwb

    if s_hat_lio is None:
        s_hat_lio = np.ones(N1 - 1)
    if s_hat_rtab is None:
        s_hat_rtab = np.ones(N2 - 1)
    if s_hat_uwb1 is None:
        s_hat_uwb1 = np.ones(N1)
    if s_hat_uwb2 is None:
        s_hat_uwb2 = np.ones(N2)

    def residual(x):
        traj1, traj2, raw_lio, raw_rtab, raw_uwb1, raw_uwb2 = \
            unpack_joint_states(x, N1, N2)

        s_lio = raw_to_reliability(raw_lio, floor=reliability_floor)
        s_rtab = raw_to_reliability(raw_rtab, floor=reliability_floor)
        s_uwb1 = raw_to_reliability(raw_uwb1, floor=reliability_floor)
        s_uwb2 = raw_to_reliability(raw_uwb2, floor=reliability_floor)

        res = []

        # ---- Robot1 第一帧强先验 ----
        e1 = traj1[0] - prior1
        e1[2] = wrap_angle(e1[2])
        res.extend([
            w_prior_xy * e1[0],
            w_prior_xy * e1[1],
            w_prior_yaw * e1[2]
        ])

        # ---- Robot2 可选弱先验 ----
        if use_robot2_prior and (prior2 is not None):
            e2 = traj2[0] - prior2
            e2[2] = wrap_angle(e2[2])
            res.extend([
                w_prior2_xy * e2[0],
                w_prior2_xy * e2[1],
                w_prior2_yaw * e2[2]
            ])

        # ---- Robot1 odom ----
        for k in range(N1 - 1):
            pred = relative_pose(traj1[k], traj1[k + 1])
            err = pred - odom1[k]
            err[2] = wrap_angle(err[2])

            alpha = np.sqrt(s_lio[k])

            res.extend([
                alpha * w_odom_xy * err[0],
                alpha * w_odom_xy * err[1],
                alpha * w_odom_yaw * err[2]
            ])

        # ---- Robot2 odom ----
        for k in range(N2 - 1):
            pred = relative_pose(traj2[k], traj2[k + 1])
            err = pred - odom2[k]
            err[2] = wrap_angle(err[2])

            alpha = np.sqrt(s_rtab[k])

            res.extend([
                alpha * w_odom_xy * err[0],
                alpha * w_odom_xy * err[1],
                alpha * w_odom_yaw * err[2]
            ])

        # ---- UWB ----
        if use_uwb:
            for meas in uwb1:
                k, m, r_meas = meas[:3]
                px, py, _ = traj1[k]
                r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])
                e_uwb = w_uwb * (r_pred - r_meas)

                alpha = np.sqrt(s_uwb1[k])
                res.append(alpha * e_uwb)

            for meas in uwb2:
                k, m, r_meas = meas[:3]
                px, py, _ = traj2[k]
                r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])
                e_uwb = w_uwb * (r_pred - r_meas)

                alpha = np.sqrt(s_uwb2[k])
                res.append(alpha * e_uwb)

        # ---- diagnostic prior: s - s_hat ----
        res.extend(list(w_s_prior_lio * (s_lio - s_hat_lio)))
        res.extend(list(w_s_prior_rtab * (s_rtab - s_hat_rtab)))
        res.extend(list(w_s_prior_uwb * (s_uwb1 - s_hat_uwb1)))
        res.extend(list(w_s_prior_uwb * (s_uwb2 - s_hat_uwb2)))

        # ---- temporal smoothness ----
        for k in range(len(s_lio) - 1):
            res.append(w_s_smooth_lio * (s_lio[k + 1] - s_lio[k]))

        for k in range(len(s_rtab) - 1):
            res.append(w_s_smooth_rtab * (s_rtab[k + 1] - s_rtab[k]))

        for k in range(len(s_uwb1) - 1):
            res.append(w_s_smooth_uwb * (s_uwb1[k + 1] - s_uwb1[k]))

        for k in range(len(s_uwb2) - 1):
            res.append(w_s_smooth_uwb * (s_uwb2[k + 1] - s_uwb2[k]))

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

    effective_uwb_error_mode, lio_windows, rtab_windows = configure_degradation_case()
    
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
    print(f"DEGRADATION_CASE               = {DEGRADATION_CASE}")
    print(f"EFFECTIVE_UWB_ERROR_MODE       = {effective_uwb_error_mode}")
    print(f"LIO_DEGRADE_WINDOWS            = {lio_windows}")
    print(f"RTAB_DEGRADE_WINDOWS           = {rtab_windows}")
    print(f"NLOS_PROB                      = {NLOS_PROB}")
    print(f"NLOS_BIAS_MEAN                 = {NLOS_BIAS_MEAN}")
    print(f"NLOS_BIAS_STD                  = {NLOS_BIAS_STD}")
    print(f"NLOS_BIAS_MIN                  = {NLOS_BIAS_MIN}")
    print(f"NLOS_BIAS_MAX                  = {NLOS_BIAS_MAX}")
    print(f"USE_RELIABILITY_WEIGHTING      = {USE_RELIABILITY_WEIGHTING}")
    print(f"RELIABILITY_FLOOR             = {RELIABILITY_FLOOR}")
    print(f"STAGE0_MAX_NFEV               = {STAGE0_MAX_NFEV}")
    print(f"DIAG_SMOOTH_WIN               = {DIAG_SMOOTH_WIN}")
    print(f"ODOM_REF_PREFIX_LEN           = {ODOM_REF_PREFIX_LEN}")
    print(f"ODOM_VAR_HALF_WINDOW          = {ODOM_VAR_HALF_WINDOW}")
    print(f"ODOM_VAR_RATIO_YAW_WEIGHT     = {ODOM_VAR_RATIO_YAW_WEIGHT}")
    print(f"ODOM_VAR_DEADZONE             = {ODOM_VAR_DEADZONE}")
    print(f"ODOM_VAR_DROP_POWER           = {ODOM_VAR_DROP_POWER}")
    print(f"DISABLE_UWB_GEOM_PENALTY_IN_LOS = {DISABLE_UWB_GEOM_PENALTY_IN_LOS}")
    print(f"UWB_GEOM_BLEND                = {UWB_GEOM_BLEND}")
    print(f"UWB_DEADZONE_Z                = {UWB_DEADZONE_Z}")
    print(f"UWB_DROP_SHARPNESS            = {UWB_DROP_SHARPNESS}")
    print(f"STAGE2_MAX_NFEV               = {STAGE2_MAX_NFEV}")
    print(f"SIGMA_S_PRIOR_LIO             = {SIGMA_S_PRIOR_LIO}")
    print(f"SIGMA_S_PRIOR_RTAB            = {SIGMA_S_PRIOR_RTAB}")
    print(f"SIGMA_S_PRIOR_UWB             = {SIGMA_S_PRIOR_UWB}")
    print(f"SIGMA_S_SMOOTH_LIO            = {SIGMA_S_SMOOTH_LIO}")
    print(f"SIGMA_S_SMOOTH_RTAB           = {SIGMA_S_SMOOTH_RTAB}")
    print(f"SIGMA_S_SMOOTH_UWB            = {SIGMA_S_SMOOTH_UWB}")
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

    lio_sigma_scale = fill_windows_scale(N1 - 1, lio_windows, 1.0, LIO_SIGMA_SCALE_DEG)
    lio_bias_scale = fill_windows_scale(N1 - 1, lio_windows, 1.0, LIO_BIAS_SCALE_DEG)

    rtab_sigma_scale = fill_windows_scale(N2 - 1, rtab_windows, 1.0, RTAB_SIGMA_SCALE_DEG)
    rtab_bias_scale = fill_windows_scale(N2 - 1, rtab_windows, 1.0, RTAB_BIAS_SCALE_DEG)


    # 4) 模拟 odom 测量（故意给车2更大漂移）
    odom1 = simulate_odom(
        gt1,
        sigma_xy=ODOM1_SIGMA_XY,
        sigma_yaw=ODOM1_SIGMA_YAW,
        bias_xy=ODOM1_BIAS_XY,
        bias_yaw=ODOM1_BIAS_YAW,
        sigma_scale_series=lio_sigma_scale,
        bias_scale_series=lio_bias_scale
    )

    odom2 = simulate_odom(
        gt2,
        sigma_xy=ODOM2_SIGMA_XY,
        sigma_yaw=ODOM2_SIGMA_YAW,
        bias_xy=ODOM2_BIAS_XY,
        bias_yaw=ODOM2_BIAS_YAW,
        sigma_scale_series=rtab_sigma_scale,
        bias_scale_series=rtab_bias_scale
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
            error_mode=effective_uwb_error_mode,
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
            error_mode=effective_uwb_error_mode,
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


    # =========================================================
    # 3.1 Stage-0:
    # 先做一遍不使用 diagnostic reliability weighting 的基础优化
    # 目的：得到用于构造诊断量的初步轨迹
    # =========================================================
    x0_stage0 = pack_states(init1, init2)

    if BASELINE_MODE == "dual_prior_all_anchors":
        prior2_for_stage0 = gt2[0]
    else:
        prior2_for_stage0 = prior2_for_opt

    residual_fn_stage0 = build_residual_function(
        N1=N1,
        N2=N2,
        odom1=odom1,
        odom2=odom2,
        uwb1=uwb1,
        uwb2=uwb2,
        anchors=anchors,
        prior1=gt1[0],
        prior2=prior2_for_stage0,
        use_robot2_prior=use_robot2_prior,
        use_uwb=use_uwb,
        sigma_prior_xy=SIGMA_PRIOR_XY,
        sigma_prior_yaw=SIGMA_PRIOR_YAW,
        sigma_prior2_xy=sigma_prior2_xy,
        sigma_prior2_yaw=sigma_prior2_yaw,
        sigma_odom_xy=SIGMA_ODOM_XY,
        sigma_odom_yaw=SIGMA_ODOM_YAW,
        sigma_uwb=SIGMA_UWB,
        s_lio=np.ones(N1 - 1),
        s_rtab=np.ones(N2 - 1),
        s_uwb1=np.ones(N1),
        s_uwb2=np.ones(N2),
        use_reliability_weighting=False,
        reliability_floor=RELIABILITY_FLOOR
    )

    result_stage0 = least_squares(
        residual_fn_stage0,
        x0_stage0,
        verbose=0,
        max_nfev=STAGE0_MAX_NFEV,
        loss="linear"
    )

    stage0_est1, stage0_est2 = unpack_states(result_stage0.x, N1, N2)

    # =========================================================
    # 3.1 Stage-1 前处理:
    # 由 stage-0 轨迹 + 观测构造 diagnostic reliability 序列
    # =========================================================
    if use_uwb:
        use_uwb_geom_penalty = not (
            DISABLE_UWB_GEOM_PENALTY_IN_LOS and effective_uwb_error_mode == "los"
    )

        s_lio, s_rtab, s_uwb1, s_uwb2, err_lio, err_rtab, err_uwb1, err_uwb2 = \
            build_diagnostic_reliability_series(
                traj1=stage0_est1,
                traj2=stage0_est2,
                odom1=odom1,
                odom2=odom2,
                uwb1=uwb1,
                uwb2=uwb2,
                anchors=anchors,
                sigma_odom_xy=SIGMA_ODOM_XY,
                sigma_odom_yaw=SIGMA_ODOM_YAW,
                sigma_uwb=SIGMA_UWB,
                reliability_floor=RELIABILITY_FLOOR,
                mad_scale_uwb=DIAG_MAD_SCALE_UWB,
                smooth_win=DIAG_SMOOTH_WIN,
                uwb_geom_blend=UWB_GEOM_BLEND,
                odom_ref_prefix_len=ODOM_REF_PREFIX_LEN,
                odom_var_half_window=ODOM_VAR_HALF_WINDOW,
                odom_var_ratio_yaw_weight=ODOM_VAR_RATIO_YAW_WEIGHT,
                odom_var_deadzone=ODOM_VAR_DEADZONE,
                odom_var_drop_power=ODOM_VAR_DROP_POWER,
                uwb_deadzone_z=UWB_DEADZONE_Z,
                uwb_drop_sharpness=UWB_DROP_SHARPNESS,
                use_uwb_geom_penalty=use_uwb_geom_penalty
            )
    else:
        # odom_only 不推荐用于 3.1 diagnostic，
        # 因为没有外部约束时，odom residual 很难提供有意义的模态诊断
        s_lio = np.ones(N1 - 1)
        s_rtab = np.ones(N2 - 1)
        s_uwb1 = np.ones(N1)
        s_uwb2 = np.ones(N2)
        err_lio = np.zeros(N1 - 1)
        err_rtab = np.zeros(N2 - 1)
        err_uwb1 = np.zeros(N1)
        err_uwb2 = np.zeros(N2)

    summarize_reliability_series(s_lio, name="s_lio")
    summarize_reliability_series(s_rtab, name="s_rtab")
    summarize_reliability_series(s_uwb1, name="s_uwb1")
    summarize_reliability_series(s_uwb2, name="s_uwb2")


    if PRINT_STAGE0_RMSE:
        stage0_rmse1 = np.sqrt(np.mean(np.sum((stage0_est1[:, :2] - gt1[:, :2]) ** 2, axis=1)))
        stage0_rmse2 = np.sqrt(np.mean(np.sum((stage0_est2[:, :2] - gt2[:, :2]) ** 2, axis=1)))

        print("\n========== Stage-0 RMSE ==========")
        print(f"Robot1 stage-0 position RMSE: {stage0_rmse1:.4f} m")
        print(f"Robot2 stage-0 position RMSE: {stage0_rmse2:.4f} m")
    
    # =========================================================
    # 3.2 Stage-2:
    # 将 diagnostic 输出 s_hat 作为先验，
    # 把 reliability 作为图内状态，与轨迹一起联合优化
    # =========================================================

    # 先把 3.1 diagnostic 输出冻结成 observation prior
    s_hat_lio = s_lio.copy()
    s_hat_rtab = s_rtab.copy()
    s_hat_uwb1 = s_uwb1.copy()
    s_hat_uwb2 = s_uwb2.copy()

    # 用 s_hat 反变换得到 raw 初值
    raw_lio0 = reliability_to_raw(s_hat_lio, floor=RELIABILITY_FLOOR)
    raw_rtab0 = reliability_to_raw(s_hat_rtab, floor=RELIABILITY_FLOOR)
    raw_uwb10 = reliability_to_raw(s_hat_uwb1, floor=RELIABILITY_FLOOR)
    raw_uwb20 = reliability_to_raw(s_hat_uwb2, floor=RELIABILITY_FLOOR)

    # 联合状态初值：
    # 轨迹用 stage-0 结果，reliability 用 diagnostic 输出初始化
    x0 = pack_joint_states(
        stage0_est1,
        stage0_est2,
        raw_lio0,
        raw_rtab0,
        raw_uwb10,
        raw_uwb20
    )

    # dual prior 模式下，Robot2 的强先验要用 gt2[0]
    if BASELINE_MODE == "dual_prior_all_anchors":
        prior2_for_opt = gt2[0]

    residual_fn = build_joint_reliability_residual_function(
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
        s_hat_lio=s_hat_lio,
        s_hat_rtab=s_hat_rtab,
        s_hat_uwb1=s_hat_uwb1,
        s_hat_uwb2=s_hat_uwb2,
        sigma_s_prior_lio=SIGMA_S_PRIOR_LIO,
        sigma_s_prior_rtab=SIGMA_S_PRIOR_RTAB,
        sigma_s_prior_uwb=SIGMA_S_PRIOR_UWB,
        sigma_s_smooth_lio=SIGMA_S_SMOOTH_LIO,
        sigma_s_smooth_rtab=SIGMA_S_SMOOTH_RTAB,
        sigma_s_smooth_uwb=SIGMA_S_SMOOTH_UWB,
        reliability_floor=RELIABILITY_FLOOR
    )

    result = least_squares(
        residual_fn,
        x0,
        verbose=2,
        max_nfev=STAGE2_MAX_NFEV,
        loss="linear"
    )

    est1, est2, raw_lio_opt, raw_rtab_opt, raw_uwb1_opt, raw_uwb2_opt = \
        unpack_joint_states(result.x, N1, N2)

    s_lio_opt = raw_to_reliability(raw_lio_opt, floor=RELIABILITY_FLOOR)
    s_rtab_opt = raw_to_reliability(raw_rtab_opt, floor=RELIABILITY_FLOOR)
    s_uwb1_opt = raw_to_reliability(raw_uwb1_opt, floor=RELIABILITY_FLOOR)
    s_uwb2_opt = raw_to_reliability(raw_uwb2_opt, floor=RELIABILITY_FLOOR)

    if PRINT_STAGE2_STATE_STATS:
        summarize_state_fit(s_hat_lio, s_lio_opt, name="s_lio")
        summarize_state_fit(s_hat_rtab, s_rtab_opt, name="s_rtab")
        summarize_state_fit(s_hat_uwb1, s_uwb1_opt, name="s_uwb1")
        summarize_state_fit(s_hat_uwb2, s_uwb2_opt, name="s_uwb2")

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
    plt.title(
        f'2D Two-Robot + Anchor-UWB Numerical Simulation '
        f'(3.2, {BASELINE_MODE}, {DEGRADATION_CASE}, graph_internal_reliability_state)'
    )
    plt.legend()
    plt.tight_layout()

    save_path = os.path.join(
        "figs",
        f"sim2d_mvp_3.2_{BASELINE_MODE}_{DEGRADATION_CASE}_graph_internal_reliability_state.png"
    )
    plt.savefig(save_path, dpi=200)
    print(f"\nFigure saved to: {save_path}")

    plt.show()


if __name__ == "__main__":
    main()