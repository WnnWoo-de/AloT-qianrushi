# Long Corridor Patent Figures Run Info

- Generated at: 2026-06-08T18:42:41
- Source optimizer script: `C:\Users\27463\Desktop\FAST-LIVO2\sim2d_mvp_3.2.3.py`
- Supplemental scene: `long_corridor_patent`
- Version source: `sim2d_mvp_3.2.3.py` reusable optimizer APIs
- Main random seed: `4242`
- Visibility seeds: Robot1 `5101`, Robot2 `5102`
- UWB LOS seeds: Robot1 `6101`, Robot2 `6102`
- Number of steps: `36`
- Long-corridor solver budgets: baseline `50`, stage-0 `60`, stage-2 `80`
- Robot1 odometry degradation windows: `[(13, 25)]`
- UWB mode: LOS, partial visible anchors, no NLOS injection
- Baseline: odometry-only, no UWB factors, no Robot2 prior, no reliability state
- Proposed: Stage-0 + diagnostic reliability + graph-internal reliability state + sqrt-count UWB prior balance
- Relative error definition: `e_rel(k)=||(p2_est(k)-p1_est(k))-(p2_gt(k)-p1_gt(k))||_2`

## Anchors

  - A0: (-1.00, 0.15)
  - A1: (3.50, 3.85)
  - A2: (8.00, 0.15)
  - A3: (12.50, 3.85)
  - A4: (17.00, 0.15)
  - A5: (23.00, 3.85)

## Visibility Counts

- Robot1 min/mean/max: 3/3.44/4
- Robot2 min/mean/max: 3/3.50/4

## Metrics

### Fig. 4/6 odometry-only baseline
- `robot1_rmse_m`: 2.842411
- `robot2_rmse_m`: 3.234405
- `relative_rmse_m`: 1.648939
- `relative_mean_m`: 1.559102
- `relative_max_m`: 2.339931

### Fig. 5/7 proposed method
- `robot1_rmse_m`: 0.108501
- `robot2_rmse_m`: 0.083921
- `relative_rmse_m`: 0.119078
- `relative_mean_m`: 0.107872
- `relative_max_m`: 0.207316

## Generated Files

- `C:\Users\27463\Desktop\FAST-LIVO2\figs\patent_figures\fig04_long_corridor_odom_baseline_trajectory.png`
- `C:\Users\27463\Desktop\FAST-LIVO2\figs\patent_figures\fig05_long_corridor_proposed_trajectory.png`
- `C:\Users\27463\Desktop\FAST-LIVO2\figs\patent_figures\fig06_long_corridor_odom_baseline_relative_error.png`
- `C:\Users\27463\Desktop\FAST-LIVO2\figs\patent_figures\fig07_long_corridor_proposed_relative_error.png`
