#!/usr/bin/env python3
"""
LCVR Stokes 偏振计优化实验 — 一键运行
======================================
1. 优化  →  2. 评估  →  3. 出图
"""

import sys
import time

def step(msg):
    print(f"\n{'='*60}")
    print(f"  [{time.strftime('%H:%M:%S')}] {msg}")
    print(f"{'='*60}")

if __name__ == '__main__':
    step("Step 1/3: 参数优化（8次差分进化，预计10-30分钟）")
    import optimize
    all_results = optimize.run_all_optimizations()

    step("Step 2/3: 统一对比评估")
    import evaluate
    all_metrics = evaluate.run_evaluation()

    step("Step 3/3: 生成论文级图表")
    import figures
    figures.generate_all_figures()

    step("全部完成!")
    print(f"  结果: {optimize.RESULTS_DIR}")
    print(f"  图表: {figures.FIGURES_DIR}")
