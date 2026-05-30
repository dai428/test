"""
LCVR Stokes Polarimeter — 物理模型
====================================
包含：
- LCVR 相位延迟模型（Haller 温漂模型）
- 4次/6次测量矩阵构建
- 条件数（高斯噪声指标）
- BCPN 分量（泊松噪声指标）
"""

import numpy as np
from scipy.linalg import pinv
from numpy.linalg import cond
from dataclasses import dataclass
from typing import Tuple


# ============================================================
# 1. LCVR 相位延迟模型
# ============================================================

def retardance_25c(lamda: float, v: float) -> float:
    """
    25°C 下的 LCVR 相位延迟量（度）
    lamda : 波长 (nm), 有效范围 350-700 nm
    v     : 电压 (V)
    """
    # 光程差经验公式
    R0 = 4.9538e2 + 1.6710e8 / lamda**2 - 2.1204e13 / lamda**4
    # Haller 模型阶参量
    A1, A2, X0, P = 1.06572, 0.06539, 1.46116, 3.36309
    x2 = A2 + (A1 - A2) / (1 + (v / X0)**P)
    R = R0 * x2
    return 360.0 * R / lamda


def retardance(lamda: float, v: float, T: float) -> float:
    """
    LCVR 相位延迟量（度），使用 Haller 温漂模型
    lamda : 波长 (nm)
    v     : 电压 (V)
    T     : 温度 (°C)
    
    Haller 模型: Δn(T) ∝ (1 - T/Tc)^β
    参考: Tiwary et al. 2017
    """
    delta_ref = retardance_25c(lamda, v)
    
    # Haller 温漂参数
    Tc = 66.9 + 273.15       # 清亮点温度 (K)
    beta = 0.213              # 临界指数
    T_ref = 25.0 + 273.15     # 参考温度 (K)
    T_abs = T + 273.15        # 当前温度 (K)
    
    factor = (1 - T_abs / Tc) / (1 - T_ref / Tc)
    if factor <= 0:
        raise ValueError(f"温度 {T}°C 超过清亮点 {Tc-273.15:.1f}°C")
    
    return delta_ref * (factor ** beta)


# ============================================================
# 2. 测量矩阵构建
# ============================================================

def buildA_4meas(theta1: float, theta2: float,
                 d11: float, d12: float, d21: float, d22: float) -> np.ndarray:
    """
    4次测量矩阵 (4×4)
    theta1, theta2 : LCVR1, LCVR2 快轴方位角 (度)
    d11, d12       : LCVR1 两种相位延迟量 (度)
    d21, d22       : LCVR2 两种相位延迟量 (度)
    """
    c2t1, s2t1 = np.cos(np.deg2rad(2*theta1)), np.sin(np.deg2rad(2*theta1))
    c2t2, s2t2 = np.cos(np.deg2rad(2*theta2)), np.sin(np.deg2rad(2*theta2))
    
    cd = [np.cos(np.deg2rad(d)) for d in [d11, d12, d21, d22]]
    sd = [np.sin(np.deg2rad(d)) for d in [d11, d12, d21, d22]]
    cd11, cd12, cd21, cd22 = cd
    sd11, sd12, sd21, sd22 = sd
    
    A = np.zeros((4, 4))
    A[:, 0] = 1.0
    
    # 行1: (d11, d21)
    A[0, 1] = (c2t2**2 + s2t2**2*cd21)*(c2t1**2 + s2t1**2*cd11) + \
              (c2t2*s2t2*(1-cd21))*(c2t1*s2t1*(1-cd11)) - s2t2*sd21*s2t1*sd11
    A[0, 2] = (c2t2**2 + s2t2**2*cd21)*(c2t1*s2t1*(1-cd11)) + \
              (c2t2*s2t2*(1-cd21))*(s2t1**2 + c2t1**2*cd11) + s2t2*sd21*c2t1*sd11
    A[0, 3] = (c2t2**2 + s2t2**2*cd21)*(-s2t1*sd11) + \
              c2t2*s2t2*(1-cd21)*c2t1*sd11 - s2t2*sd21*cd11
    
    # 行2: (d11, d22)
    A[1, 1] = (c2t2**2 + s2t2**2*cd22)*(c2t1**2 + s2t1**2*cd11) + \
              (c2t2*s2t2*(1-cd22))*(c2t1*s2t1*(1-cd11)) - s2t2*sd22*s2t1*sd11
    A[1, 2] = (c2t2**2 + s2t2**2*cd22)*(c2t1*s2t1*(1-cd11)) + \
              (c2t2*s2t2*(1-cd22))*(s2t1**2 + c2t1**2*cd11) + s2t2*sd22*c2t1*sd11
    A[1, 3] = (c2t2**2 + s2t2**2*cd22)*(-s2t1*sd11) + \
              c2t2*s2t2*(1-cd22)*c2t1*sd11 - s2t2*sd22*cd11
    
    # 行3: (d12, d21)
    A[2, 1] = (c2t2**2 + s2t2**2*cd21)*(c2t1**2 + s2t1**2*cd12) + \
              (c2t2*s2t2*(1-cd21))*(c2t1*s2t1*(1-cd12)) - s2t2*sd21*s2t1*sd12
    A[2, 2] = (c2t2**2 + s2t2**2*cd21)*(c2t1*s2t1*(1-cd12)) + \
              (c2t2*s2t2*(1-cd21))*(s2t1**2 + c2t1**2*cd12) + s2t2*sd21*c2t1*sd12
    A[2, 3] = (c2t2**2 + s2t2**2*cd21)*(-s2t1*sd12) + \
              c2t2*s2t2*(1-cd21)*c2t1*sd12 - s2t2*sd21*cd12
    
    # 行4: (d12, d22)
    A[3, 1] = (c2t2**2 + s2t2**2*cd22)*(c2t1**2 + s2t1**2*cd12) + \
              (c2t2*s2t2*(1-cd22))*(c2t1*s2t1*(1-cd12)) - s2t2*sd22*s2t1*sd12
    A[3, 2] = (c2t2**2 + s2t2**2*cd22)*(c2t1*s2t1*(1-cd12)) + \
              (c2t2*s2t2*(1-cd22))*(s2t1**2 + c2t1**2*cd12) + s2t2*sd22*c2t1*sd12
    A[3, 3] = (c2t2**2 + s2t2**2*cd22)*(-s2t1*sd12) + \
              c2t2*s2t2*(1-cd22)*c2t1*sd12 - s2t2*sd22*cd12
    
    return A


def buildA_6meas(theta1: float, theta2: float,
                 d11: float, d12: float, d13: float,
                 d21: float, d22: float) -> np.ndarray:
    """
    6次测量矩阵 (6×4)，LCVR1 用3个状态，LCVR2 用2个状态
    行顺序: (d11,d21), (d11,d22), (d12,d21), (d12,d22), (d13,d21), (d13,d22)
    """
    c2t1, s2t1 = np.cos(np.deg2rad(2*theta1)), np.sin(np.deg2rad(2*theta1))
    c2t2, s2t2 = np.cos(np.deg2rad(2*theta2)), np.sin(np.deg2rad(2*theta2))
    
    def _row(d1, d2):
        cd1, sd1 = np.cos(np.deg2rad(d1)), np.sin(np.deg2rad(d1))
        cd2, sd2 = np.cos(np.deg2rad(d2)), np.sin(np.deg2rad(d2))
        m12 = (c2t2**2 + s2t2**2*cd2)*(c2t1**2 + s2t1**2*cd1) + \
              (c2t2*s2t2*(1-cd2))*(c2t1*s2t1*(1-cd1)) - s2t2*sd2*s2t1*sd1
        m13 = (c2t2**2 + s2t2**2*cd2)*(c2t1*s2t1*(1-cd1)) + \
              (c2t2*s2t2*(1-cd2))*(s2t1**2 + c2t1**2*cd1) + s2t2*sd2*c2t1*sd1
        m14 = (c2t2**2 + s2t2**2*cd2)*(-s2t1*sd1) + \
              c2t2*s2t2*(1-cd2)*c2t1*sd1 - s2t2*sd2*cd1
        return np.array([1.0, m12, m13, m14])
    
    rows = [
        _row(d11, d21), _row(d11, d22),
        _row(d12, d21), _row(d12, d22),
        _row(d13, d21), _row(d13, d22),
    ]
    return np.vstack(rows)


def get_A_4meas(params: np.ndarray, lamda: float, T: float) -> np.ndarray:
    """
    给定参数计算 4次测量矩阵
    params = [theta1, theta2, v11, v12, v21, v22]
    """
    theta1, theta2, v11, v12, v21, v22 = params
    d11 = retardance(lamda, v11, T)
    d12 = retardance(lamda, v12, T)
    d21 = retardance(lamda, v21, T)
    d22 = retardance(lamda, v22, T)
    return buildA_4meas(theta1, theta2, d11, d12, d21, d22)


def get_A_6meas(params: np.ndarray, lamda: float, T: float) -> np.ndarray:
    """
    给定参数计算 6次测量矩阵
    params = [theta1, theta2, v11, v12, v13, v21, v22]
    """
    theta1, theta2, v11, v12, v13, v21, v22 = params
    d11 = retardance(lamda, v11, T)
    d12 = retardance(lamda, v12, T)
    d13 = retardance(lamda, v13, T)
    d21 = retardance(lamda, v21, T)
    d22 = retardance(lamda, v22, T)
    return buildA_6meas(theta1, theta2, d11, d12, d13, d21, d22)


# ============================================================
# 3. 性能指标
# ============================================================

def safe_cond(A: np.ndarray) -> float:
    """安全的条件数计算"""
    try:
        c = cond(A, 2)
        if np.isnan(c) or np.isinf(c) or c > 1e6:
            return 1e6
        return float(c)
    except Exception:
        return 1e6


def compute_bcpn(A: np.ndarray) -> Tuple[float, float, float, float]:
    """
    计算 BCPN 分量 (泊松噪声指标)
    返回 (q0, q1, q2, q3)
    向量化实现加速
    """
    B = pinv(A)                     # 4×m
    
    # 向量化 Q = B² @ A
    # B[i,:]² * A[:,j] → (B²) @ A
    B_sq = B ** 2                   # 4×m
    Q = B_sq @ A                    # 4×4
    
    q0 = float(np.linalg.norm(Q[0, 1:4]))
    q1 = float(np.linalg.norm(Q[1, 1:4]))
    q2 = float(np.linalg.norm(Q[2, 1:4]))
    q3 = float(np.linalg.norm(Q[3, 1:4]))
    return q0, q1, q2, q3


# ============================================================
# 4. 适应度函数
# ============================================================

IDEAL_CN = np.sqrt(3)

def gauss_loss(cn: float) -> float:
    """高斯噪声损失: (1/√3 - 1/CN)^4"""
    return (1.0 / IDEAL_CN - 1.0 / cn) ** 4


def poisson_loss(q0: float, q1: float, q2: float, q3: float) -> float:
    """泊松噪声损失: BCPN 分量四次方和"""
    return q0**4 + q1**4 + q2**4 + q3**4


# ============================================================
# 5. 参数边界
# ============================================================

BOUNDS_4MEAS = [(-90, 90), (-90, 90),  # theta1, theta2
                (1.5, 10), (1.5, 10),  # v11, v12
                (1.5, 10), (1.5, 10)]  # v21, v22

BOUNDS_6MEAS = [(-90, 90), (-90, 90),  # theta1, theta2
                (1.5, 10), (1.5, 10), (1.5, 10),  # v11, v12, v13
                (1.5, 10), (1.5, 10)]  # v21, v22
