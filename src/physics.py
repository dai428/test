"""
LCVR Stokes偏振测量系统 — 物理模型模块
=======================================
包含：LCVR相位延迟模型、测量矩阵构建（4次/6次）
"""

import numpy as np
from typing import Tuple, Optional

# ===============================================================
# 物理常数
# ===============================================================
LCVR_PARAMS = {
    "R0_coeff": [4.9538e2, 1.6710e8, -2.1204e13],  # R0(λ) = c0 + c1/λ² + c2/λ⁴
    "A1": 1.06572,
    "A2": 0.06539,
    "X0": 1.46116,    # 阈值电压 (V)
    "P": 3.36309,     # 陡度参数
    "alpha": -0.0027, # 温漂系数 (/°C)
    "T0": 25.0,       # 标定温度 (°C)
}

WAVELENGTH_RANGE = (350, 700)  # nm
VOLTAGE_RANGE = (1.5, 10.0)    # V
TEMP_RANGE = (20.0, 50.0)      # °C
ANGLE_RANGE = (-90.0, 90.0)    # deg


def retardance(wavelength_nm: float, voltage_V: float, temp_C: float = 25.0) -> float:
    """
    计算 LCVR 相位延迟量（单位：度）

    Parameters
    ----------
    wavelength_nm : float
        波长 (nm)，范围 350-700
    voltage_V : float
        驱动电压 (V)，范围 1.5-10
    temp_C : float
        温度 (°C)，范围 20-50

    Returns
    -------
    float : 延迟量（度）
    """
    # 室温光程差
    c0, c1, c2 = LCVR_PARAMS["R0_coeff"]
    R0 = c0 + c1 / wavelength_nm**2 + c2 / wavelength_nm**4

    # 电压响应曲线（Sigmoid类型）
    x2 = LCVR_PARAMS["A2"] + (LCVR_PARAMS["A1"] - LCVR_PARAMS["A2"]) / \
         (1 + (voltage_V / LCVR_PARAMS["X0"]) ** LCVR_PARAMS["P"])
    R = R0 * x2  # 光程差 (nm)

    # 延迟量（度）
    delta0 = 360.0 * R / wavelength_nm

    # 温漂修正（线性模型）
    alpha = LCVR_PARAMS["alpha"]
    T0 = LCVR_PARAMS["T0"]
    delta = delta0 * (1 + alpha * (temp_C - T0))
    return delta


def retardance_nonlinear(wavelength_nm: float, voltage_V: float, temp_C: float = 25.0,
                         Tc: float = 85.0, beta: float = 0.162) -> float:
    """
    基于完整Haller非线性模型的LCVR相位延迟量（度）

    使用Δn(T) = Δn₀ · (1 - T/Tc)^β 的非线性温漂模型，
    而非线性近似 δ(T) = δ(T₀) · (1 + α(T-T₀))。

    Parameters
    ----------
    wavelength_nm : float
        波长 (nm)，范围 350-700
    voltage_V : float
        驱动电压 (V)，范围 1.5-10
    temp_C : float
        温度 (°C)，范围 -10~40
    Tc : float
        Haller清亮点温度 (°C)，默认85°C
    beta : float
        Haller指数，默认0.162

    Returns
    -------
    float : 延迟量（度）
    """
    T0 = LCVR_PARAMS["T0"]  # 标定温度 25°C

    # 先计算标定温度下的延迟量
    delta_T0 = retardance(wavelength_nm, voltage_V, T0)

    # Haller非线性温漂比例因子
    # Δn(T) / Δn(T₀) = (1 - T/Tc)^β / (1 - T₀/Tc)^β
    # 使用开尔文温度
    Tc_K = Tc + 273.15
    T_K = temp_C + 273.15
    T0_K = T0 + 273.15

    ratio = ((1 - T_K / Tc_K) / (1 - T0_K / Tc_K)) ** beta
    delta = delta_T0 * ratio
    return delta


def build_matrix_4meas(theta1_deg: float, theta2_deg: float,
                       d11: float, d12: float,
                       d21: float, d22: float) -> np.ndarray:
    """
    构建 4×4 测量矩阵（4次测量，2×2状态）

    Parameters
    ----------
    theta1_deg, theta2_deg : LCVR1, LCVR2 快轴角度 (deg)
    d11, d12 : LCVR1 在两个电压下的延迟量 (deg)
    d21, d22 : LCVR2 在两个电压下的延迟量 (deg)

    Returns
    -------
    np.ndarray : 4×4 测量矩阵 A
    """
    c2t1 = np.cos(np.deg2rad(2 * theta1_deg))
    s2t1 = np.sin(np.deg2rad(2 * theta1_deg))
    c2t2 = np.cos(np.deg2rad(2 * theta2_deg))
    s2t2 = np.sin(np.deg2rad(2 * theta2_deg))

    cd11, sd11 = np.cos(np.deg2rad(d11)), np.sin(np.deg2rad(d11))
    cd12, sd12 = np.cos(np.deg2rad(d12)), np.sin(np.deg2rad(d12))
    cd21, sd21 = np.cos(np.deg2rad(d21)), np.sin(np.deg2rad(d21))
    cd22, sd22 = np.cos(np.deg2rad(d22)), np.sin(np.deg2rad(d22))

    A = np.zeros((4, 4))
    A[:, 0] = 1.0

    def fill_row(r, c2t, s2t, cd, sd):
        """填充矩阵一行的 m12, m13, m14"""
        m12 = (c2t2**2 + s2t2**2 * cd21) * (c2t1**2 + s2t1**2 * cd11 if r == 0 else ...)
        # 用实际的行号对应
        ...

    # 行1: (d11, d21)
    A[0, 1] = (c2t2**2 + s2t2**2 * cd21) * (c2t1**2 + s2t1**2 * cd11) + \
              (c2t2 * s2t2 * (1 - cd21)) * (c2t1 * s2t1 * (1 - cd11)) - s2t2 * sd21 * s2t1 * sd11
    A[0, 2] = (c2t2**2 + s2t2**2 * cd21) * (c2t1 * s2t1 * (1 - cd11)) + \
              (c2t2 * s2t2 * (1 - cd21)) * (s2t1**2 + c2t1**2 * cd11) + s2t2 * sd21 * c2t1 * sd11
    A[0, 3] = (c2t2**2 + s2t2**2 * cd21) * (-s2t1 * sd11) + \
              c2t2 * s2t2 * (1 - cd21) * c2t1 * sd11 - s2t2 * sd21 * cd11
    # 行2: (d11, d22)
    A[1, 1] = (c2t2**2 + s2t2**2 * cd22) * (c2t1**2 + s2t1**2 * cd11) + \
              (c2t2 * s2t2 * (1 - cd22)) * (c2t1 * s2t1 * (1 - cd11)) - s2t2 * sd22 * s2t1 * sd11
    A[1, 2] = (c2t2**2 + s2t2**2 * cd22) * (c2t1 * s2t1 * (1 - cd11)) + \
              (c2t2 * s2t2 * (1 - cd22)) * (s2t1**2 + c2t1**2 * cd11) + s2t2 * sd22 * c2t1 * sd11
    A[1, 3] = (c2t2**2 + s2t2**2 * cd22) * (-s2t1 * sd11) + \
              c2t2 * s2t2 * (1 - cd22) * c2t1 * sd11 - s2t2 * sd22 * cd11
    # 行3: (d12, d21)
    A[2, 1] = (c2t2**2 + s2t2**2 * cd21) * (c2t1**2 + s2t1**2 * cd12) + \
              (c2t2 * s2t2 * (1 - cd21)) * (c2t1 * s2t1 * (1 - cd12)) - s2t2 * sd21 * s2t1 * sd12
    A[2, 2] = (c2t2**2 + s2t2**2 * cd21) * (c2t1 * s2t1 * (1 - cd12)) + \
              (c2t2 * s2t2 * (1 - cd21)) * (s2t1**2 + c2t1**2 * cd12) + s2t2 * sd21 * c2t1 * sd12
    A[2, 3] = (c2t2**2 + s2t2**2 * cd21) * (-s2t1 * sd12) + \
              c2t2 * s2t2 * (1 - cd21) * c2t1 * sd12 - s2t2 * sd21 * cd12
    # 行4: (d12, d22)
    A[3, 1] = (c2t2**2 + s2t2**2 * cd22) * (c2t1**2 + s2t1**2 * cd12) + \
              (c2t2 * s2t2 * (1 - cd22)) * (c2t1 * s2t1 * (1 - cd12)) - s2t2 * sd22 * s2t1 * sd12
    A[3, 2] = (c2t2**2 + s2t2**2 * cd22) * (c2t1 * s2t1 * (1 - cd12)) + \
              (c2t2 * s2t2 * (1 - cd22)) * (s2t1**2 + c2t1**2 * cd12) + s2t2 * sd22 * c2t1 * sd12
    A[3, 3] = (c2t2**2 + s2t2**2 * cd22) * (-s2t1 * sd12) + \
              c2t2 * s2t2 * (1 - cd22) * c2t1 * sd12 - s2t2 * sd22 * cd12
    return A


def build_matrix_6meas(theta1_deg: float, theta2_deg: float,
                       d11: float, d12: float, d13: float,
                       d21: float, d22: float) -> np.ndarray:
    """
    构建 6×4 测量矩阵（6次测量，2×3状态）

    行顺序: (v11,v21), (v11,v22), (v12,v21), (v12,v22), (v13,v21), (v13,v22)
    """
    c2t1 = np.cos(np.deg2rad(2 * theta1_deg))
    s2t1 = np.sin(np.deg2rad(2 * theta1_deg))
    c2t2 = np.cos(np.deg2rad(2 * theta2_deg))
    s2t2 = np.sin(np.deg2rad(2 * theta2_deg))

    def _row(d1_deg, d2_deg):
        cd1 = np.cos(np.deg2rad(d1_deg))
        sd1 = np.sin(np.deg2rad(d1_deg))
        cd2 = np.cos(np.deg2rad(d2_deg))
        sd2 = np.sin(np.deg2rad(d2_deg))

        m12 = (c2t2**2 + s2t2**2 * cd2) * (c2t1**2 + s2t1**2 * cd1) + \
              (c2t2 * s2t2 * (1 - cd2)) * (c2t1 * s2t1 * (1 - cd1)) - s2t2 * sd2 * s2t1 * sd1
        m13 = (c2t2**2 + s2t2**2 * cd2) * (c2t1 * s2t1 * (1 - cd1)) + \
              (c2t2 * s2t2 * (1 - cd2)) * (s2t1**2 + c2t1**2 * cd1) + s2t2 * sd2 * c2t1 * sd1
        m14 = (c2t2**2 + s2t2**2 * cd2) * (-s2t1 * sd1) + \
              c2t2 * s2t2 * (1 - cd2) * c2t1 * sd1 - s2t2 * sd2 * cd1
        return np.array([1.0, m12, m13, m14])

    rows = [
        _row(d11, d21), _row(d11, d22),
        _row(d12, d21), _row(d12, d22),
        _row(d13, d21), _row(d13, d22),
    ]
    return np.vstack(rows)


def params_to_retardances_4meas(params, wavelength_nm, temp_C=25.0):
    """
    将4-meas参数向量转换为4个延迟量
    
    params = [theta1, theta2, v11, v12, v21, v22]
    """
    theta1, theta2, v11, v12, v21, v22 = params
    d11 = retardance(wavelength_nm, v11, temp_C)
    d12 = retardance(wavelength_nm, v12, temp_C)
    d21 = retardance(wavelength_nm, v21, temp_C)
    d22 = retardance(wavelength_nm, v22, temp_C)
    return theta1, theta2, d11, d12, d21, d22


def params_to_retardances_6meas(params, wavelength_nm, temp_C=25.0):
    """
    将6-meas参数向量转换为6个延迟量
    
    params = [theta1, theta2, v11, v12, v13, v21, v22]
    """
    theta1, theta2, v11, v12, v13, v21, v22 = params
    d11 = retardance(wavelength_nm, v11, temp_C)
    d12 = retardance(wavelength_nm, v12, temp_C)
    d13 = retardance(wavelength_nm, v13, temp_C)
    d21 = retardance(wavelength_nm, v21, temp_C)
    d22 = retardance(wavelength_nm, v22, temp_C)
    return theta1, theta2, d11, d12, d13, d21, d22
