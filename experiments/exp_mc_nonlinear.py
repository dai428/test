#!/usr/bin/env python3
"""MC Stokes误差分析：使用非线性Haller模型"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import numpy as np
from physics import retardance_nonlinear, build_matrix_6meas, build_matrix_4meas
import json, time

np.random.seed(42)
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 加载优化结果
data3 = np.load(os.path.join(root, 'results/exp_haller_v3/nsga2.npz'), allow_pickle=True)
pop3, fit3 = data3['pareto_front'], data3['pareto_fitnesses']
f1n=(fit3[:,0]-fit3[:,0].min())/(fit3[:,0].max()-fit3[:,0].min()+1e-10)
f2n=(fit3[:,1]-fit3[:,1].min())/(fit3[:,1].max()-fit3[:,1].min()+1e-10)
f3n=(fit3[:,2]-fit3[:,2].min())/(fit3[:,2].max()-fit3[:,2].min()+1e-10)
k3_params = pop3[np.argmin(np.sqrt(f1n**2+f2n**2+f3n**2))]

data2 = np.load(os.path.join(root, 'results/exp_ablation/nsga2_2obj.npz'), allow_pickle=True)
pop2, fit2 = data2['pareto_pop'], data2['pareto_fit']
f2a=(fit2[:,0]-fit2[:,0].min())/(fit2[:,0].max()-fit2[:,0].min()+1e-10)
f2b=(fit2[:,1]-fit2[:,1].min())/(fit2[:,1].max()-fit2[:,1].min()+1e-10)
k2_params = pop2[np.argmin(np.sqrt(f2a**2+f2b**2))]

ga6_params = np.array([-72.51, -18.62, 9.80, 2.20, 3.15, 8.48, 1.97])

WL = np.linspace(350, 700, 36)
TEMPS = np.array([-10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40])
N_SAMPLE = 500
NOISE = 0.01

def compute_matrix_nl(params, T, wl, n_meas=6):
    θ1, θ2 = params[0], params[1]
    if n_meas == 4:
        v = [params[2], params[3], params[4], params[5]]
        rets = [retardance_nonlinear(wl, vv, T) for vv in v]
        return build_matrix_4meas(θ1, θ2, *rets)
    else:
        v = [params[2], params[3], params[4], params[5], params[6]]
        rets = [retardance_nonlinear(wl, vv, T) for vv in v]
        return build_matrix_6meas(θ1, θ2, *rets)

def mc_run(params, name, nm=6):
    res = {'CN': [], 'BCPN': [], 'RMSE_S1': [], 'RMSE_S2': [], 'RMSE_S3': [], 'RMSE_total': []}
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
                In = I + np.random.normal(0, NOISE*np.mean(I), len(I)) + (np.random.poisson(I*1000)/1000.0 - I)*0.1
                Se = Ap @ In
                s1e.append((Se[1]-S[1])**2); s2e.append((Se[2]-S[2])**2)
                s3e.append((Se[3]-S[3])**2); te.append(np.sum((Se-S)**2))
        res['CN'].append(np.mean(cnv))
        res['RMSE_S1'].append(np.sqrt(np.mean(s1e)))
        res['RMSE_S2'].append(np.sqrt(np.mean(s2e)))
        res['RMSE_S3'].append(np.sqrt(np.mean(s3e)))
        res['RMSE_total'].append(np.sqrt(np.mean(te)))
    return res

print("=== 非线性Haller MC Stokes误差分析 ===")
start = time.time()
all_r = {}
for name, params, nm in [("GA 6meas", ga6_params, 6),
                           ("2目标(无温漂)", k2_params, 6),
                           ("3目标(有温漂)", k3_params, 6)]:
    print(f"\n--- {name} ---")
    r = mc_run(params, name, nm)
    all_r[name] = r
    for i, T in enumerate(TEMPS):
        if T in [-10, 0, 25, 40]:
            print(f"  T={T:3d}°C: CN={r['CN'][i]:.4f}, Total RMSE={r['RMSE_total'][i]:.5f}")

elapsed = time.time()-start
print(f"\n耗时: {elapsed:.1f}s")

# 对比线性MC结果
d_lin = np.load(os.path.join(root, 'results/monte_carlo/stokes_errors.npz'), allow_pickle=True)
r_lin = d_lin['results'].item()

print("\n=== 线性 vs 非线性：核心指标对比 ===")
for name in ['GA 6meas', '2目标(无温漂)', '3目标(有温漂)']:
    rl = r_lin[name]
    rn = all_r[name]
    print(f"\n{name}:")
    for i, T in enumerate(TEMPS):
        if T in [-10, 25, 40]:
            print(f"  T={T:3d}°C: CN_{'lin'}={rl['CN_all'][i]:.4f}→CN_{'nl'}={rn['CN'][i]:.4f}, "
                  f"RMSE_lin={rl['RMSE_total'][i]:.5f}→RMSE_nl={rn['RMSE_total'][i]:.5f}")
    print(f"  ΔCN_lin={max(rl['CN_all'])-min(rl['CN_all']):.4f}, ΔCN_nl={max(rn['CN'])-min(rn['CN']):.4f}")

# 保存
np.savez(os.path.join(root, 'results/monte_carlo/stokes_errors_nonlinear.npz'),
         temps=TEMPS, results={k: {kk: np.array(vv) for kk,vv in v.items()} for k,v in all_r.items()})
