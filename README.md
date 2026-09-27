# eBPF-CrossLayer-UAV

## 🚀 Artifacts Overview

* **`ebpf_guards/`**: The core eBPF C programs (`tc_rho_kern.c`, `xdp_b4_kern.c`) and their BCC Python loaders. 
* **`scripts/`**: Bash scripts for automated cluster deployment, eBPF compilation, and hook attachment (e.g., `full_setup.sh`, `deploy_tc_rho.sh`).
* **`ros2_config/`**: Contains `fastdds_unicast.xml`, an essential configuration to bypass multicast limitations in cloud environments for reproducing Incast storms.
* **`datasets/`**: Real-world trace-driven data collected from a 10-node Google Cloud Platform (GCP) cluster (`exp_results_B1.csv`).
  * *Note on `exp_results_B4.csv`:* This 0-byte file represents the empirical result of our ablation study on the XDP hook. When facing 4000B payload fragmentation, XDP's lack of IP reassembly semantics causes 100% fragment leakage and application-layer starvation.
* **`evaluation/`**: Python plotting scripts (e.g., `master_cdf_plot.py`) used to generate the exact Master CDF plots featured in Section 5 of our paper.
