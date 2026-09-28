import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from google.colab import files

# ==========================================
# 1. 檔案上傳與讀取 (只需 B1 基準數據)
# ==========================================
print("📦 請上傳 GCP 實驗數據：exp_results_B1.csv")
if not os.path.exists('exp_results_B1.csv'):
    uploaded = files.upload()

# 讀取 B1 基準線 (Ground Truth)
latencies_b1 = pd.read_csv('exp_results_B1.csv')['latency_ms'].dropna().values

# [跡線驅動 1] OURS 正常截斷 (Trace-driven Filter, 模擬 eBPF 在 2.0ms 丟包)
latencies_ours = latencies_b1[latencies_b1 <= 2.0]

# [跡線驅動 2] Rho = 1.2 物理否決權 (模擬 eBPF 強制放行，軌跡完全等價於 B1)
latencies_rho = latencies_b1.copy()

# 計算 CDF
def get_cdf(data):
    s = np.sort(data)
    y = np.arange(1, len(data) + 1) / len(data)
    return s, y

s_b1, p_b1 = get_cdf(latencies_b1)
s_ours, p_ours = get_cdf(latencies_ours)
s_rho, p_rho = get_cdf(latencies_rho)

# ==========================================
# 2. 繪圖區與 PDF 輸出 (對齊模擬章節風格)
# ==========================================
plt.style.use('default')
fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)

# 繪製核心數據線
ax.plot(s_b1, p_b1, label='B1: Native Fast DDS', color='red', linestyle='-', linewidth=2.5, alpha=0.8, zorder=1)
ax.plot(s_ours, p_ours, label=r'Ours ($\rho \leq 1.0$): Perfect Intercept', color='purple', linestyle='--', linewidth=3.0, zorder=3)
ax.plot(s_rho, p_rho, label=r'Ours ($\rho = 1.2$): Physical Veto', color='green', linestyle=':', linewidth=3.5, alpha=0.9, zorder=2)

# 截斷邊界輔助線
ax.axvline(x=2.0, color='black', linestyle='-.', linewidth=1.5, label=r'EVT Cutoff Limit ($2.0ms$)')

# 座標軸與網格設定
ax.set_xlabel('End-to-End Latency (ms)', fontsize=13)
ax.set_ylabel('Cumulative Probability (CDF)', fontsize=13)
ax.set_xlim(0, max(15, s_b1.max() * 1.1))
ax.set_ylim(0, 1.05)
ax.grid(True, linestyle='--', alpha=0.6)
ax.legend(loc='lower right', fontsize=11)

# 【新增】圖解動線：高質感註解框 (完美避開線條交錯處)
# 註解 1：指向紫線的垂直截斷點
ax.annotate(r'$\mathcal{O}(1)$ Hard Boundary',
            xy=(2.0, 0.85), xytext=(3.5, 0.4),
            arrowprops=dict(facecolor='purple', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=0.15"),
            fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="purple", alpha=0.9))

# 註解 2：指向綠線與紅線重合的長尾處，解釋物理否決權
overlap_x = 9.0
overlap_y = np.interp(overlap_x, s_b1, p_b1)
ax.annotate('Saturation Veto:\nForced Release',
            xy=(overlap_x, overlap_y), xytext=(6.5, 0.65),
            arrowprops=dict(facecolor='green', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=-0.15"),
            fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="green", alpha=0.9))

plt.tight_layout()
fig.savefig('fig_e_cross_layer_veto.pdf', format='pdf', bbox_inches='tight')
plt.show()

print("✅ 圖表已繪製完畢！您可從 Colab 下載 fig_e_cross_layer_veto.pdf。")