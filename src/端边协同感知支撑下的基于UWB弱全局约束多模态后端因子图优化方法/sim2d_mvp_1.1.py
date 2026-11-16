# ============================================================
# sim2d_mvp_1.1
# 2D 双车 + Anchor-UWB 后端数值仿真（正常 LOS 误差基线版）
#
# 【本版本目标】
# 在 1.0 最小后端骨架已经验证通过的基础上，
# 进一步将 odom 与 UWB 的误差模型参数化，形成一个
# “正常 LOS 工况下可调、可复现、可做参数扫描”的基线版本。
#
# ------------------------------------------------------------
# 【本版本仿真的内容】
# 1. 仿真二维世界中的两台机器人真值轨迹
# 2. 仿真两台机器人的局部 odom 测量
# 3. 仿真两台机器人到固定 anchors 的 UWB 测距
# 4. 使用 odom 积分生成带漂移的初始轨迹
# 5. 使用后端优化同时融合：
#    - Robot1 odom
#    - Robot2 odom
#    - Robot1 到 anchors 的 UWB range
#    - Robot2 到 anchors 的 UWB range
#    - 第一帧先验
# 6. 输出优化前后 RMSE，并绘制轨迹图
#
# ------------------------------------------------------------
# 【与 1.0 相比的改进】
# 1. 将 odom 噪声、odom 偏置、UWB 噪声集中为显式参数
# 2. 将优化中使用的先验/odom/UWB 权重参数显式化
# 3. 便于进行正常 LOS 条件下的参数扫描，例如：
#    - 不同 UWB sigma_r
#    - 不同 Robot2 odom 漂移强度
# 4. 为后续 2.0 版本（NLOS 外点 + 鲁棒损失）提供可靠基线
#
# ------------------------------------------------------------
# 【本版本考虑到的误差】
# 1. Robot1 odom 高斯噪声
# 2. Robot1 odom 固定偏置
# 3. Robot2 odom 高斯噪声
# 4. Robot2 odom 固定偏置
# 5. UWB range 高斯测距噪声（LOS 正常工况）
#
# ------------------------------------------------------------
# 【本版本仍未考虑的内容】
# 1. NLOS 偏置 / gross outlier / 丢包
# 2. 鲁棒核 / switchable constraints
# 3. 统一退化识别
# 4. 车车约束
# 5. 时间偏置 Δt
# 6. 原始相机 / 雷达 / IMU 数据与地图生成
#
# ------------------------------------------------------------
# 【本版本意义】
# 本版本用于建立“正常 LOS 条件下”的后端性能基线，
# 以便后续在此基础上引入 NLOS、鲁棒损失和统一可靠性模型。
# ============================================================
import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares


# =========================
# 仿真参数（1.1 版新增）
# =========================


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
SIGMA_UWB = 0.10



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
def simulate_uwb(traj, anchors, sigma_r=0.08):
    """
    对每个时刻、每个 anchor，生成测距
    返回列表: (k, anchor_id, measured_range)
    """
    measurements = []
    for k in range(len(traj)):
        px, py, _ = traj[k]
        p = np.array([px, py])

        for m, a in enumerate(anchors):
            r_true = np.linalg.norm(p - a)
            r_meas = r_true + np.random.randn() * sigma_r
            measurements.append((k, m, r_meas))

    return measurements


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
    prior1, prior2,
    sigma_prior_xy=0.02,
    sigma_prior_yaw=0.02,
    sigma_odom_xy=0.05,
    sigma_odom_yaw=0.03,
    sigma_uwb=0.10
):
    """
    返回 least_squares 使用的残差函数
    """
    w_prior_xy = 1.0 / sigma_prior_xy
    w_prior_yaw = 1.0 / sigma_prior_yaw
    w_odom_xy = 1.0 / sigma_odom_xy
    w_odom_yaw = 1.0 / sigma_odom_yaw
    w_uwb = 1.0 / sigma_uwb

    def residual(x):
        traj1, traj2 = unpack_states(x, N1, N2)
        res = []

        # ---- 第一帧先验（仿真里直接固定到真值起点）----
        e1 = traj1[0] - prior1
        e1[2] = wrap_angle(e1[2])
        res.extend([w_prior_xy * e1[0], w_prior_xy * e1[1], w_prior_yaw * e1[2]])

        e2 = traj2[0] - prior2
        e2[2] = wrap_angle(e2[2])
        res.extend([w_prior_xy * e2[0], w_prior_xy * e2[1], w_prior_yaw * e2[2]])

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

        # ---- Robot1 UWB 因子 ----
        for (k, m, r_meas) in uwb1:
            px, py, _ = traj1[k]
            r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])
            res.append(w_uwb * (r_pred - r_meas))

        # ---- Robot2 UWB 因子 ----
        for (k, m, r_meas) in uwb2:
            px, py, _ = traj2[k]
            r_pred = np.linalg.norm(np.array([px, py]) - anchors[m])
            res.append(w_uwb * (r_pred - r_meas))

        return np.array(res)

    return residual


# =========================
# 主程序
# =========================
def main():
    np.random.seed(42)
    print("========== Simulation Config ==========")
    print(f"ODOM1_SIGMA_XY  = {ODOM1_SIGMA_XY}")
    print(f"ODOM1_SIGMA_YAW = {ODOM1_SIGMA_YAW}")
    print(f"ODOM1_BIAS_XY   = {ODOM1_BIAS_XY}")
    print(f"ODOM1_BIAS_YAW  = {ODOM1_BIAS_YAW}")
    print(f"ODOM2_SIGMA_XY  = {ODOM2_SIGMA_XY}")
    print(f"ODOM2_SIGMA_YAW = {ODOM2_SIGMA_YAW}")
    print(f"ODOM2_BIAS_XY   = {ODOM2_BIAS_XY}")
    print(f"ODOM2_BIAS_YAW  = {ODOM2_BIAS_YAW}")
    print(f"UWB_SIGMA_R     = {UWB_SIGMA_R}")
    print("=======================================")
    os.makedirs("figs", exist_ok=True)

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
    uwb1 = simulate_uwb(gt1, anchors, sigma_r=UWB_SIGMA_R)
    uwb2 = simulate_uwb(gt2, anchors, sigma_r=UWB_SIGMA_R)

    # 6) 由 odom 积分得到初始轨迹
    init1 = integrate_odom(odom1, gt1[0].copy())
    init2 = integrate_odom(odom2, gt2[0].copy())

    # 7) 打包初值
    x0 = pack_states(init1, init2)

    # 8) 构造残差函数
    residual_fn = build_residual_function(
        N1=N1,
        N2=N2,
        odom1=odom1,
        odom2=odom2,
        uwb1=uwb1,
        uwb2=uwb2,
        anchors=anchors,
        prior1=gt1[0],
        prior2=gt2[0],
        sigma_prior_xy=SIGMA_PRIOR_XY,
        sigma_prior_yaw=SIGMA_PRIOR_YAW,
        sigma_odom_xy=SIGMA_ODOM_XY,
        sigma_odom_yaw=SIGMA_ODOM_YAW,
        sigma_uwb=SIGMA_UWB
    )

    # 9) 优化
    result = least_squares(
        residual_fn,
        x0,
        verbose=2,
        max_nfev=100
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
    plt.title('2D Two-Robot + Anchor-UWB Numerical Simulation')
    plt.legend()
    plt.tight_layout()

    save_path = os.path.join("figs", "sim2d_mvp_1.1.png")
    plt.savefig(save_path, dpi=200)
    print(f"\nFigure saved to: {save_path}")

    plt.show()


if __name__ == "__main__":
    main()