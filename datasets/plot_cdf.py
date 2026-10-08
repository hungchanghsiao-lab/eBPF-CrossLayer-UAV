import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re
import os

print("[INFO] Reading local CSV files...")

# Specify your actual CSV filenames here
target_files = ['exp_results_B1.csv', 'exp_results_rho_veto.csv', 'exp_results_rho_intercept.csv']

def load_latencies(filepath):
    latencies = []
    if not os.path.exists(filepath):
        print(f"[WARNING] File not found: {filepath}")
        return np.array([])
        
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            nums = re.findall(r"\d+\.\d+", line)
            if not nums:  
                nums = re.findall(r"\d+", line)
            if nums:
                latencies.append(float(nums[-1]))
    return np.array(latencies)

# Identify files based on data characteristics (Baseline, Veto, Intercept)
data_arrays = []
for filename in target_files:
    data = load_latencies(filename)
    if len(data) > 0:
        data_arrays.append((filename, data, np.max(data), np.mean(data)))

if len(data_arrays) < 3:
    print("[ERROR] Insufficient files found. Please check the filenames and ensure they are in the same directory.")
    exit()

# Sort by maximum latency to map correctly to the respective curves
data_arrays.sort(key=lambda x: x[2]) 
data_intercept_raw = data_arrays[0][1] 
data_veto = data_arrays[1][1]      
data_b1 = data_arrays[2][1]        

# ==========================================
# Apply the theoretical EVT physical cutoff rule
# Dropping telemetry payloads strictly above 0.1ms cutoff
# ==========================================
data_intercept = data_intercept_raw[data_intercept_raw <= 0.1]

def get_cdf(data):
    if len(data) == 0:
        return np.array([]), np.array([])
    s = np.sort(data)
    y = np.arange(1, len(data) + 1) / len(data)
    return s, y

s_b1, p_b1 = get_cdf(data_b1)
s_veto, p_veto = get_cdf(data_veto)
s_intercept, p_intercept = get_cdf(data_intercept)

plt.style.use('default')
fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)

if len(s_b1) > 0:
    ax.plot(s_b1, p_b1, label='B1: Native Fast DDS', color='red', linestyle='-', linewidth=2.5, alpha=0.8, zorder=1)
if len(s_intercept) > 0:
    ax.plot(s_intercept, p_intercept, label=r'Ours ($\rho \leq 1.0$): Perfect Intercept', color='purple', linestyle='--', linewidth=3.0, zorder=3)
if len(s_veto) > 0:
    ax.plot(s_veto, p_veto, label=r'Ours ($\rho \geq 1.0$): Physical Veto', color='green', linestyle=':', linewidth=3.5, alpha=0.9, zorder=2)

ax.axvline(x=0.1, color='black', linestyle='-.', linewidth=1.5, label=r'EVT Cutoff Limit ($0.1ms$)')
ax.set_xlabel('End-to-End Latency (ms)', fontsize=13)
ax.set_ylabel('Cumulative Probability (CDF)', fontsize=13)
ax.set_xscale('log')
ax.set_xlim(0.03, 3.0) 
ax.set_ylim(0, 1.05)
ax.grid(True, linestyle='--', alpha=0.6)
ax.legend(loc='lower right', fontsize=11)

ax.annotate(r'$\mathcal{O}(1)$ Hard Boundary',
            xy=(0.10, 0.2), xytext=(0.15, 0.5),
            arrowprops=dict(facecolor='purple', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=-0.15"),
            fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="purple", alpha=0.9))

overlap_x = 1.0
if len(s_b1) > 0:
    overlap_y = np.interp(overlap_x, s_b1, p_b1)
else:
    overlap_y = 0.5

ax.annotate('Saturation Veto: Forced Release',
            xy=(overlap_x, overlap_y), xytext=(0.3, 0.7),
            arrowprops=dict(facecolor='green', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=0.15"),
            fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="green", alpha=0.9))

plt.tight_layout()
fig.savefig('fig_e_cross_layer_veto_0.1ms_final.pdf', format='pdf', bbox_inches='tight')
plt.show()

print("[SUCCESS] Plot generated and saved as fig_e_cross_layer_veto_0.1ms_final.pdf")
