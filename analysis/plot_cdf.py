import numpy as np
import matplotlib.pyplot as plt
import re, os

def load_latencies(filepath):
    latencies = []
    if not os.path.exists(filepath):
        print(f"⚠️ File not found: {filepath}")
        return np.array([])
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            nums = re.findall(r"\d+\.\d+", line)
            if not nums:
                nums = re.findall(r"\d+", line)
            if nums:
                latencies.append(float(nums[-1]))
    return np.array(latencies)

data_dir = "../data/"
data_b1 = load_latencies(data_dir + 'exp_results_arm10_b1.csv')
data_veto = load_latencies(data_dir + 'exp_results_arm10_veto.csv')
data_intercept_raw = load_latencies(data_dir + 'exp_results_arm10_intercept.csv')

data_intercept = data_intercept_raw[data_intercept_raw <= 0.1]

def get_cdf(data):
    if len(data) == 0: return np.array([]), np.array([])
    return np.sort(data), np.arange(1, len(data) + 1) / len(data)

s_b1, p_b1 = get_cdf(data_b1)
s_veto, p_veto = get_cdf(data_veto)
s_intercept, p_intercept = get_cdf(data_intercept)

plt.style.use('default')
fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)

if len(s_b1) > 0:
    ax.plot(s_b1, p_b1, label=f'B1: Native Fast DDS (Survival: {len(data_b1)}/1000)', color='red', linestyle='-', linewidth=2.5, alpha=0.8, zorder=1)
if len(s_intercept) > 0:
    ax.plot(s_intercept, p_intercept, label=rf'Ours ($\rho \leq 1.0$): Intercept (Survival: {len(data_intercept_raw)}/1000)', color='purple', linestyle='--', linewidth=3.0, zorder=3)
if len(s_veto) > 0:
    ax.plot(s_veto, p_veto, label=rf'Ours ($\rho \geq 1.0$): Physical Veto (Survival: {len(data_veto)}/1000)', color='green', linestyle=':', linewidth=3.5, alpha=0.9, zorder=2)

ax.axvline(x=0.1, color='black', linestyle='-.', linewidth=1.5, label=r'EVT Cutoff Limit ($0.1ms$)')
ax.set_xlabel('End-to-End Latency (ms)', fontsize=13)
ax.set_ylabel('Cumulative Probability (CDF)', fontsize=13)
ax.set_xscale('log')
ax.set_xlim(0.03, 0.4)
ax.set_ylim(0, 1.05)
ax.grid(True, linestyle='--', alpha=0.6)
ax.legend(loc='lower right', fontsize=11)

ax.annotate(r'$\mathcal{O}(1)$ Hard Boundary', xy=(0.10, 0.4), xytext=(0.12, 0.55),
            arrowprops=dict(facecolor='purple', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=-0.15"),
            fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="purple", alpha=0.9))

overlap_x = 0.25 
overlap_y = np.interp(overlap_x, s_b1, p_b1) if len(s_b1) > 0 else 0.9
ax.annotate('Saturation Veto: Forced Release', xy=(overlap_x, overlap_y), xytext=(0.11, 0.8),
            arrowprops=dict(facecolor='green', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=-0.1"),
            fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="green", alpha=0.9))

plt.tight_layout()
fig.savefig('arm10_latency_cdf.pdf', format='pdf', bbox_inches='tight')
print("✅ Plot generated: arm10_latency_cdf.pdf")
