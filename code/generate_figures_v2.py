#!/usr/bin/env python3
"""生成论文级图表（图2 Pareto + 图3 噪声扫描）— 高质量视觉，英文标签"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os, json

os.makedirs("/tmp/paper_figs", exist_ok=True)

# 配色 — 高级学术配色
colors = {
    'orange': '#E69F00', 'blue': '#56B4E9', 'green': '#009E73',
    'yellow': '#F0E442', 'dkblue': '#0072B2', 'red': '#D55E00',
    'pink': '#CC79A7', 'gray': '#888888', 'ltgray': '#E8E8E8',
    'black': '#333333'
}

plt.rcParams.update({
    'font.size': 12,
    'font.family': 'sans-serif',
    'axes.titlesize': 14,
    'axes.labelsize': 13,
    'axes.linewidth': 1.2,
    'xtick.major.width': 1.0,
    'ytick.major.width': 1.0,
    'figure.dpi': 200,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

# ===============================================================
#  图2：Pareto前沿3D
# ===============================================================
print("=== 图2: Pareto 3D ===")
data = np.load("/home/user2/research-project/lcvr-optimization/results/exp03/nsga2_v2.npz")
pf = data['pareto_fit']

# 过滤f2异常值
mask = pf[:, 1] < 10
pf_f = pf[mask]

# 膝点
fn = (pf_f - pf_f.min(axis=0)) / (pf_f.max(axis=0) - pf_f.min(axis=0) + 1e-10)
knee_idx = np.argmin(np.linalg.norm(fn, axis=1))
knee_pt = pf_f[knee_idx]

# 每个点距理想点的距离（用于配色）
ideal = pf_f.min(axis=0)
norm_dist = np.linalg.norm((pf_f - ideal) / (pf_f.max(axis=0) - pf_f.min(axis=0) + 1e-10), axis=1)

fig = plt.figure(figsize=(9, 7.5), facecolor='white')
ax = fig.add_subplot(111, projection='3d')

# 散点：viridis_r渐变色
sc = ax.scatter(pf_f[:, 0], pf_f[:, 1], pf_f[:, 2],
                c=norm_dist, cmap='viridis_r', s=40, alpha=0.8,
                edgecolors='w', linewidth=0.3, zorder=5)

# 膝点大星星
ax.scatter(knee_pt[0], knee_pt[1], knee_pt[2],
           c=colors['red'], s=200, marker='*', edgecolors='black', linewidths=1.5,
           label='Knee point', zorder=10)

# 膝点投影线到三个轴平面
for axis in ['x', 'y', 'z']:
    pts = np.zeros((2, 3))
    pts[0] = knee_pt
    pts[1] = knee_pt.copy()
    if axis == 'x':
        pts[1, 0] = pf_f[:, 0].min()
    elif axis == 'y':
        pts[1, 1] = pf_f[:, 1].min()
    else:
        pts[1, 2] = pf_f[:, 2].min()
    ax.plot(pts[:, 0], pts[:, 1], pts[:, 2], '--', color=colors['red'], alpha=0.25, lw=0.8)

# 颜色条
cbar = fig.colorbar(sc, ax=ax, shrink=0.6, aspect=20, pad=0.1)
cbar.set_label('Normalized distance to ideal point', fontsize=10)

# 坐标轴
ax.set_xlabel(r'$f_1$: Gaussian (e4)', fontsize=12, labelpad=10)
ax.set_ylabel(r'$f_2$: Poisson (BCPN)', fontsize=12, labelpad=10)
ax.set_zlabel(r'$f_3$: Thermal sensitivity', fontsize=12, labelpad=10)

# 范围适当扩展
ax.set_xlim(pf_f[:, 0].min()*0.8, pf_f[:, 0].max()*1.3)
ax.set_ylim(pf_f[:, 1].min()*0.8, pf_f[:, 1].max()*1.3)
ax.set_zlim(pf_f[:, 2].min()*0.8, pf_f[:, 2].max()*1.3)

# 网格
ax.xaxis.pane.set_edgecolor('#dddddd')
ax.yaxis.pane.set_edgecolor('#dddddd')
ax.zaxis.pane.set_edgecolor('#dddddd')

# 视角
ax.view_init(elev=22, azim=-55)

legend = ax.legend(loc='upper left', fontsize=10, framealpha=0.85,
                   edgecolor=colors['gray'], fancybox=True)

ax.set_title('Pareto front (NSGA-II, 200 generations)', fontsize=13, pad=15)

plt.tight_layout()
plt.savefig("/tmp/paper_figs/fig_pareto.png", dpi=300)
plt.savefig("/tmp/paper_figs/fig_pareto.pdf", dpi=300)
plt.close()
print("  OK!")

# ===============================================================
#  图3：噪声扫描曲线（双面板）
# ===============================================================
print("=== 图3: Noise scan ===")
with open("/home/user2/research-project/lcvr-optimization/results/exp05/stokes_reconstruction.json") as f:
    sr = json.load(f)

noise_data = sr["noise_scan"]
noise_levels = sorted([float(k) for k in noise_data.keys()])

name_map = {
    "4meas random":       "4meas \u968f\u673a(\u672a\u4f18\u5316)",
    "4meas CN-opt":       "4meas \u5355\u76ee\u6807(CN)",
    "6meas CN-opt":       "6meas \u5355\u76ee\u6807(CN)",
    "6meas Knee point":   "6meas \u591a\u76ee\u6807\u819d\u70b9(\u2605)",
}

curves = [
    ("4meas random",     'o', colors['gray'],  '--', 1.5, 1),
    ("4meas CN-opt",     's', colors['orange'], '--', 1.8, 2),
    ("6meas CN-opt",     'D', colors['blue'],   '-.', 1.8, 3),
    ("6meas Knee point", '*', colors['red'],    '-',  2.5, 4),
]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
fig.patch.set_facecolor('white')
for ax in [ax1, ax2]:
    ax.set_facecolor('white')

for label, marker, color, ls, lw, z in curves:
    real_key = name_map[label]
    y_vals = [noise_data[str(nl)][real_key]["vec_error"] for nl in noise_levels]
    ax1.loglog(noise_levels, y_vals,
              marker=marker, color=color, ls=ls, lw=lw,
              markersize=7 if marker != '*' else 14,
              label=label, zorder=z)
    y_vals = [noise_data[str(nl)][real_key]["dolp_error"] for nl in noise_levels]
    ax2.loglog(noise_levels, y_vals,
              marker=marker, color=color, ls=ls, lw=lw,
              markersize=7 if marker != '*' else 14,
              label=label, zorder=z)

for ax, title, ylabel in [
    (ax1, '(a) Stokes vector error', 'Stokes vector error'),
    (ax2, '(b) DoLP error', 'DoLP error'),
]:
    ax.set_xlabel('Gaussian noise std', fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=13)
    ax.grid(True, alpha=0.25, which='both', linestyle=':')
    ax.legend(fontsize=9, framealpha=0.85, edgecolor=colors['gray'],
              ncol=1, loc='lower right')

plt.suptitle('Reconstruction accuracy vs noise level', fontsize=14, y=1.02)
plt.tight_layout()
plt.savefig("/tmp/paper_figs/fig_noise_scan.png", dpi=300)
plt.savefig("/tmp/paper_figs/fig_noise_scan.pdf", dpi=300)
plt.close()
print("  OK!")

print("\n\u2705 All figures generated in /tmp/paper_figs/")
