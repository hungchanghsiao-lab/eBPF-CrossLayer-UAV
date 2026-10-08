# Cross-Layer eBPF Scheduler for Cyber-Physical Systems

This repository contains the system implementation and reproducibility artifacts for our $\mathcal{O}(1)$ cross-layer scheduling framework, designed for ROS 2 UAV swarms. It utilizes Linux Traffic Control (TC) and the extended Berkeley Packet Filter (eBPF) to mitigate Head-of-Line (HoL) blocking under extreme heavy-tailed network congestion using Extreme Value Theory (EVT) and a dynamic "Physical Veto" ($\rho \ge 1.0$) mechanism.

## Directory Structure

This repository is organized to strictly correspond with the hybrid evaluation methodology presented in our paper:

### 1. Large-Scale Algorithmic Simulation (Exp 1 & 2)
* **`simulation/`**: Contains the `mean_field_sim.py` script. It implements the Mean-Field Abstraction to validate the $\mathcal{O}(1)$ EVT scheduling logic, kinematic stop-loss limits, and parameter sensitivity under macroscopic 500-node swarm conditions.

### 2. Core Implementation & Ablation Baselines
* **`ebpf_guard/`**: The core eBPF scheduler. Includes the LLVM-compiled kernel-space C code (`tc_rho_kern.c`) implementing the $\mathcal{O}(1)$ EVT boundary and Physical Veto logic, along with the Python BCC loader (`ebpf_tc_loader.py`).
* **`ablation_study/`**: Contains the baseline eBPF implementation attached to the XDP layer (`xdp_b4_kern.c`). It demonstrates the architectural fragmentation leakage issue (B4 Baseline) when handling jumbo payloads below the IP stack.
* **`ros2_workspace/`**: C++ source code for ROS 2 Fast DDS test nodes (`incast_publisher.cpp`, `ego_subscriber.cpp`) and `CMakeLists.txt`.

### 3. Edge Emulation & Data Analysis (Exp 3 & 4)
* **`experiments/`**: Automation shell scripts (`run_cluster_b1.sh`, `run_cluster_intercept.sh`, `run_cluster_veto.sh`) to orchestrate the 10-node distributed Synchronized Incast experiment on natively throttled ARM64 edge instances.
* **`data/`**: Stores the raw end-to-end latency measurements (in ms) gathered during the 1000-packet Incast storms.
* **`analysis/`**: Contains the Python plotting script (`plot_cdf.py`) to parse the CSV results and generate the CDF log-scale vector graphics.

## Prerequisites

To fully replicate the experiments, the following environment is required:
*   **OS**: Ubuntu 22.04 LTS
*   **Middleware**: ROS 2 Humble (with Fast DDS)
*   **Kernel Tools**: `bpfcc-tools`, `linux-headers-generic`, `clang`, `llvm`, `cpulimit`
*   **Python Packages**: `scipy`, `bcc`, `pandas`, `numpy`, `matplotlib`
*   **Infrastructure**: A cluster of 10 ARM64 instances (e.g., GCP Tau T2A) configured with SSH/IAP access (1 Receiver/Ego-Node, 9 Sender/Teammate-Nodes).

## Empirical Highlights (10-Node ARM64 Edge Emulation)

We empirically validated the scheduler on a 10-node native **ARM64 architecture**. To faithfully replicate resource-constrained IoT Edge limitations, the eBPF scheduler on the receiver is strictly throttled to **50% of a single ARM core** using `cpulimit`. Under a 9-node Incast attack generating continuous 4000 B Jumbo point cloud payloads:

1. **B1 Baseline (Native Fast DDS)**: The OS queue suffers severe deadlock, resulting in a **3.0%** survival rate.
2. **eBPF Intercept ($\rho \le 1.0$)**: Actively prunes stale jumbo frames strictly at the 0.1 ms EVT cutoff limit, forming an $\mathcal{O}(1)$ Hard Boundary. This clears the queue blockage and increases the payload survival rate to **77.3%**. 
3. **Physical Veto ($\rho \ge 1.0$)**: Under kinematic critical states, the scheduler dynamically suspends the network stop-loss limit to prioritize critical information flow, yielding an **8.2%** survival rate and mirroring the baseline's queue saturation overhead.

## Quick Start

### Phase 1: Large-Scale Algorithmic Simulation
To execute the mean-field abstraction and generate the macroscopic evaluation plots:
    cd simulation
    python3 mean_field_sim.py

### Phase 2: Edge System Emulation (ARM64 Cluster)
Navigate to the `experiments/` directory on the Receiver Node (Node-0). Ensure your GCP CLI is authenticated.

    cd experiments

    # 1. Run the B1 Baseline (Native Fast DDS without eBPF protection)
    ./run_cluster_b1.sh
    
    # 2. Run the eBPF Intercept mechanism (EVT Limit = 0.1ms)
    ./run_cluster_intercept.sh
    
    # 3. Run the Saturation Physical Veto mechanism (Force Release)
    ./run_cluster_veto.sh

### Phase 3: Data Analysis & Visualization
To parse the empirical CSV results and reproduce the CDF comparison plots:
    cd analysis
    pip install numpy matplotlib pandas
    python3 plot_cdf.py

This script will output the final `arm10_latency_cdf.pdf` visualizing the $\mathcal{O}(1)$ Hard Boundary and the latency shift effects.

---

## Implementation Notes & Proof-of-Concept (PoC) Scope

To ensure strict scientific variable isolation and reproducible benchmarking on cloud environments, the provided source code represents a Proof-of-Concept (PoC) focused exclusively on measuring the $\mathcal{O}(1)$ computational overhead of the core EVT decision pipeline on ARM64 ALUs. 

Please note the following architectural simplifications made for this benchmark:
* **Mock Delays via BPF Maps:** Due to the lack of PTP hardware clock synchronization in standard cloud virtual NICs, calculating true one-way latency via `bpf_ktime_get_ns()` is substituted with asynchronous mock injections (`mock_delay_map`). This isolates the pure ALU-constrained arithmetic overhead from environmental clock drift noise.
* **GAP Token Injection Omission:** Algorithm 1 in the paper describes forging an RTPS GAP token to maintain state machine monotonicity. Since synthesizing this token requires complex header rewriting and incremental checksum updates (via `bpf_l4_csum_replace`)—which are standard but verbose kernel routines—they are omitted in this PoC to accurately profile the fundamental `TC_ACT_SHOT` interception overhead.
* **LRU Map Fragmentation Tracking Isolation:** The stateful fragment tracking mechanism utilizing `BPF_MAP_TYPE_LRU_HASH` is a structural necessity for robustly handling IP fragment dispersion. However, to rigorously isolate and profile the standalone single-packet mathematical decision latency of our fixed-point EVT model, the multi-packet LRU correlation logic is separated from this specific benchmarking C source code.

## License
This project is licensed under the Apache License 2.0.
