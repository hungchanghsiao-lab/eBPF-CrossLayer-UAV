import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8-paper')
plt.rcParams.update({'font.size': 12, 'font.family': 'serif'})

print("正在讀取標準 CSV 數據...")

# 直接指定讀取 latency_ms 欄位
df = pd.read_csv('exp_results_B1.csv')
latencies = df['latency_ms'].dropna().values

sorted_data = np.sort(latencies)
p = 1. * np.arange(len(sorted_data)) / (len(sorted_data) - 1)

print(f"共解析出 {len(latencies)} 筆有效封包延遲。最高延遲: {sorted_data[-1]:.2f} ms")

plt.figure(figsize=(8, 5))
plt.plot(sorted_data, p, lw=2, color='tab:red', label='B1 (Native Fast DDS)')
plt.axvline(x=15.0, color='k', linestyle='--', lw=1.5, label='EVT Cutoff Limit ($15ms$)')

plt.xlim(0, max(20, sorted_data.max() * 1.1))
plt.ylim(0, 1.05)
plt.xlabel('End-to-End Latency (ms)', fontweight='bold')
plt.ylabel('Cumulative Probability (CDF)', fontweight='bold')
plt.title('Incast Storm Latency Distribution (Baseline)', fontweight='bold')
plt.grid(True, linestyle=':', alpha=0.7)
plt.legend(loc='lower right')
plt.tight_layout()

plt.savefig('cdf_baseline_B1.png', dpi=300)
print("✅ 繪圖完成！已產出 cdf_baseline_B1.png")
