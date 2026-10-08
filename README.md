# eBPF-CrossLayer-UAV

This repository contains the reproducibility artifacts for the eBPF-based cross-layer QoS scheduling framework designed for ROS 2 UAV swarms. It evaluates the system's resilience against extreme network Incast storms using Extreme Value Theory (EVT) and a dynamic "Saturation Veto" ($\rho \ge 1.0$) mechanism.

## Project Structure

This repository is organized into three main experimental phases, strictly corresponding to the hybrid evaluation methodology presented in the paper:

### 1. Large-Scale Algorithmic Simulation (Exp 1 & 2)
* **`simulation/`**: Contains the `mean_field_sim.py` script. It implements the Mean-Field Abstraction to validate the $\mathcal{O}(1)$ EVT scheduling logic, kinematic stop-loss, and parameter sensitivity. This script reproduces the macroscopic availability and microscopic trajectory results (Fig 5, 6, 7, 8, and 9).

### 2. Hardware-Agnostic Edge Emulation (ARM64 Micro-Benchmark)
To rigorously address the hardware constraints of actual UAV companion computers (e.g., Cortex-A72 on Raspberry Pi 4), this repository includes a pure Python-based micro-benchmark.
* **`ebpf_guard/`**: The core eBPF scheduler. Includes the LLVM-compiled kernel-space C code (`tc_rho_kern.c`) implementing the $\mathcal{O}(1)$ EVT boundary, Out-of-band Telemetry bypass, and Force Release logic, along with the Python BCC loader (`ebpf_tc_loader.py`).
* **`arm_edge_emulation/`**: Contains lightweight UDP telemetry scripts (`echo_server.py`, `incast_shooter_max.py`, `latency_logger.py`, and `plot_cdf.py`) to validate the wire-speed $\mathcal{O}(1)$ performance on a natively throttled **ARM64 architecture (GCP Tau T2A)** without the overhead of the ROS 2 framework.

### 3. Cloud System Emulation Testbed (Exp 3 & 4)
* **`ros2_workspace/`**: C++ source code for ROS 2 Fast DDS nodes. Contains the `incast_publisher` (for generating high-frequency point cloud payloads) and `ego_subscriber` (for capturing end-to-end latency).
* **`ablation_study/`**: Contains alternative eBPF implementations (`xdp_b4_kern.c`) and loaders (`ebpf_xdp_loader.py`) to evaluate architectural baselines such as B4 (XDP Fragment Leakage).
* **`scripts/`**: Automation shell scripts (`run_cluster_exp.sh`) to orchestrate the 10-node distributed Incast storm experiment on Google Cloud Platform (GCP).
* **`datasets/`**: Stores pre-collected benchmarking CSV results and the plotting scripts for both ARM edge emulation and GCP macro-emulation.

## Prerequisites

To fully replicate the experiments, the following environment is required:
*   **OS**: Ubuntu 22.04 LTS
*   **Middleware**: ROS 2 Humble (with Fast DDS) for Phase 3
*   **Kernel Tools**: `bpfcc-tools`, `linux-headers-generic`, `clang`, `llvm`, `cpulimit`
*   **Python Packages**: `scipy`, `bcc`, `pyroute2`, `pandas`, `numpy`, `matplotlib`
*   **Infrastructure**: 
    *   Phase 2: An ARM64 instance (e.g., GCP Tau T2A).
    *   Phase 3: A cluster of 10 x86 nodes (1 Ego-Node, 9 Teammate-Nodes) with SSH/IAP access.

## Quick Start

### Phase 1: Large-Scale Algorithmic Simulation
To execute the mean-field abstraction and generate the algorithmic evaluation plots (Exp 1 & 2):
```bash
cd simulation
python3 mean_field_sim.py
```
*(This will output `fig_a_network_cdf.pdf` through `fig_f_sensitivity.pdf` in the current directory).*

### Phase 2: Hardware-Agnostic Edge Emulation (ARM64)
We empirically validated our $\mathcal{O}(1)$ EVT scheduler on a native **ARM64 architecture**. To faithfully replicate IoT Edge limitations, the eBPF scheduler is strictly throttled to **50% of a single ARM core** using `cpulimit`, while defending against a heavy-tailed Synchronized Incast storm (continuous 4000 B Jumbo Payloads).

#### 📊 Extreme Pressure Evaluation (0.1ms Hard Boundary)
As shown in the CDF evaluation below, under kinematic safety states ($\rho \le 1.0$), our eBPF mechanism drops stale jumbo frames strictly at the **0.1ms EVT cutoff limit**, creating a perfect vertical asymptote (Perfect Intercept). Furthermore, the leftward shift of the purple curve demonstrates the successful mitigation of Head-of-Line (HoL) blocking, accelerating subsequent packets. Under saturation ($\rho \ge 1.0$), it seamlessly triggers the Physical Veto, falling back to the native queue behavior.

![CDF Evaluation](datasets/fig_e_cross_layer_veto_0.1ms_final.png)

#### 🛠️ How to run the Micro-Benchmark
```bash
# 1. On Node-0 (Receiver): Start eBPF scheduler with 0.1ms EVT cutoff
sudo python3 ebpf_guard/ebpf_tc_loader.py --rho 0.8 --limit 0.1 &
sleep 2

# 2. Throttle the ingress scheduler to 50% CPU limit
sudo cpulimit -p $! -l 50 &

# 3. Start Telemetry Echo Server
python3 arm_edge_emulation/echo_server.py

# 4. On Node-1 (Sender): Launch Synchronized Incast & Telemetry
python3 arm_edge_emulation/incast_shooter_max.py &
python3 arm_edge_emulation/latency_logger.py result.csv
```

### Phase 3: Cloud System Emulation (ROS 2 Macro-Benchmark)
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
To compare our cross-layer framework with other architectural baselines, use the built-in ROS 2 parameters and the provided ablation loaders:

```bash
# Run B1 Baseline: Native Fast DDS (Pure OS Queuing without QoS constraints)
ros2 run cross_layer_test ego_subscriber --ros-args -p qos_mode:="B1"

# Run B2 Baseline: Pure ROS 2 Application-Layer QoS (50ms Lifespan)
ros2 run cross_layer_test ego_subscriber --ros-args -p qos_mode:="B2"

# Run B4 Baseline: eBPF attached to XDP (Demonstrating Fragment Leakage)
# Start the XDP guard in a separate terminal before running the subscriber
sudo python3 ablation_study/ebpf_xdp_loader.py --limit 0.1 &
```

⚠️ Implementation Notes & Proof-of-Concept (PoC) Scope

To ensure strict scientific variable isolation and reproducible benchmarking on cloud environments (GCP), the provided source code represents a Proof-of-Concept (PoC) focused exclusively on the core O(1) EVT scheduling logic. 

Please note the following architectural simplifications made for this micro-benchmark:

* **Mock Delays via BPF Maps:** Due to the lack of PTP hardware clock synchronization in GCP virtual NICs, calculating true one-way latency via `bpf_ktime_get_ns()` is substituted with asynchronous mock injections (`mock_delay_map`). This isolates the pure ALU-constrained arithmetic overhead from environmental clock drift noise.
* **GAP Token Injection & Checksum Updates Omission:** Algorithm 1 in the paper describes forging an RTPS GAP token to maintain state machine monotonicity. As this requires complex header rewriting tightly coupled with specific DDS vendor layouts, along with incremental checksum updates (via `bpf_l4_csum_replace`), they are omitted in this PoC. We execute the fundamental `TC_ACT_SHOT` interception to evaluate the theoretical baseline overhead. Deep Packet Inspection (DPI) is similarly bypassed to maximize wire-speed performance in this benchmark.
* **LRU Map Fragmentation Tracking Isolation:** The stateful fragment tracking mechanism utilizing `BPF_MAP_TYPE_LRU_HASH`—designed to robustly handle IP fragment dispersion for jumbo payloads—is a structural necessity for production. However, to accurately profile the standalone single-packet mathematical decision latency of our fixed-point EVT model, the multi-packet LRU correlation logic is isolated from this specific benchmarking source code.

## License
This project is licensed under the Apache License 2.0.
