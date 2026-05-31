#!/usr/bin/env python3
"""Monte Carlo Stokes误差分析 + Poincaré球调制态分布"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json, time
from physics import retardance, build_matrix_6meas, build_matrix_4meas
from metrics import condition_number, compute_bcpn

np.random.seed(42)

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ===== 加载优化结果 =====
# 3目标膝点
data3 = np.load(os.path.join(root, 'results/exp_haller_v3/nsga2.npz'), allow_pickle=True)
pop3, fit3 = data3['pareto_front'], data3['pareto_fitnesses']
f1n = (fit3[:,0]-fit3[:,0].min())/(fit3[:,0].max()-fit3[:,0].min()+1e-10)
f2n = (fit3[:,1]-fit3[:,1].min())/(fit3[:,1].max()-fit3[:,1].min()+1e-10)
f3n = (fit3[:,2]-fit3[:,2].min())/(fit3[:,2].max()-fit3[:,2].min()+1e-10)
k3_idx = np.argmin(np.sqrt(f1n**2+f2n**2+f3n**2))
k3_params = pop3[k3_idx]  # [θ1,θ2,V11,V12,V13,V21,V22]

# 2目标膝点
data2 = np.load(os.path.join(root, 'results/exp_ablation/nsga2_2obj.npz'), allow_pickle=True)
pop2, fit2 = data2['pareto_pop'], data2['pareto_fit']
f2a = (fit2[:,0]-fit2[:,0].min())/(fit2[:,0].max()-fit2[:,0].min()+1e-10)
f2b = (fit2[:,1]-fit2[:,1].min())/(fit2[:,1].max()-fit2[:,1].min()+1e-10)
k2_idx = np.argmin(np.sqrt(f2a**2+f2b**2))
k2_params = pop2[k2_idx]  # [θ1,θ2,V11,V12,V13,V21,V22]

# 单目标GA 6meas (from DE optimization results: θ=-11.66°, -38.01°)
# [-11.6622, -38.0113, 2.0632, 1.5000, 9.8189, 2.0367, 3.8169]
ga6_params = np.array([-11.6622, -38.0113, 2.0632, 1.5000, 9.8189, 2.0367, 3.8169])

# 单目标GA 4meas
ga4_params = np.array([-70.06, -10.48, 2.79, 7.21, 6.23, 3.95])

print("=== 参数加载完成 ===")
print(f"3目标膝点: θ=[{k3_params[0]:.2f},{k3_params[1]:.2f}], V1={np.round(k3_params[2:5],2)}, V2={np.round(k3_params[5:7],2)}")
print(f"2目标膝点: θ=[{k2_params[0]:.2f},{k2_params[1]:.2f}], V1={np.round(k2_params[2:5],2)}, V2={np.round(k2_params[5:7],2)}")
print(f"GA 6meas:  θ=[{ga6_params[0]:.2f},{ga6_params[1]:.2f}], V1={np.round(ga6_params[2:5],2)}, V2={np.round(ga6_params[5:7],2)}")
print(f"GA 4meas:  θ=[{ga4_params[0]:.2f},{ga4_params[1]:.2f}], V1={np.round(ga4_params[2:4],2)}, V2={np.round(ga4_params[4:6],2)}")

# ===== 参数设置 =====
wl_all = np.linspace(350, 700, 36)
temps = np.array([-10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40])
n_stokes = 500  # Monte Carlo样本数
noise_level = 0.01  # 相对噪声水平

def build_4meas_matrix(theta1, theta2, d11, d12, d21, d22):
    return build_matrix_4meas(theta1, theta2, d11, d12, d21, d22)

def build_6meas_matrix(theta1, theta2, d11, d12, d13, d21, d22):
    return build_matrix_6meas(theta1, theta2, d11, d12, d13, d21, d22)

def compute_matrix(params, temperature, wl, n_meas=6):
    """计算给定温度下的测量矩阵"""
    θ1, θ2 = params[0], params[1]
    if n_meas == 4:
        v11, v12, v21, v22 = params[2], params[3], params[4], params[5]
        d11 = retardance(wl, v11, temperature)
        d12 = retardance(wl, v12, temperature)
        d21 = retardance(wl, v21, temperature)
        d22 = retardance(wl, v22, temperature)
        return build_4meas_matrix(θ1, θ2, d11, d12, d21, d22)
    else:
        v11, v12, v13, v21, v22 = params[2], params[3], params[4], params[5], params[6]
        d11 = retardance(wl, v11, temperature)
        d12 = retardance(wl, v12, temperature)
        d13 = retardance(wl, v13, temperature)
        d21 = retardance(wl, v21, temperature)
        d22 = retardance(wl, v22, temperature)
        return build_6meas_matrix(θ1, θ2, d11, d12, d13, d21, d22)

# ===== Monte Carlo Stokes重建 =====
def monte_carlo_stokes(method_params, method_name, n_meas=6):
    """Monte Carlo模拟Stokes重建误差"""
    np.random.seed(42)
    results = {'CN_all': [], 'BCPN_all': [], 'RMSE_S1': [], 'RMSE_S2': [], 'RMSE_S3': [], 'RMSE_total': []}
    
    for T in temps:
        s1_errs, s2_errs, s3_errs, total_errs = [], [], [], []
        cn_vals, bcpn_vals = [], []
        
        for wl in wl_all:
            A = compute_matrix(method_params, T, wl, n_meas)
            cn = np.linalg.cond(A)
            bcpn_all = compute_bcpn(A)
            bcpn_val = bcpn_all['q_sum']
            cn_vals.append(cn)
            bcpn_vals.append(bcpn_val)
            Ap = np.linalg.pinv(A)
            
            for _ in range(n_stokes):
                # 随机Stokes向量（覆盖Poincaré球）
                s0 = 1.0
                theta_s = np.random.uniform(0, np.pi)
                phi_s = np.random.uniform(0, 2*np.pi)
                s1 = np.cos(phi_s) * np.sin(theta_s)
                s2 = np.sin(phi_s) * np.sin(theta_s)
                s3 = np.cos(theta_s)
                S_true = np.array([s0, s1, s2, s3])
                
                # 理想测量强度
                I_true = A @ S_true
                
                # 高斯噪声
                noise_g = np.random.normal(0, noise_level * np.mean(I_true), len(I_true))
                
                # 散粒噪声（泊松近似为高斯）
                I_shot = np.random.poisson(I_true * 1000) / 1000.0  # 1000光子计数
                
                # 总噪声
                I_noisy = I_true + noise_g + (I_shot - I_true) * 0.1
                
                # Stokes重建
                S_est = Ap @ I_noisy
                
                # 误差
                s1_errs.append((S_est[1] - s1)**2)
                s2_errs.append((S_est[2] - s2)**2)
                s3_errs.append((S_est[3] - s3)**2)
                total_errs.append(np.sum((S_est - S_true)**2))
        
        results['CN_all'].append(np.mean(cn_vals))
        results['BCPN_all'].append(np.mean(bcpn_vals))
        results['RMSE_S1'].append(np.sqrt(np.mean(s1_errs)))
        results['RMSE_S2'].append(np.sqrt(np.mean(s2_errs)))
        results['RMSE_S3'].append(np.sqrt(np.mean(s3_errs)))
        results['RMSE_total'].append(np.sqrt(np.mean(total_errs)))
    
    return results

# 执行MC模拟
print("\n=== Monte Carlo Stokes误差分析 ===")
print("样本数: %d / 温度点: %d / 波长: %d" % (n_stokes, len(temps), len(wl_all)))
start = time.time()

all_results = {}
for name, params, nm in [
    ("GA 4meas", ga4_params, 4),
    ("GA 6meas", ga6_params, 6),
    ("2目标(无温漂)", k2_params, 6),
    ("3目标(有温漂)", k3_params, 6),
]:
    print(f"\n--- {name} ---")
    res = monte_carlo_stokes(params, name, nm)
    all_results[name] = res
    
    # 打印关键温度点的结果
    for i, T in enumerate(temps):
        if T in [-10, 0, 25, 40]:
            print(f"  T={T:3d}°C: CN={res['CN_all'][i]:.4f}, BCPN={res['BCPN_all'][i]:.4f}, "
                  f"RMSE_S1={res['RMSE_S1'][i]:.5f}, RMSE_S2={res['RMSE_S2'][i]:.5f}, "
                  f"RMSE_S3={res['RMSE_S3'][i]:.5f}, RMSE总={res['RMSE_total'][i]:.5f}")

elapsed = time.time() - start
print(f"\n耗时: {elapsed:.1f}s")

# ===== 保存数据 =====
out_dir = os.path.join(root, 'results/monte_carlo')
os.makedirs(out_dir, exist_ok=True)
np.savez(os.path.join(out_dir, 'stokes_errors.npz'),
         temps=temps, wl_all=wl_all, n_stokes=n_stokes,
         results={k: {kk: np.array(vv) for kk, vv in v.items()} for k, v in all_results.items()})
print(f"\n数据已保存: {out_dir}")

# ===== 画图 =====
colors = {'GA 4meas': '#95A5A6', 'GA 6meas': '#7F8C8D', 
          '2目标(无温漂)': '#E74C3C', '3目标(有温漂)': '#2E86C1'}

# 图1: RMSE随温度变化
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
fig.patch.set_facecolor('white')
metrics = [('RMSE_S1', 'S₁ RMSE'), ('RMSE_S2', 'S₂ RMSE'), ('RMSE_S3', 'S₃ RMSE'), ('RMSE_total', 'Total RMSE')]
for ax, (key, ylabel) in zip(axes.flat, metrics):
    for name in ['GA 4meas', 'GA 6meas', '2目标(无温漂)', '3目标(有温漂)']:
        ax.plot(temps, all_results[name][key], 'o-', color=colors[name], label=name, linewidth=1.5, markersize=4)
    ax.set_xlabel('Temperature (°C)', fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(os.path.join(root, 'figures/monte_carlo_rmse.png'), dpi=300, bbox_inches='tight')
print("图1 saved: figures/monte_carlo_rmse.png")

# 图2: 25°C下各Stokes分量RMSE柱状图
fig, ax = plt.subplots(figsize=(10, 5))
fig.patch.set_facecolor('white')
t25_idx = np.where(temps == 25)[0][0]
methods = ['GA4', 'GA6', '2-obj', '3-obj']
x = np.arange(len(methods))
w = 0.2
for i, (key, label, offset) in enumerate([('RMSE_S1', 'S₁', -1.5), ('RMSE_S2', 'S₂', -0.5), 
                                            ('RMSE_S3', 'S₃', 0.5), ('RMSE_total', 'Total', 1.5)]):
    vals = [all_results[m][key][t25_idx] for m in ['GA 4meas', 'GA 6meas', '2目标(无温漂)', '3目标(有温漂)']]
    bars = ax.bar(x + offset*w, vals, w*0.8, label=label, alpha=0.8)
ax.set_xticks(x)
ax.set_xticklabels(methods)
ax.set_ylabel('RMSE', fontsize=12)
ax.set_title('Stokes Reconstruction Error at 25°C', fontsize=13, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
fig.savefig(os.path.join(root, 'figures/monte_carlo_bar.png'), dpi=300, bbox_inches='tight')
print("图2 saved: figures/monte_carlo_bar.png")

# ===== Poincaré球调制态分布图 =====
from mpl_toolkits.mplot3d import Axes3D

def get_modulation_states(params, n_meas=6):
    """获取测量矩阵每行的归一化Stokes分析方向（S1,S2,S3分量）"""
    states = []
    for wl in wl_all:
        for T in [25]:  # 室温
            A = compute_matrix(params, T, wl, n_meas)
            # 每行去掉S0分量，归一化
            for row in A:
                s = row[1:4]
                norm = np.linalg.norm(s)
                if norm > 1e-10:
                    states.append(s / norm)
    return np.array(states)

fig = plt.figure(figsize=(14, 6))
fig.patch.set_facecolor('white')

for idx, (name, params, nm) in enumerate([
    ("GA 6meas (25°C)", ga6_params, 6),
    ("2-obj (25°C)", k2_params, 6),
    ("3-obj (25°C)", k3_params, 6),
]):
    states = get_modulation_states(params, nm)
    ax = fig.add_subplot(1, 3, idx+1, projection='3d')
    
    # 绘制单位球
    u = np.linspace(0, 2*np.pi, 20)
    v = np.linspace(0, np.pi, 20)
    x = np.outer(np.cos(u), np.sin(v))
    y = np.outer(np.sin(u), np.sin(v))
    z = np.outer(np.ones(np.size(u)), np.cos(v))
    ax.plot_wireframe(x, y, z, alpha=0.1, color='gray')
    
    # 绘制调制态
    ax.scatter(states[:, 0], states[:, 1], states[:, 2], 
               c='#2E86C1', s=15, alpha=0.6)
    
    # 重心
    center = np.mean(states, axis=0)
    ax.scatter([center[0]], [center[1]], [center[2]], 
               c='#E74C3C', s=50, marker='*', label='Centroid')
    
    ax.set_xlabel('S₁'); ax.set_ylabel('S₂'); ax.set_zlabel('S₃')
    ax.set_title(name, fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.view_init(elev=20, azim=45)

plt.tight_layout()
fig.savefig(os.path.join(root, 'figures/poincare_sphere.png'), dpi=300, bbox_inches='tight')
print("图3 saved: figures/poincare_sphere.png")
plt.close('all')

# 打印关键对比表
print("\n=== 25°C Stokes重建误差对比表 ===")
print(f"{'方法':<20} {'CN':>8} {'BCPN':>8} {'S₁ RMSE':>10} {'S₂ RMSE':>10} {'S₃ RMSE':>10} {'Total RMSE':>12}")
print("-"*80)
for name in ['GA 4meas', 'GA 6meas', '2目标(无温漂)', '3目标(有温漂)']:
    r = all_results[name]
    print(f"{name:<20} {r['CN_all'][t25_idx]:>8.4f} {r['BCPN_all'][t25_idx]:>8.4f} "
          f"{r['RMSE_S1'][t25_idx]:>10.5f} {r['RMSE_S2'][t25_idx]:>10.5f} "
          f"{r['RMSE_S3'][t25_idx]:>10.5f} {r['RMSE_total'][t25_idx]:>12.5f}")

# 全温域平均
print(f"\n=== 全温域(−10~40°C)平均 ===")
print(f"{'方法':<20} {'CN':>8} {'BCPN':>8} {'S₁ RMSE':>10} {'S₂ RMSE':>10} {'S₃ RMSE':>10} {'Total RMSE':>12} {'ΔCN':>8}")
print("-"*90)
for name in ['GA 4meas', 'GA 6meas', '2目标(无温漂)', '3目标(有温漂)']:
    r = all_results[name]
    avg = lambda k: np.mean(r[k])
    drift = max(r['CN_all']) - min(r['CN_all'])
    print(f"{name:<20} {avg('CN_all'):>8.4f} {avg('BCPN_all'):>8.4f} "
          f"{avg('RMSE_S1'):>10.5f} {avg('RMSE_S2'):>10.5f} "
          f"{avg('RMSE_S3'):>10.5f} {avg('RMSE_total'):>12.5f} {drift:>8.4f}")
