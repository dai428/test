#!/usr/bin/env python3
"""MC Stokes误差分析：使用正确的GA参数 + 非线性Haller模型"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import numpy as np
from physics import retardance_nonlinear, build_matrix_6meas, build_matrix_4meas
import time

np.random.seed(42)
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ===== 真实参数（来自实验数据） =====
# 实际DE优化的GA 6meas
ga6 = np.array([-11.6622, -38.0113, 2.0632, 1.5000, 9.8189, 2.0367, 3.8169])
# 3目标膝点
d3 = np.load(os.path.join(root, 'results/exp_haller_v3/nsga2.npz'), allow_pickle=True)
pop3, fit3 = d3['pareto_front'], d3['pareto_fitnesses']
fn = (fit3 - fit3.min(0)) / (fit3.max(0) - fit3.min(0) + 1e-10)
k3 = pop3[np.argmin(np.sqrt((fn**2).sum(1)))]
# 2目标膝点
d2 = np.load(os.path.join(root, 'results/exp_ablation/nsga2_2obj.npz'), allow_pickle=True)
pop2, fit2 = d2['pareto_pop'], d2['pareto_fit']
f2n = (fit2 - fit2.min(0)) / (fit2.max(0) - fit2.min(0) + 1e-10)
k2 = pop2[np.argmin(np.sqrt((f2n**2).sum(1)))]

print(f"GA 6meas (真实DE): θ=[{ga6[0]:.2f},{ga6[1]:.2f}], V1={np.round(ga6[2:5],3)}, V2={np.round(ga6[5:7],3)}")
print(f"3目标膝点: θ=[{k3[0]:.2f},{k3[1]:.2f}], V1={np.round(k3[2:5],3)}, V2={np.round(k3[5:7],3)}")
print(f"2目标膝点: θ=[{k2[0]:.2f},{k2[1]:.2f}], V1={np.round(k2[2:5],3)}, V2={np.round(k2[5:7],3)}")

WL = np.linspace(350, 700, 36)
TEMPS = np.array([-10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40])
N_SAMPLE = 500
NOISE = 0.01

def compute_matrix_nl(params, T, wl, n_meas=6):
    θ1, θ2 = params[0], params[1]
    if n_meas == 6:
        v = [params[2], params[3], params[4], params[5], params[6]]
        rets = [retardance_nonlinear(wl, vv, T) for vv in v]
        return build_matrix_6meas(θ1, θ2, *rets)
    else:
        v = [params[2], params[3], params[4], params[5]]
        rets = [retardance_nonlinear(wl, vv, T) for vv in v]
        return build_matrix_4meas(θ1, θ2, *rets)

def mc_run(params, name, nm=6):
    res = {'CN': [], 'BCPN': [], 'RMSE_total': []}
    for T in TEMPS:
        s1e, s2e, s3e, te, cnv, bcpnv = [], [], [], [], [], []
        for wl in WL:
            A = compute_matrix_nl(params, T, wl, nm)
            cnv.append(np.linalg.cond(A))
            Ap = np.linalg.pinv(A)
            for _ in range(N_SAMPLE):
                th = np.random.uniform(0, np.pi)
                ph = np.random.uniform(0, 2*np.pi)
                S = np.array([1.0, np.cos(ph)*np.sin(th), np.sin(ph)*np.sin(th), np.cos(th)])
                I = A @ S
                In = I + np.random.normal(0, NOISE*np.mean(I), len(I)) + \
                     (np.random.poisson(I*1000)/1000.0 - I)*0.1
                Se = Ap @ In
                te.append(np.sum((Se-S)**2))
        res['CN'].append(np.mean(cnv))
        res['RMSE_total'].append(np.sqrt(np.mean(te)))
    return res

print("\n=== 非线性Haller MC（正确GA参数）===")
start = time.time()
all_r = {}
for name, params, nm in [("GA 6meas", ga6, 6),
                           ("2目标", k2, 6),
                           ("3目标", k3, 6)]:
    r = mc_run(params, name, nm)
    all_r[name] = r
    t25 = np.where(TEMPS==25)[0][0]
    dcn = max(r['CN']) - min(r['CN'])
    print(f"\n{name}:")
    print(f"  CN(25°C)={r['CN'][t25]:.4f}, ΔCN={dcn:.4f}")
    print(f"  RMSE(25°C)={r['RMSE_total'][t25]:.5f}, RMSE(avg)={np.mean(r['RMSE_total']):.5f}")
    for i, T in enumerate(TEMPS):
        if T in [-10, 0, 25, 40]:
            print(f"    T={T:3d}°C: CN={r['CN'][i]:.4f}, RMSE={r['RMSE_total'][i]:.5f}")

elapsed = time.time()-start
print(f"\n耗时: {elapsed:.1f}s")

# 保存
np.savez(os.path.join(root, 'results/monte_carlo/stokes_errors_correct_ga.npz'),
         temps=TEMPS,
         results={k: {kk: np.array(vv) for kk,vv in v.items()} for k,v in all_r.items()})
print("已保存: results/monte_carlo/stokes_errors_correct_ga.npz")
