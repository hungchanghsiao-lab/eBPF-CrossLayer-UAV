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
data_b2 = load_latencies(data_dir + 'exp_results_arm10_b2.csv')
data_b3 = load_latencies(data_dir + 'exp_results_arm10_b3.csv')
data_b4 = load_latencies(data_dir + 'exp_results_arm10_b4.csv')
data_intercept = load_latencies(data_dir + 'exp_results_arm10_intercept.csv')
data_veto = load_latencies(data_dir + 'exp_results_arm10_veto.csv')

# Calibration for base hardware virtualization latency (0.25 ms)
hardware_delay_offset = 0.25

def remove_offset(data):
    if len(data) == 0:
        return data
    adjusted = data - hardware_delay_offset
    return np.clip(adjusted, 0.01, None)

data_b1 = remove_offset(data_b1)
data_b2 = remove_offset(data_b2)
data_b3 = remove_offset(data_b3)
data_b4 = remove_offset(data_b4)
data_intercept = remove_offset(data_intercept)
data_veto = remove_offset(data_veto)

# Apply jitter smoothing to reconstruct continuous CDF from discrete %.2f logs
np.random.seed(42)
def apply_jitter_smoothing(data):
    if len(data) == 0:
        return data
    jitter = np.random.uniform(-0.005, 0.005, size=len(data))
    return np.clip(data + jitter, 0.01, None)

data_b1 = apply_jitter_smoothing(data_b1)
data_b2 = apply_jitter_smoothing(data_b2)
data_b3 = apply_jitter_smoothing(data_b3)
data_b4 = apply_jitter_smoothing(data_b4)
data_intercept = apply_jitter_smoothing(data_intercept)
data_veto = apply_jitter_smoothing(data_veto)

def get_cdf(data):
    if len(data) == 0:
        return np.array([]), np.array([])
    return np.sort(data), np.arange(1, len(data) + 1) / len(data)

s_b1, p_b1 = get_cdf(data_b1)
s_b2, p_b2 = get_cdf(data_b2)
s_b3, p_b3 = get_cdf(data_b3)
s_b4, p_b4 = get_cdf(data_b4)
s_intercept, p_intercept = get_cdf(data_intercept)
s_veto, p_veto = get_cdf(data_veto)

plt.style.use('default')
fig, ax = plt.subplots(figsize=(10, 6.5), dpi=150)

# Legend Configuration
ax.plot(s_b1, p_b1, label='B1: Native Fast DDS', color='blue', linestyle='-', linewidth=2.0, alpha=0.6, zorder=2)
ax.plot(s_b2, p_b2, label='B2: App-layer QoS', color='orange', linestyle=':', linewidth=2.5, alpha=0.8, zorder=2)
ax.plot(s_b3, p_b3, label='B3: S.A. AQM', color='cyan', linestyle='-.', linewidth=2.0, alpha=0.7, zorder=2)
ax.plot(s_b4, p_b4, label='B4: AF_XDP', color='gray', linestyle=(0, (3, 5, 1, 5)), linewidth=2.0, alpha=0.7, zorder=2)

ax.plot(s_intercept, p_intercept, label=r'Ours ($\rho \leq 1.0$): Intercept', color='purple', linestyle='--', linewidth=3.5, zorder=4)
ax.plot(s_veto, p_veto, label=r'Ours ($\rho \geq 1.0$): Physical Veto', color='red', linestyle='-', linewidth=3.0, alpha=0.9, zorder=3)

ax.axvline(x=0.1, color='black', linestyle='-.', linewidth=1.5, label=r'EVT Cutoff Limit ($0.1ms$)')

ax.set_xlabel('End-to-End Latency (ms)', fontsize=14)
ax.set_ylabel('Cumulative Probability (CDF)', fontsize=14)
ax.set_xscale('log')
ax.set_xlim(0.01, 2.5)
ax.set_ylim(0, 1.05)
ax.grid(True, linestyle='--', alpha=0.6)
ax.legend(loc='lower right', fontsize=11, framealpha=0.9)

# Annotations positioning
target_y_intercept = 0.8
target_x_intercept = np.interp(target_y_intercept, p_intercept, s_intercept) if len(s_intercept) > 0 else 0.08
ax.annotate(r'$\mathcal{O}(1)$ Hard Boundary',
            xy=(target_x_intercept, target_y_intercept),
            xytext=(0.012, 0.9),
            ha='left',
            arrowprops=dict(facecolor='purple', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=0.1"),
            fontsize=13, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="purple", alpha=0.9), zorder=5)

target_y_veto = 1.0
target_x_veto = 1.0
ax.annotate('Saturation Veto: Forced Release',
            xy=(target_x_veto, target_y_veto),
            xytext=(0.3, 0.85),
            ha='left',
            arrowprops=dict(facecolor='red', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=0.1"),
            fontsize=13, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", alpha=0.9), zorder=5)

plt.tight_layout()
fig.savefig('all_baselines_cdf.pdf', format='pdf', bbox_inches='tight')
print("[SUCCESS] Plot generated: all_baselines_cdf.pdf")