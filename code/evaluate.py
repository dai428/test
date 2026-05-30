"""
LCVR Stokes Polarimeter — 统一对比评估
=========================================
对每个策略在整个(λ, T)空间上做精细评估，输出对比表格。
"""

import numpy as np
import json
from pathlib import Path
from itertools import product

from models import (
    get_A_4meas, get_A_6meas,
    safe_cond, compute_bcpn,
    gauss_loss, poisson_loss, IDEAL_CN
)

RESULTS_DIR = Path(__file__).parent / "results"
TABLES_DIR = RESULTS_DIR / "tables"
TABLES_DIR.mkdir(exist_ok=True)


# ============================================================
# 精细评估网格
# ============================================================
LAMBDAS_FINE = np.arange(400, 701, 2)     # 精细波长步长
T_FINE = np.arange(-10, 41, 5)            # -10°C ~ 40°C


# ============================================================
# 评估单个策略
# ============================================================

def evaluate_strategy(params, is_6meas, lambdas=None, temps=None):
    """
    在(λ, T)网格上全面评估一个策略
    
    返回 dict:
      mean_cn, std_cn, max_cn, min_cn
      mean_bcpn (Σ||q_k||)
      mean_gauss_loss, mean_poisson_loss
      cn_grid (T×λ), bcpn_grid (T×λ)
      cn_vs_lambda_T_variation (CN在每个λ下随T波动的标准差均值)
    """
    if lambdas is None:
        lambdas = LAMBDAS_FINE
    if temps is None:
        temps = T_FINE
    
    get_A = get_A_6meas if is_6meas else get_A_4meas
    
    nT, nL = len(temps), len(lambdas)
    cn_grid = np.zeros((nT, nL))
    gauss_grid = np.zeros((nT, nL))
    poisson_grid = np.zeros((nT, nL))
    bcpn_total_grid = np.zeros((nT, nL))
    
    for i, T in enumerate(temps):
        for j, lam in enumerate(lambdas):
            A = get_A(params, lam, T)
            cn = safe_cond(A)
            q0, q1, q2, q3 = compute_bcpn(A)
            
            cn_grid[i, j] = cn
            gauss_grid[i, j] = gauss_loss(cn)
            poisson_grid[i, j] = poisson_loss(q0, q1, q2, q3)
            bcpn_total_grid[i, j] = q0 + q1 + q2 + q3
    
    # CN指标
    mean_cn = float(np.mean(cn_grid))
    std_cn = float(np.std(cn_grid))
    max_cn = float(np.max(cn_grid))
    min_cn = float(np.min(cn_grid))
    
    # 温度波动: 每个波长下 CN 随T的波动
    cn_per_lambda_std = np.std(cn_grid, axis=0)  # 每个λ的CN标准差（跨温度）
    mean_cn_temp_std = float(np.mean(cn_per_lambda_std))
    
    # 损失指标
    mean_gauss = float(np.mean(gauss_grid))
    mean_poisson = float(np.mean(poisson_grid))
    mean_bcpn = float(np.mean(bcpn_total_grid))
    
    # 各BCPN分量平均值
    bcpn_components_avg = [0.0, 0.0, 0.0, 0.0]
    count = 0
    for T in temps:
        for lam in lambdas:
            A = get_A(params, lam, T)
            qs = compute_bcpn(A)
            for k in range(4):
                bcpn_components_avg[k] += qs[k]
            count += 1
    bcpn_components_avg = [v / count for v in bcpn_components_avg]
    
    return {
        'mean_cn': mean_cn,
        'std_cn': std_cn,
        'max_cn': max_cn,
        'min_cn': min_cn,
        'mean_cn_temp_std': mean_cn_temp_std,
        'mean_gauss_loss': mean_gauss,
        'mean_poisson_loss': mean_poisson,
        'mean_bcpn_total': mean_bcpn,
        'bcpn_q0': bcpn_components_avg[0],
        'bcpn_q1': bcpn_components_avg[1],
        'bcpn_q2': bcpn_components_avg[2],
        'bcpn_q3': bcpn_components_avg[3],
        'cn_grid': cn_grid.tolist(),
        'gauss_grid': gauss_grid.tolist(),
        'poisson_grid': poisson_grid.tolist(),
        'bcpn_grid': bcpn_total_grid.tolist(),
    }


# ============================================================
# 输出对比表格
# ============================================================

def format_table_row(name, metrics):
    """格式化一行表格数据"""
    cn = f"{metrics['mean_cn']:.3f}±{metrics['std_cn']:.3f}"
    cn_range = f"{metrics['min_cn']:.2f}~{metrics['max_cn']:.2f}"
    cn_drift = f"{metrics['mean_cn_temp_std']:.4f}"
    bcpn = f"{metrics['mean_bcpn_total']:.4f}"
    q = [f"{metrics[f'bcpn_q{k}']:.4f}" for k in range(4)]
    return f"  {name:<20s}  {cn:<18s}  {cn_range:<18s}  {cn_drift:<10s}  {bcpn:<10s}"


def print_comparison_table(all_metrics):
    """打印完整的对比表格"""
    
    print("\n" + "="*120)
    print("  综合性能对比")
    print("="*120)
    print(f"  评估范围: λ∈[400,700]nm, T∈[-10,50]°C")
    print(f"  理想条件数: √3 ≈ {IDEAL_CN:.4f}")
    print()
    print(f"  {'策略':<20s}  {'平均CN':<18s}  {'CN范围':<18s}  {'温飘σ_CN':<10s}  {'BCPN':<10s}")
    print(f"  {'-'*20}  {'-'*18}  {'-'*18}  {'-'*10}  {'-'*10}")
    
    for name in ['A_CN_4meas', 'A_CN_6meas', 'B_BCPN_4meas', 'B_BCPN_6meas',
                  'C_Temp_4meas', 'C_Temp_6meas', 'D_Comb_4meas', 'D_Comb_6meas']:
        if name in all_metrics:
            print(format_table_row(name, all_metrics[name]))
    
    print(f"  {'-'*20}  {'-'*18}  {'-'*18}  {'-'*10}  {'-'*10}")
    
    # 打印BCPN分量明细
    print()
    print(f"  BCPN分量明细:")
    print(f"  {'策略':<20s}  {'||q0||':<10s}  {'||q1||':<10s}  {'||q2||':<10s}  {'||q3||':<10s}")
    print(f"  {'-'*20}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*10}")
    for name in ['A_CN_4meas', 'A_CN_6meas', 'B_BCPN_4meas', 'B_BCPN_6meas',
                  'C_Temp_4meas', 'C_Temp_6meas', 'D_Comb_4meas', 'D_Comb_6meas']:
        if name in all_metrics:
            m = all_metrics[name]
            q = [f"{m[f'bcpn_q{k}']:.4f}" for k in range(4)]
            print(f"  {name:<20s}  {q[0]:<10s}  {q[1]:<10s}  {q[2]:<10s}  {q[3]:<10s}")
    
    print("="*120)
    print()


def save_json_metrics(all_metrics):
    """保存评估结果JSON"""
    # 移除grid数据（太大）
    serializable = {}
    for k, v in all_metrics.items():
        serializable[k] = {kk: vv for kk, vv in v.items() 
                          if kk not in ['cn_grid', 'gauss_grid', 'poisson_grid', 'bcpn_grid']}
    
    with open(TABLES_DIR / "comparison_metrics.json", 'w') as f:
        json.dump(serializable, f, indent=2)
    
    # 也保存grid数据供绘图用
    grid_data = {}
    for k, v in all_metrics.items():
        if 'cn_grid' in v:
            grid_data[k] = {
                'cn_grid': v['cn_grid'],
                'gauss_grid': v['gauss_grid'],
                'poisson_grid': v['poisson_grid'],
                'bcpn_grid': v['bcpn_grid'],
            }
    with open(TABLES_DIR / "grid_data.json", 'w') as f:
        json.dump(grid_data, f, indent=2)


# ============================================================
# 执行评估
# ============================================================

def load_params():
    """加载所有优化参数"""
    with open(RESULTS_DIR / "all_optimizations.json") as f:
        data = json.load(f)
    
    strategies = {
        'A_CN_4meas':  (np.array(data['A_CN_4meas']['params']),  False),
        'A_CN_6meas':  (np.array(data['A_CN_6meas']['params']),  True),
        'B_BCPN_4meas':  (np.array(data['B_BCPN_4meas']['params']), False),
        'B_BCPN_6meas':  (np.array(data['B_BCPN_6meas']['params']), True),
        'C_Temp_4meas':  (np.array(data['C_Temp_4meas']['params']), False),
        'C_Temp_6meas':  (np.array(data['C_Temp_6meas']['params']), True),
        'D_Comb_4meas':  (np.array(data['D_Comb_4meas']['params']), False),
        'D_Comb_6meas':  (np.array(data['D_Comb_6meas']['params']), True),
    }
    return strategies


def run_evaluation():
    """运行全部策略评估"""
    print("加载优化参数...")
    strategies = load_params()
    
    all_metrics = {}
    for name, (params, is_6meas) in strategies.items():
        print(f"  评估 {name}...")
        metrics = evaluate_strategy(params, is_6meas)
        all_metrics[name] = metrics
    
    print_comparison_table(all_metrics)
    save_json_metrics(all_metrics)
    
    return all_metrics


if __name__ == '__main__':
    run_evaluation()
