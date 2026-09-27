import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
plt.style.use('seaborn-v0_8-paper')
plt.rcParams.update({'font.size': 12, 'font.family': 'serif'})

latencies_b1 = pd.read_csv('exp_results_B1.csv')['latency_ms'].dropna().values
latencies_ours = latencies_b1[latencies_b1 <= 2.0]

latencies_rho = []
with open('exp_results_rho120.csv', 'r') as f:
    for line in f:
        match = re.search(r'Latency:\s*([0-9.]+)\s*ms', line)
        if match: latencies_rho.append(float(match.group(1)))
latencies_rho = np.array(latencies_rho)

def get_cdf(data):
    s = np.sort(data)
    return s, 1. * np.arange(len(s)) / (len(s) - 1)

s_b1, p_b1 = get_cdf(latencies_b1)
s_ours, p_ours = get_cdf(latencies_ours)
s_rho, p_rho = get_cdf(latencies_rho)

plt.figure(figsize=(8, 5))
plt.plot(s_b1, p_b1, lw=2.5, color='tab:red', linestyle='-', label='B1 (Native Baseline)', alpha=0.8)
plt.plot(s_ours, p_ours, lw=2.5, color='tab:blue', linestyle='-.', label='OURS ($\\rho \leq 1.0$ - Perfect Intercept)')
plt.plot(s_rho, p_rho, lw=3, color='tab:green', linestyle=':', label='OURS ($\\rho = 1.2$ - Physical Veto)')

plt.axvline(x=2.0, color='k', linestyle='--', lw=1.5, label='EVT Cutoff Limit ($2.0ms$)')
plt.xlim(0, max(15, s_b1.max() * 1.1))
plt.ylim(0, 1.05)
plt.xlabel('End-to-End Latency (ms)', fontweight='bold')
plt.ylabel('Cumulative Probability (CDF)', fontweight='bold')
plt.title('Ablation Study: Collision Saturation & Physical Veto', fontweight='bold')
plt.legend(loc='lower right')
plt.grid(True, linestyle=':', alpha=0.7)
plt.tight_layout()
plt.savefig('cdf_ablation_rho_veto.png', dpi=300)
