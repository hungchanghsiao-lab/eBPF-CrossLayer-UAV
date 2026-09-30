# eBPF-CrossLayer-UAV

This repository contains the reproducibility artifacts for the eBPF-based cross-layer QoS scheduling framework designed for ROS 2 UAV swarms. It evaluates the system's resilience against extreme network Incast storms using Extreme Value Theory (EVT) and a dynamic "Saturation Veto" ($\rho \ge 1.0$) mechanism.

## Project Structure

This repository is organized into two main experimental phases, strictly corresponding to the hybrid evaluation methodology presented in the paper:

### 1. Large-Scale Algorithmic Simulation (Exp 1 & 2)
* **`simulation/`**: Contains the `mean_field_sim.py` script. It implements the Mean-Field Abstraction to validate the $\mathcal{O}(1)$ EVT scheduling logic, kinematic stop-loss, and parameter sensitivity. This script reproduces the macroscopic availability and microscopic trajectory results (Fig 4, 5, 6, 7, and 8).

### 2. Cloud System Emulation Testbed (Exp 3 & 4)
* **`ebpf_kernel/`**: The core eBPF scheduler. Includes the LLVM-compiled kernel-space C code (`tc_rho_kern.c`) implementing the $\mathcal{O}(1)$ EVT boundary and Force Release logic, along with the Python BCC loader.
* **`ros2_workspace/`**: C++ source code for ROS 2 Fast DDS nodes. Contains the `incast_publisher` (for generating high-frequency point cloud payloads) and `ego_subscriber` (for capturing end-to-end latency).
* **`ablation_study/`**: Contains execution scripts and alternative eBPF implementations (e.g., XDP mode) to evaluate architectural baselines such as B1 (Native OS), B2 (App-Layer QoS Lifespan), and B4 (XDP Fragment Leakage).
* **`scripts/`**: Automation shell scripts to orchestrate the 10-node distributed Incast storm experiment on Google Cloud Platform (GCP).
* **`datasets/`**: Stores pre-collected benchmarking CSV results and the plotting scripts for the GCP emulation (Fig 9).

## Prerequisites

To fully replicate the experiments, the following environment is required:
*   **OS**: Ubuntu 22.04 LTS
*   **Middleware**: ROS 2 Humble (with Fast DDS)
*   **Kernel Tools**: `bpfcc-tools`, `linux-headers-generic`, `clang`, `llvm`
*   **Python Packages**: `scipy`, `bcc`, `pyroute2`, `pandas`, `numpy`, `matplotlib`
*   **Infrastructure**: A cluster of 10 nodes (1 Ego-Node, 9 Teammate-Nodes) with SSH/IAP access configured for the emulation phase.

## Quick Start

### Phase 1: Large-Scale Algorithmic Simulation
To execute the mean-field abstraction and generate the algorithmic evaluation plots (Exp 1 & 2):
```bash
cd simulation
python3 mean_field_sim.py
```
*(This will output `fig_a_network_cdf.pdf` through `fig_f_sensitivity.pdf` in the current directory).*

### Phase 2: Cloud System Emulation
#### 1. Build the ROS 2 Workspace
```bash
cd ros2_workspace
source /opt/ros/humble/setup.bash
colcon build --packages-select cross_layer_test
```

#### 2. Execute the Core Incast Storm Experiment (OURS: TC + Saturation Veto)
Navigate to the `scripts/` directory on the Ego-Node. Ensure your GCP CLI is authenticated and `ROS_DOMAIN_ID` is strictly synchronized across all instances.
```bash
cd scripts
./run_cluster_exp.sh
```
This sequentially launches 9 remote ROS 2 publishers, dynamically attaches the eBPF TC hook, and captures latency data under extreme load ($\rho \ge 1.0$).

#### 3. Execute Baseline Ablation Studies (B1, B2 & B4)
To compare our cross-layer framework with other architectural baselines:
```bash
cd ablation_study

# Run B1 Baseline: Native Fast DDS (Pure OS Queuing without QoS constraints)
./run_b1_baseline.sh

# Run B2 Baseline: Pure ROS 2 Application-Layer QoS (50ms Lifespan)
./run_b2_baseline.sh

# Run B4 Baseline: eBPF attached to XDP (Demonstrating Fragment Leakage)
./run_b4_ablation.sh
```

#### 4. Generate Emulation Plots
Once all GCP trace data is collected into the `datasets/` directory:
```bash
cd datasets
python3 master_cdf_plot.py
```
*(This will output `fig_e_cross_layer_veto.pdf`, illustrating the precise $\mathcal{O}(1)$ perfect intercept and the robust long-tail trajectory of the physical veto mechanism).*

## ⚠️ Implementation Notes & Proof-of-Concept (PoC) Scope

To ensure strict scientific variable isolation and reproducible benchmarking on cloud environments (GCP), the provided source code represents a Proof-of-Concept (PoC) of the core $\mathcal{O}(1)$ EVT scheduling logic:
*   **Mock Delays via BPF Maps:** Due to the lack of PTP hardware clock synchronization in GCP virtual NICs, calculating true one-way latency via `bpf_ktime_get_ns()` is substituted with asynchronous mock injections (`mock_delay_map`) to purely benchmark the ALU-constrained arithmetic overhead without clock drift noise.
*   **GAP Token Injection Omission:** Algorithm 1 in the paper describes forging an RTPS GAP token to maintain state machine monotonicity. As this requires complex header rewriting tightly coupled with specific DDS vendor layouts, this PoC currently executes the fundamental `TC_ACT_SHOT` interception to evaluate the theoretical baseline overhead. Deep Packet Inspection (DPI) is similarly bypassed to maximize wire-speed performance in this benchmark.

## License
This project is licensed under the Apache License 2.0.