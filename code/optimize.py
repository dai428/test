"""
LCVR Stokes Polarimeter — 对比策略优化
=========================================
4个对比策略（每个策略分别做4次和6次测量）:

策略A: 纯高斯噪声最优 (CN-only)   固定25°C
策略B: 纯泊松噪声最优 (BCPN-only) 固定25°C
策略C: 纯温漂鲁棒最优 (Temp-only) -10~40°C minimax
策略D: 联合最优 (Combined)        -10~40°C, 高斯+泊松
"""

import numpy as np
from scipy.optimize import differential_evolution
import time
import json
from pathlib import Path

from models import (
    get_A_4meas, get_A_6meas,
    safe_cond, compute_bcpn,
    gauss_loss, poisson_loss,
    BOUNDS_4MEAS, BOUNDS_6MEAS, IDEAL_CN
)

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ============================================================
# 公共优化参数（串行 workers=1 避免 WSL 崩溃）
# ============================================================
DE_KWARGS = dict(
    strategy='rand1bin',
    maxiter=300,
    popsize=15,
    tol=1e-6,
    mutation=(0.6, 0.9),
    recombination=0.85,
    polish=True,
    workers=1,
    updating='immediate',
    seed=42,
    disp=False,
)

# 联合优化泊松项权重
ALPHA = 0.001

# 温漂策略温度采样
T_TEMP_ONLY = np.arange(-10, 41, 10)   # -10, 0, 10, 20, 30, 40

# 公共波长采样（策略A/B/C用）
LAMBDAS = np.arange(350, 701, 10)

# 联合优化采样（更稀疏以加速）
LAMBDAS_COMB = np.arange(350, 701, 20)    # 18点
T_COMBINED = [-10, 5, 20, 40]             # 4个温度

# 联合优化DE参数（轻量级）
DE_COMB_KWARGS = dict(DE_KWARGS, maxiter=200, popsize=12)


# ============================================================
# 策略A: 纯高斯噪声最优 (CN-only)
# ============================================================

def _fitness_gauss_4meas(params):
    total = 0.0
    for lam in LAMBDAS:
        A = get_A_4meas(params, lam, 25.0)
        total += gauss_loss(safe_cond(A))
    return total / len(LAMBDAS)


def _fitness_gauss_6meas(params):
    total = 0.0
    for lam in LAMBDAS:
        A = get_A_6meas(params, lam, 25.0)
        total += gauss_loss(safe_cond(A))
    return total / len(LAMBDAS)


def optimize_gauss(label: str):
    is_6meas = '6次' in label
    bounds = BOUNDS_6MEAS if is_6meas else BOUNDS_4MEAS
    fitness = _fitness_gauss_6meas if is_6meas else _fitness_gauss_4meas
    t0 = time.time()
    result = differential_evolution(fitness, bounds, **DE_KWARGS)
    print(f"  → 最优值={result.fun:.6e}, 耗时={time.time()-t0:.0f}s, θ₁={result.x[0]:.1f}° θ₂={result.x[1]:.1f}°")
    return result.x


# ============================================================
# 策略B: 纯泊松噪声最优 (BCPN-only)
# ============================================================

def _fitness_bcpn_4meas(params):
    total = 0.0
    for lam in LAMBDAS:
        A = get_A_4meas(params, lam, 25.0)
        q0, q1, q2, q3 = compute_bcpn(A)
        total += q0 + q1 + q2 + q3
    return total / len(LAMBDAS)


def _fitness_bcpn_6meas(params):
    total = 0.0
    for lam in LAMBDAS:
        A = get_A_6meas(params, lam, 25.0)
        q0, q1, q2, q3 = compute_bcpn(A)
        total += q0 + q1 + q2 + q3
    return total / len(LAMBDAS)


def optimize_bcpn(label: str):
    is_6meas = '6次' in label
    bounds = BOUNDS_6MEAS if is_6meas else BOUNDS_4MEAS
    fitness = _fitness_bcpn_6meas if is_6meas else _fitness_bcpn_4meas
    t0 = time.time()
    result = differential_evolution(fitness, bounds, **DE_KWARGS)
    print(f"  → 最优值={result.fun:.6e}, 耗时={time.time()-t0:.0f}s")
    return result.x


# ============================================================
# 策略C: 纯温漂鲁棒最优 (Temp-only, minimax)
# ============================================================

def _fitness_temp_4meas(params):
    """Minimax: 最小化全温域内最差温度的平均高斯损失"""
    temp_max_errors = []
    for T in T_TEMP_ONLY:
        total = 0.0
        for lam in LAMBDAS:
            A = get_A_4meas(params, lam, T)
            total += gauss_loss(safe_cond(A))
        temp_max_errors.append(total / len(LAMBDAS))
    return max(temp_max_errors)


def _fitness_temp_6meas(params):
    temp_max_errors = []
    for T in T_TEMP_ONLY:
        total = 0.0
        for lam in LAMBDAS:
            A = get_A_6meas(params, lam, T)
            total += gauss_loss(safe_cond(A))
        temp_max_errors.append(total / len(LAMBDAS))
    return max(temp_max_errors)


def optimize_temp(label: str):
    is_6meas = '6次' in label
    bounds = BOUNDS_6MEAS if is_6meas else BOUNDS_4MEAS
    fitness = _fitness_temp_6meas if is_6meas else _fitness_temp_4meas
    t0 = time.time()
    result = differential_evolution(fitness, bounds, **DE_KWARGS)
    print(f"  → 最优值={result.fun:.6e}, 耗时={time.time()-t0:.0f}s")
    return result.x


# ============================================================
# 策略D: 联合最优 (高斯+泊松+温漂)
# ============================================================

def _fitness_combined_4meas(params):
    """
    联合优化: 在全温域上最小化 (高斯损失 + α × 泊松损失)
    高斯: (1/√3 - 1/CN)^4
    泊松: Σ||q_k||^4  (四次方对大值更敏感)
    α=0.001 使两项量级相当
    """
    total = 0.0
    n = 0
    for T in T_COMBINED:
        for lam in LAMBDAS_COMB:
            A = get_A_4meas(params, lam, T)
            g_loss = gauss_loss(safe_cond(A))
            q0, q1, q2, q3 = compute_bcpn(A)
            p_loss = poisson_loss(q0, q1, q2, q3)
            total += g_loss + ALPHA * p_loss
            n += 1
    return total / n


def _fitness_combined_6meas(params):
    total = 0.0
    n = 0
    for T in T_COMBINED:
        for lam in LAMBDAS_COMB:
            A = get_A_6meas(params, lam, T)
            g_loss = gauss_loss(safe_cond(A))
            q0, q1, q2, q3 = compute_bcpn(A)
            p_loss = poisson_loss(q0, q1, q2, q3)
            total += g_loss + ALPHA * p_loss
            n += 1
    return total / n


def optimize_combined(label: str):
    is_6meas = '6次' in label
    bounds = BOUNDS_6MEAS if is_6meas else BOUNDS_4MEAS
    fitness = _fitness_combined_6meas if is_6meas else _fitness_combined_4meas
    t0 = time.time()
    result = differential_evolution(fitness, bounds, **DE_COMB_KWARGS)
    print(f"  → 最优值={result.fun:.6e}, 耗时={time.time()-t0:.0f}s")
    return result.x


# ============================================================
# 运行所有优化
# ============================================================

def run_all_optimizations():
    strategies = {
        'A_CN_4meas':  ('4次', 'gauss'),
        'A_CN_6meas':  ('6次', 'gauss'),
        'B_BCPN_4meas': ('4次', 'bcpn'),
        'B_BCPN_6meas': ('6次', 'bcpn'),
        'C_Temp_4meas': ('4次', 'temp'),
        'C_Temp_6meas': ('6次', 'temp'),
        'D_Comb_4meas': ('4次', 'combined'),
        'D_Comb_6meas': ('6次', 'combined'),
    }

    results = {}
    for key, (label, strategy) in strategies.items():
        print(f"\n{'='*60}")
        if strategy == 'gauss':
            print(f"  策略A: 纯高斯噪声最优 [{label}]")
            print(f"{'='*60}")
            params = optimize_gauss(label)
        elif strategy == 'bcpn':
            print(f"  策略B: 纯泊松噪声最优(BCPN) [{label}]")
            print(f"{'='*60}")
            params = optimize_bcpn(label)
        elif strategy == 'temp':
            print(f"  策略C: 纯温漂鲁棒最优 [Minimax, {label}]")
            print(f"{'='*60}")
            params = optimize_temp(label)
        elif strategy == 'combined':
            print(f"  策略D: 联合最优 [高斯+泊松+温漂 α={ALPHA}, {label}]")
            print(f"{'='*60}")
            params = optimize_combined(label)

        results[key] = {'params': params.tolist()}
        with open(RESULTS_DIR / f"{key}.json", 'w') as f:
            json.dump({'params': params.tolist()}, f, indent=2)

    # 保存汇总
    with open(RESULTS_DIR / "all_optimizations.json", 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  所有优化完成! 结果保存至: {RESULTS_DIR}")
    print(f"{'='*60}")
    return results


if __name__ == '__main__':
    run_all_optimizations()
