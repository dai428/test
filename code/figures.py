"""
LCVR Stokes Polarimeter — 论文级图表
=====================================
生成论文所需的对比图和表格。
"""

import numpy as np
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path

from models import IDEAL_CN, get_A_4meas, get_A_6meas, safe_cond
from evaluate import evaluate_strategy, load_params, LAMBDAS_FINE, T_FINE

RESULTS_DIR = Path(__file__).parent / "results"
TABLES_DIR = RESULTS_DIR / "tables"
FIGURES_DIR = Path(__file__).parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# 配色方案 (Nature 风格, 色盲友好)
COLORS = {
    'A_CN_4meas': '#E64B35',    # 红
    'A_CN_6meas': '#E64B35',    # 红
    'B_BCPN_4meas': '#4DBBD5',  # 蓝
    'B_BCPN_6meas': '#4DBBD5',  # 蓝
    'C_Temp_4meas': '#00A087',  # 绿
    'C_Temp_6meas': '#00A087',  # 绿
    'D_Comb_4meas': '#3C5488',  # 紫蓝
    'D_Comb_6meas': '#3C5488',  # 紫蓝
}
LABELS = {
    'A_CN_4meas': '高斯最优(4次)',
    'A_CN_6meas': '高斯最优(6次)',
    'B_BCPN_4meas': '泊松最优(4次)',
    'B_BCPN_6meas': '泊松最优(6次)',
    'C_Temp_4meas': '温漂鲁棒(4次)',
    'C_Temp_6meas': '温漂鲁棒(6次)',
    'D_Comb_4meas': '联合最优(4次)',
    'D_Comb_6meas': '联合最优(6次)',
}


# ============================================================
# 图1: CN vs 波长 (不同温度, 单策略)
# ============================================================

def fig1_cn_vs_wavelength(name, params, is_6meas):
    """每个策略: CN vs λ 在不同温度下的曲线"""
    selected_T = [-10, 0, 10, 20, 30, 40]
    lambdas = np.arange(400, 701, 5)
    
    plt.figure(figsize=(8, 5))
    for T in selected_T:
        cn_vals = []
        for lam in lambdas:
            A = (get_A_6meas if is_6meas else get_A_4meas)(params, lam, T)
            cn_vals.append(safe_cond(A))
        plt.plot(lambdas, cn_vals, lw=1.8, label=f'{T}°C')
    
    plt.axhline(y=IDEAL_CN, color='k', ls='--', lw=1.5, alpha=0.6, label=f'Ideal √3={IDEAL_CN:.3f}')
    plt.xlabel('Wavelength (nm)', fontsize=12)
    plt.ylabel('Condition Number', fontsize=12)
    plt.title(f'CN vs Wavelength — {name}', fontsize=13)
    plt.grid(True, alpha=0.3)
    plt.legend(ncol=2, fontsize=9)
    plt.ylim(1.5, None)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / f'fig1_cn_vs_lambda_{name}.pdf', dpi=300)
    plt.savefig(FIGURES_DIR / f'fig1_cn_vs_lambda_{name}.png', dpi=150)
    plt.close()
    print(f"  图1已保存: fig1_cn_vs_lambda_{name}")


# ============================================================
# 图2: CN 3D 曲面 (CN vs λ × T) — 4个策略对比
# ============================================================

def fig2_cn_3d_surface(all_metrics):
    """4个主要策略的 CN 3D 曲面对比 (2×2 子图)"""
    strategies = ['A_CN_4meas', 'C_Temp_4meas', 'B_BCPN_4meas', 'D_Comb_4meas']
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), subplot_kw={'projection': '3d'})
    
    X, Y = np.meshgrid(LAMBDAS_FINE, T_FINE)
    
    for idx, name in enumerate(strategies):
        ax = axes[idx // 2, idx % 2]
        cn_grid = np.array(all_metrics[name]['cn_grid'])
        
        surf = ax.plot_surface(X, Y, cn_grid, cmap='viridis', 
                               edgecolor='none', alpha=0.85, antialiased=True)
        
        # 理想平面
        ideal_surface = np.full_like(cn_grid, IDEAL_CN)
        ax.plot_surface(X, Y, ideal_surface, color='red', alpha=0.15, 
                        label=f'Ideal √3={IDEAL_CN:.3f}')
        
        ax.set_xlabel('λ (nm)', fontsize=10, labelpad=8)
        ax.set_ylabel('T (°C)', fontsize=10, labelpad=8)
        ax.set_zlabel('CN', fontsize=10, labelpad=4)
        ax.set_title(LABELS[name], fontsize=12, pad=10)
        ax.view_init(elev=25, azim=-60)
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=12, label='CN')
    
    plt.suptitle('Condition Number Surface (λ × T)', fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'fig2_cn_3d_comparison.pdf', dpi=300, bbox_inches='tight')
    plt.savefig(FIGURES_DIR / 'fig2_cn_3d_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  图2已保存: fig2_cn_3d_comparison")


# ============================================================
# 图3: 柱状图对比
# ============================================================

def fig3_bar_chart_comparison(all_metrics):
    """所有策略的关键指标柱状图对比"""
    strategies = ['A_CN_4meas', 'A_CN_6meas', 'B_BCPN_4meas', 'B_BCPN_6meas',
                  'C_Temp_4meas', 'C_Temp_6meas', 'D_Comb_4meas', 'D_Comb_6meas']
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    
    colors = [COLORS[s] for s in strategies]
    labels = [LABELS[s] for s in strategies]
    
    # (a) 平均 CN
    ax = axes[0, 0]
    means = [all_metrics[s]['mean_cn'] for s in strategies]
    ax.bar(range(len(strategies)), means, color=colors, alpha=0.85, edgecolor='gray', lw=0.5)
    ax.axhline(y=IDEAL_CN, color='red', ls='--', lw=1.5, label=f'Ideal {IDEAL_CN:.3f}')
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Mean Condition Number', fontsize=11)
    ax.set_title('(a) 平均条件数', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    
    # (b) 温飘 (CN随温度标准差)
    ax = axes[0, 1]
    drifts = [all_metrics[s]['mean_cn_temp_std'] for s in strategies]
    ax.bar(range(len(strategies)), drifts, color=colors, alpha=0.85, edgecolor='gray', lw=0.5)
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('CN Std across Temperature', fontsize=11)
    ax.set_title('(b) 温飘幅度 (σ_CN across T)', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    
    # (c) BCPN总分量
    ax = axes[1, 0]
    bcpn = [all_metrics[s]['mean_bcpn_total'] for s in strategies]
    ax.bar(range(len(strategies)), bcpn, color=colors, alpha=0.85, edgecolor='gray', lw=0.5)
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Mean BCPN Sum', fontsize=11)
    ax.set_title('(c) 平均 BCPN 总和 (泊松噪声)', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    
    # (d) 综合损失 (高斯+泊松)
    ax = axes[1, 1]
    combined = [all_metrics[s]['mean_gauss_loss'] + all_metrics[s]['mean_poisson_loss'] 
                for s in strategies]
    ax.bar(range(len(strategies)), combined, color=colors, alpha=0.85, edgecolor='gray', lw=0.5)
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Combined Loss', fontsize=11)
    ax.set_title('(d) 综合损失 (高斯+泊松)', fontsize=12)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'fig3_bar_chart_comparison.pdf', dpi=300)
    plt.savefig(FIGURES_DIR / 'fig3_bar_chart_comparison.png', dpi=150)
    plt.close()
    print("  图3已保存: fig3_bar_chart_comparison")


# ============================================================
# 图4: 核心对比 — 4次 vs 6次测量在联合优化下的表现
# ============================================================

def fig4_meas_comparison():
    """联合优化下 4次 vs 6次 的 CN vs λ 对比"""
    all_params = load_params()
    selected_T = [0, 20, 40]
    
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    
    for idx, T in enumerate(selected_T):
        ax = axes[idx]
        lambdas_plot = np.arange(400, 701, 3)
        
        for name_prefix, ls in [('D_Comb_4meas', '-'), ('D_Comb_6meas', '--')]:
            params, is_6meas = all_params[name_prefix]
            cn_vals = []
            for lam in lambdas_plot:
                A = (get_A_6meas if is_6meas else get_A_4meas)(params, lam, T)
                cn_vals.append(safe_cond(A))
            ax.plot(lambdas_plot, cn_vals, ls=ls, lw=2, 
                   label=LABELS[name_prefix], color=COLORS[name_prefix])
        
        ax.axhline(y=IDEAL_CN, color='k', ls=':', lw=1, alpha=0.5)
        ax.set_xlabel('Wavelength (nm)', fontsize=11)
        ax.set_ylabel('Condition Number', fontsize=11)
        ax.set_title(f'T = {T}°C', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=9)
    
    plt.suptitle('联合优化: 4次 vs 6次测量 CN 对比', fontsize=13, y=1.03)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'fig4_4meas_vs_6meas_combined.pdf', dpi=300)
    plt.savefig(FIGURES_DIR / 'fig4_4meas_vs_6meas_combined.png', dpi=150)
    plt.close()
    print("  图4已保存: fig4_4meas_vs_6meas_combined")


# ============================================================
# 图5: 温度鲁棒性对比
# ============================================================

def fig5_temp_robustness():
    """关键策略的温度鲁棒性对比"""
    all_params = load_params()
    selected_strategies = ['A_CN_4meas', 'C_Temp_4meas', 'D_Comb_4meas', 'D_Comb_6meas']
    
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    
    # 左图: λ=550nm 处 CN vs T
    ax = axes[0]
    lam_target = 550.0
    
    for name in selected_strategies:
        params, is_6meas = all_params[name]
        T_range = np.arange(-10, 41, 2)
        cn_vals = []
        for T in T_range:
            A = (get_A_6meas if is_6meas else get_A_4meas)(params, lam_target, T)
            cn_vals.append(safe_cond(A))
        ax.plot(T_range, cn_vals, lw=2, label=LABELS[name], color=COLORS[name])
    
    ax.axhline(y=IDEAL_CN, color='k', ls=':', lw=1, alpha=0.5)
    ax.set_xlabel('Temperature (°C)', fontsize=11)
    ax.set_ylabel('Condition Number', fontsize=11)
    ax.set_title(f'Temperature Robustness at λ={lam_target:.0f}nm', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    
    # 右图: 全波段CN温度标准差
    ax = axes[1]
    strategies = ['A_CN_4meas', 'A_CN_6meas', 'B_BCPN_4meas', 'B_BCPN_6meas',
                  'C_Temp_4meas', 'C_Temp_6meas', 'D_Comb_4meas', 'D_Comb_6meas']
    
    for name in strategies:
        params, is_6meas = all_params[name]
        lambdas = np.arange(400, 701, 5)
        cn_per_T = []
        for lam in lambdas:
            cn_at_T = []
            for T in T_FINE:
                A = (get_A_6meas if is_6meas else get_A_4meas)(params, lam, T)
                cn_at_T.append(safe_cond(A))
            cn_per_T.append(np.std(cn_at_T))
        ax.plot(lambdas, cn_per_T, lw=1.8, label=LABELS[name], color=COLORS[name])
    
    ax.set_xlabel('Wavelength (nm)', fontsize=11)
    ax.set_ylabel('σ(CN) across Temperature', fontsize=11)
    ax.set_title('CN Temperature Fluctuation vs λ', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'fig5_temp_robustness.pdf', dpi=300)
    plt.savefig(FIGURES_DIR / 'fig5_temp_robustness.png', dpi=150)
    plt.close()
    print("  图5已保存: fig5_temp_robustness")


# ============================================================
# 生成所有图表
# ============================================================

def load_metrics():
    with open(TABLES_DIR / "comparison_metrics.json") as f:
        return json.load(f)


def load_grid_data():
    """加载网格数据（含cn_grid等大数组）"""
    with open(TABLES_DIR / "grid_data.json") as f:
        return json.load(f)


def generate_all_figures():
    """生成论文所有图表"""
    print("加载评估数据...")
    all_metrics = load_metrics()
    grid_data = load_grid_data()

    print("生成图1: CN vs 波长曲线 (每个策略单独)...")
    all_params = load_params()
    for name, (params, is_6meas) in all_params.items():
        fig1_cn_vs_wavelength(name, params, is_6meas)

    print("\n生成图2: CN 3D 曲面对比...")
    fig2_cn_3d_surface(grid_data)
    
    print("\n生成图3: 柱状图对比...")
    fig3_bar_chart_comparison(all_metrics)
    
    print("\n生成图4: 4次 vs 6次对比...")
    fig4_meas_comparison()
    
    print("\n生成图5: 温度鲁棒性...")
    fig5_temp_robustness()
    
    print(f"\n全部图表已保存至: {FIGURES_DIR}")


if __name__ == '__main__':
    generate_all_figures()
