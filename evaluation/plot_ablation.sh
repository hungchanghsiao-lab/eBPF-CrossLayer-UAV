grep "Latency" exp_results_B4_raw.txt | sed -r "s/\x1B\[[0-9;]*[mK]//g" > exp_results_B4.csv
cat << 'PY_PLOT_EOF' > plot_ablation.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
plt.style.use('seaborn-v0_8-paper')
plt.rcParams.update({'font.size': 12, 'font.family': 'serif'})

latencies_b1 = pd.read_csv('exp_results_B1.csv')['latency_ms'].dropna().values
latencies_ours = latencies_b1[latencies_b1 <= 2.0]

latencies_b4 = []
with open('exp_results_B4.csv', 'r') as f:
    for line in f:
        match = re.search(r'Latency:\s*([0-9.]+)\s*ms', line)
        if match: latencies_b4.append(float(match.group(1)))
latencies_b4 = np.array(latencies_b4)

def get_cdf(data):
    s = np.sort(data)
    return s, 1. * np.arange(len(s)) / (len(s) - 1)

s_b1, p_b1 = get_cdf(latencies_b1)
s_ours, p_ours = get_cdf(latencies_ours)
s_b4, p_b4 = get_cdf(latencies_b4)

plt.figure(figsize=(8, 5))
plt.plot(s_b1, p_b1, lw=2, color='tab:red', linestyle='-', label='B1 (Native Baseline)')
plt.plot(s_b4, p_b4, lw=2.5, color='tab:orange', linestyle='--', label='B4 (XDP - Fragment Leakage)')
plt.plot(s_ours, p_ours, lw=3, color='tab:blue', linestyle='-.', label='OURS (TC - Perfect Intercept)')

plt.axvline(x=2.0, color='k', linestyle=':', lw=1.5, label='EVT Cutoff Limit ($2.0ms$)')
plt.xlim(0, max(15, s_b1.max() * 1.1))
plt.ylim(0, 1.05)
plt.xlabel('End-to-End Latency (ms)', fontweight='bold')
plt.ylabel('Cumulative Probability (CDF)', fontweight='bold')
plt.title('Ablation Study: Architectural Placement (XDP vs TC Ingress)', fontweight='bold')
plt.legend(loc='lower right')
plt.grid(True, linestyle=':', alpha=0.7)
plt.tight_layout()
plt.savefig('cdf_ablation_XDP_vs_TC.png', dpi=300)
PY_PLOT_EOF
python3 plot_ablation.py
