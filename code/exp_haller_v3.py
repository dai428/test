#!/usr/bin/env python3
"""
海伦模型 — NSGA-II 精优化
==========================
1. 单目标DEbaseline (CN/BCPN/温漂)
2. NSGA-II 三目标Pareto优化
3. 膝点选取 + L-BFGS-B局部精化
4. 全面评估
"""
import sys, os, json, time, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.optimization import NSGA2, find_knee_point
from scipy.optimize import differential_evolution, minimize
os.makedirs("results/exp_haller_v3", exist_ok=True)

# ===== 海伦模型 =====
TC=85.0; BETA=0.162; T0=25.0
c0,c1,c2=4.9538e2,1.6710e8,-2.1204e13

def retardance(wl,v,t):
    R0=c0+c1/wl**2+c2/wl**4
    a2=0.06539+(1.06572-0.06539)/(1+(v/1.46116)**3.36309)
    d0=360.0*R0*a2/wl
    return d0*((1-t/TC)/(1-T0/TC))**BETA

def build_A(t1,t2,v,wl,t,nm):
    def row_fn(d1,d2):
        c2t1=np.cos(np.deg2rad(2*t1)); s2t1=np.sin(np.deg2rad(2*t1))
        c2t2=np.cos(np.deg2rad(2*t2)); s2t2=np.sin(np.deg2rad(2*t2))
        cd1,sd1=np.cos(np.deg2rad(d1)),np.sin(np.deg2rad(d1))
        cd2,sd2=np.cos(np.deg2rad(d2)),np.sin(np.deg2rad(d2))
        m12=(c2t2**2+s2t2**2*cd2)*(c2t1**2+s2t1**2*cd1)+(c2t2*s2t2*(1-cd2))*(c2t1*s2t1*(1-cd1))-s2t2*sd2*s2t1*sd1
        m13=(c2t2**2+s2t2**2*cd2)*(c2t1*s2t1*(1-cd1))+(c2t2*s2t2*(1-cd2))*(s2t1**2+c2t1**2*cd1)+s2t2*sd2*c2t1*sd1
        m14=(c2t2**2+s2t2**2*cd2)*(-s2t1*sd1)+c2t2*s2t2*(1-cd2)*c2t1*sd1-s2t2*sd2*cd1
        return np.array([1.0,m12,m13,m14])
    d=[retardance(wl,vi,t) for vi in v]
    if nm==4: return np.vstack([row_fn(d[0],d[2]),row_fn(d[0],d[3]),row_fn(d[1],d[2]),row_fn(d[1],d[3])])
    return np.vstack([row_fn(d[0],d[3]),row_fn(d[0],d[4]),row_fn(d[1],d[3]),row_fn(d[1],d[4]),row_fn(d[2],d[3]),row_fn(d[2],d[4])])

def get_metrics(A):
    u,s,vh=np.linalg.svd(A,full_matrices=False)
    if min(s)<1e-12: return (9999,)*3
    cn=max(s)/min(s); n=A.shape[0]; eww=(1.0/n)*np.sum(1.0/s**2)
    Ap=np.linalg.pinv(A)
    Q=np.array([[np.sum(Ap[i,:]**2*A[:,j]) for j in range(4)] for i in range(4)])
    bcpn=sum(np.linalg.norm([Q[k,1],Q[k,2],Q[k,3]]) for k in range(4))
    return cn,eww,bcpn

# ===== 网格 =====
WL_S=np.linspace(350,700,10)    # NSGA-II内部
WL_F=np.linspace(350,700,36)    # 最终评估
T_S=np.array([-10,0,10,20,30,40])
T_F=np.array([-10,-5,0,5,10,15,20,25,30,35,40])

B4=[(-85,85),(-85,85),(1.5,10),(1.5,10),(1.5,10),(1.5,10)]
B6=[(-85,85),(-85,85),(1.5,10),(1.5,10),(1.5,10),(1.5,10),(1.5,10)]

# ===== 三目标适应度函数（NSGA-II用） =====
def fitness_multi(params):
    """返回 [f1(e4高斯), f2(BCPN), f3(温漂灵敏度)]"""
    nm=6 if len(params)==7 else 4
    t1,t2=params[0],params[1]; v=params[2:]
    build_A_fn=build_A
    cns,bcpns=[],[]
    cn_by_wl={i:[] for i in range(len(WL_S))}
    for wi,wl in enumerate(WL_S):
        for T in T_S:
            A=build_A_fn(t1,t2,v,wl,T,nm)
            cn,eww,bcpn=get_metrics(A)
            cns.append(cn); bcpns.append(bcpn)
            cn_by_wl[wi].append(cn)
    mean_cn=np.mean(cns); mean_bcpn=np.mean(bcpns)
    temp_sens=np.mean([np.std(cn_by_wl[wi],ddof=1) for wi in range(len(WL_S))])
    f1=(1/np.sqrt(3)-1/mean_cn if mean_cn>np.sqrt(3) else 0)**4 if mean_cn>np.sqrt(3) else 1e-8
    return [f1, mean_bcpn, temp_sens]

# ===== 单目标DE =====
def eval_de(params,nm,target):
    t1,t2=params[0],params[1]; v=params[2:]
    vals=[]
    for wl in WL_S:
        for T in T_S:
            A=build_A(t1,t2,v,wl,T,nm)
            u,s,vh=np.linalg.svd(A,full_matrices=False)
            if min(s)<1e-12: return 9999
            if target=='cn': vals.append(max(s)/min(s))
            elif target=='bcpn':
                Ap=np.linalg.pinv(A)
                Q=np.array([[np.sum(Ap[i,:]**2*A[:,j]) for j in range(4)] for i in range(4)])
                vals.append(sum(np.linalg.norm([Q[k,1],Q[k,2],Q[k,3]]) for k in range(4)))
    return np.mean(vals)

def eval_de_minimax(params,nm):
    """温漂minimax"""
    t1,t2=params[0],params[1]; v=params[2:]
    cn_by_T=[]
    for T in T_S:
        c_at_T=[]
        for wl in WL_S:
            A=build_A(t1,t2,v,wl,T,nm)
            u,s,vh=np.linalg.svd(A,full_matrices=False)
            c_at_T.append(max(s)/min(s) if min(s)>1e-12 else 9999)
        cn_by_T.append(np.mean(c_at_T))
    return max(cn_by_T)+0.3*np.mean(cn_by_T)

# ===== 全面评估 =====
def eval_full(params):
    nm=6 if len(params)==7 else 4
    t1,t2=params[0],params[1]; v=params[2:]
    cns,ewvs,bcpns=[],[],[]
    cn_by_wl={i:[] for i in range(len(WL_F))}
    for wi,wl in enumerate(WL_F):
        for T in T_F:
            A=build_A(t1,t2,v,wl,T,nm)
            cn,eww,bcpn=get_metrics(A)
            cns.append(cn); ewvs.append(eww); bcpns.append(bcpn)
            cn_by_wl[wi].append(cn)
    return np.mean(cns),np.mean(ewvs),np.mean(bcpns),np.mean([np.std(cn_by_wl[wi],ddof=1) for wi in range(len(WL_F))])

# ================================================================
print("="*60)
print("海伦模型 — NSGA-II精优化")
print(f"Tc={TC}°C, β={BETA}, 温度: -10~40°C")
print("="*60)

all_res={}

# 阶段1: 单目标DEbaseline
print("\n--- 阶段1: 单目标baseline ---")
for label,fn,bounds in [
    ("4meas CN最优", lambda p:eval_de(p,4,'cn'),B4),
    ("4meas BCPN最优", lambda p:eval_de(p,4,'bcpn'),B4),
    ("4meas 温漂(minimax)", lambda p:eval_de_minimax(p,4),B4),
    ("6meas CN最优", lambda p:eval_de(p,6,'cn'),B6),
    ("6meas BCPN最优", lambda p:eval_de(p,6,'bcpn'),B6),
    ("6meas 温漂(minimax)", lambda p:eval_de_minimax(p,6),B6),
]:
    t0=time.time()
    res=differential_evolution(fn,bounds,strategy='best1bin',popsize=25,maxiter=100,seed=42,polish=True)
    c,e,b,t=eval_full(res.x)
    all_res[label]={'CN':c,'EWV':e,'BCPN':b,'温漂':t}
    print(f"  {label:<22}: CN={c:.4f}, BCPN={b:.4f}, 温漂={t:.4f} ({time.time()-t0:.0f}s)")

# 阶段2: NSGA-II 多目标优化
print("\n--- 阶段2: NSGA-II (6次测量) ---")
nsga2=NSGA2(n_obj=3,bounds=B6,pop_size=100,n_generations=200)
nsga_result=nsga2.optimize(fitness_multi,verbose=True,save_path="results/exp_haller_v3/nsga2.npz")
np.savez("results/exp_haller_v3/nsga2.npz",**{k:v for k,v in nsga_result.items() if k!='history'})

# 过滤BCPN异常并找膝点
pf_pop=nsga_result['pareto_front']
pf_fit=nsga_result['pareto_fitnesses']
mask=pf_fit[:,1]<10
pf_pop_f=pf_pop[mask]; pf_fit_f=pf_fit[mask]
print(f"Pareto点: {len(pf_fit)} → 过滤后: {len(pf_fit_f)}")

knee_fit,knee_idx=find_knee_point(pf_fit_f)
knee_params=pf_pop_f[knee_idx]
print(f"膝点: f1={knee_fit[0]:.6f}, f2={knee_fit[1]:.4f}, f3={knee_fit[2]:.4f}")
c,e,b,t=eval_full(knee_params)
all_res['6meas NSGA-II膝点(粗)']={'CN':c,'EWV':e,'BCPN':b,'温漂':t}
print(f"  粗评估: CN={c:.4f}, BCPN={b:.4f}, 温漂={t:.4f}")

# 阶段3: L-BFGS-B精化
print("\n--- 阶段3: L-BFGS-B精化 ---")
def refine_fitness(params):
    nm=6 if len(params)==7 else 4
    t1,t2=params[0],params[1]; v=params[2:]
    cns,bcpns=[],[]
    cn_by_wl={i:[] for i in range(len(WL_S))}
    for wi,wl in enumerate(WL_S):
        for T in T_S:
            A=build_A(t1,t2,v,wl,T,nm)
            cn,eww,bcpn=get_metrics(A)
            cns.append(cn); bcpns.append(bcpn)
            cn_by_wl[wi].append(cn)
    mean_cn=np.mean(cns); mean_bcpn=np.mean(bcpns)
    temp_sens=np.mean([np.std(cn_by_wl[wi],ddof=1) for wi in range(len(WL_S))])
    return mean_cn+0.5*mean_bcpn+10*temp_sens

res_ref=minimize(refine_fitness,knee_params,method='L-BFGS-B',
                 bounds=B6,options={'maxiter':500,'ftol':1e-12})
print(f"  精化前: {refine_fitness(knee_params):.6f} → 精化后: {res_ref.fun:.6f}")
c,e,b,t=eval_full(res_ref.x)
all_res['6meas NSGA-II膝点(精化)★']={'CN':c,'EWV':e,'BCPN':b,'温漂':t}
print(f"  精化评估: CN={c:.4f}, BCPN={b:.4f}, 温漂={t:.4f}")
print(f"  参数: θ1={res_ref.x[0]:.2f}°, θ2={res_ref.x[1]:.2f}°")
nv=res_ref.x[2:]
if len(nv)==5: print(f"        V1=[{nv[0]:.3f},{nv[1]:.3f},{nv[2]:.3f}]V, V2=[{nv[3]:.3f},{nv[4]:.3f}]V")

# 温漂扫描（精化膝点）
print("\n--- 温漂扫描 (精化膝点) ---")
p=res_ref.x; nm=6
t1,t2=p[0],p[1]; v=p[2:]
for T in T_F:
    c_at_T=[]
    for wl in WL_F:
        A=build_A(t1,t2,v,wl,T,6)
        cn,_,_=get_metrics(A)
        c_at_T.append(cn)
    print(f"  T={T:3.0f}°C: mean_CN={np.mean(c_at_T):.4f}")

# 输出
print("\n"+"="*70)
print(f"{'配置':<28} {'CN':<10} {'BCPN':<10} {'温漂':<10}")
print("="*70)
for k,v in sorted(all_res.items()):
    print(f"{k:<28} {v['CN']:<10.4f} {v['BCPN']:<10.4f} {v['温漂']:<10.6f}")
print("="*70)

with open("results/exp_haller_v3/results.json","w") as f:
    json.dump(all_res,f,indent=2)
print(f"\n✅ 保存: results/exp_haller_v3/")
