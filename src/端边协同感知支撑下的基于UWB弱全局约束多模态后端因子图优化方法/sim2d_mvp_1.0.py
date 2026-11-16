# ============================================================
# sim2d_mvp_1.0
# 2D 双车 + Anchor-UWB 后端数值仿真（最小可行版本 / MVP）
#
# 【本版本目标】
# 验证双车协同后端的最小数学骨架是否成立：
# 在二维平面中，当两台机器人各自只有带漂移的局部里程计时，
# 是否可以借助已知坐标的 UWB anchors，将两车轨迹同时约束到
# 同一个全局世界系（anchor 世界系）中。
#
# ------------------------------------------------------------
# 【本版本仿真的内容】
# 1. 仿真二维世界（2D）
#    - 机器人状态为 [x, y, yaw]
#    - 只考虑平面位置与航向角，不考虑 3D 姿态
#
# 2. 仿真固定已知坐标的 UWB anchors
#    - anchors 在世界系中固定不动
#    - anchors 坐标已知
#    - 这对应真实系统中的 anchor 世界系 / uwb_world
#
# 3. 仿真两台机器人的真值轨迹
#    - Robot1 和 Robot2 各有一条真值轨迹
#    - 两条真值轨迹都位于同一个世界系中
#
# 4. 仿真两台机器人的局部 odom 测量
#    - 根据真值轨迹相邻时刻生成相对位姿测量
#    - odom 测量包含：
#      a) 高斯随机噪声
#      b) 固定系统偏置（bias）
#    - 因此仅靠 odom 积分会产生累计漂移
#
# 5. 仿真两台机器人到 anchors 的 UWB 测距
#    - 对每个时刻、每个 anchor 生成一条 range 测量
#    - UWB 测距包含高斯噪声
#    - 当前版本默认是正常 LOS 测距，不含 NLOS 偏置和异常值
#
# 6. 仿真“仅依赖 odom 积分”的初始轨迹
#    - 使用 odom 从第一帧开始逐步积分
#    - 得到带漂移的初始轨迹 init1 / init2
#
# 7. 仿真最小后端优化问题
#    - 优化变量：两台机器人所有离散时刻的位姿
#    - 约束包括：
#      a) 第一帧先验
#      b) Robot1 odom 因子
#      c) Robot2 odom 因子
#      d) Robot1 UWB range 因子
#      e) Robot2 UWB range 因子
#    - 目标：同时满足局部运动连续性和 anchor 测距一致性
#
# 8. 仿真后端效果评估
#    - 计算优化前后的位置 RMSE
#    - 绘制真值轨迹、初始轨迹、优化轨迹和 anchor 布局
#
# ------------------------------------------------------------
# 【本版本考虑到的误差】
# 1. Robot1 odom 的高斯噪声
# 2. Robot1 odom 的固定偏置漂移
# 3. Robot2 odom 的高斯噪声
# 4. Robot2 odom 的固定偏置漂移
# 5. UWB range 的高斯测距噪声（LOS 正常测距模型）
#
# ------------------------------------------------------------
# 【本版本未考虑的内容】
# 1. 未仿真相机、雷达、IMU 的原始传感器数据
# 2. 未生成点云地图、彩色地图或子图融合结果
# 3. 未考虑 UWB 的 NLOS 偏置、异常值、丢包和时间延迟
# 4. 未考虑统一退化识别、鲁棒核、车车约束和闭环
# 5. 未考虑多机时间偏置 Δt
#
# ------------------------------------------------------------
# 【本版本意义】
# 本版本不是最终系统，而是后端主干的数学原型：
# 它用于验证状态定义、残差构造和优化目标是否正确，
# 并证明 anchor-UWB 可以把双车轨迹统一到同一世界系中。
# ============================================================
import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares


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
    os.makedirs("figs", exist_ok=True)

    # 1) anchor 坐标（世界系）
    anchors = np.array([
        [0.0, 0.0],
        [10.0, 0.0],
        [10.0, 8.0],
        [0.0, 8.0]
    ])

    # 2) 轨迹长度
    N1 = 60
    N2 = 60

    # 3) 生成两车真值轨迹
    gt1 = generate_truth_traj(center_x=4.0, center_y=4.0,
                              radius_x=2.5, radius_y=1.5,
                              phase=0.0, N=N1)

    gt2 = generate_truth_traj(center_x=5.2, center_y=3.0,
                              radius_x=2.0, radius_y=1.2,
                              phase=0.5, N=N2)

    # 4) 模拟 odom 测量（故意给车2更大漂移）
    odom1 = simulate_odom(
        gt1,
        sigma_xy=0.03,
        sigma_yaw=0.01,
        bias_xy=(0.004, -0.002),
        bias_yaw=0.0015
    )

    odom2 = simulate_odom(
        gt2,
        sigma_xy=0.04,
        sigma_yaw=0.015,
        bias_xy=(0.006, 0.003),
        bias_yaw=-0.002
    )

    # 5) 模拟 UWB 测距
    uwb1 = simulate_uwb(gt1, anchors, sigma_r=0.10)
    uwb2 = simulate_uwb(gt2, anchors, sigma_r=0.10)

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
        sigma_prior_xy=0.02,
        sigma_prior_yaw=0.02,
        sigma_odom_xy=0.05,
        sigma_odom_yaw=0.03,
        sigma_uwb=0.10
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

    save_path = os.path.join("figs", "sim2d_mvp_1.0.png")
    plt.savefig(save_path, dpi=200)
    print(f"\nFigure saved to: {save_path}")

    plt.show()


if __name__ == "__main__":
    main()