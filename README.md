# eBPF-CrossLayer-UAV: Cross-layer eBPF Scheduling Framework for UAV Swarms

**Note for Reviewers:** This repository is prepared for double-blind peer review. All author identities, affiliations, and geographic metadata have been strictly removed to comply with the double-blind policy.

## Overview
This repository contains the reproducibility artifacts, simulation models, and automated execution scripts for our proposed **Cross-layer eBPF Scheduling Framework**. The framework leverages eBPF (Extended Berkeley Packet Filter) at the Linux Traffic Control (TC) layer to mitigate Extreme Value Theory (EVT) tail-risk latency in ROS 2 / Fast DDS based Unmanned Aerial Vehicle (UAV) swarm networks, specifically targeting heavy-tailed incast congestion scenarios.

## Repository Structure

*   `ablation_study/`
    *   Contains the `AF_XDP` baseline implementation (`xdp_b4_kern.c` and loader). Used to demonstrate the limitations of XDP (e.g., lack of IP defragmentation semantics for jumbo frames).
*   `analysis/`
    *   Python scripts for statistical analysis and CDF (Cumulative Distribution Function) visualization.
    *   `plot_cdf_general.py`: Generates the continuous distribution CDF plots with hardware latency calibration and jitter smoothing.
*   `data/`
    *   Raw experimental datasets (`.csv`) for the 6 comparative baselines.
*   `ebpf_guard/`
    *   **Core Contribution:** Contains the TC eBPF programs (`tc_rho_kern.c` and loader).
    *   Implements the \mathcal{O}(1) EVT Cutoff filter and the **Saturation Release (Physical Veto)** mechanism.
    *   Features RTPS **GAP Token spoofing** and progressive UDP checksum recalculation (`bpf_l4_csum_replace`) to prevent silent drops by the OS or Fast DDS.
*   `ros2_workspace/`
    *   ROS 2 application layer source code (C++) simulating the UAV swarm Ego-vehicle subscriber and Incast publishers.
*   `sim/`
    *   `mean_field_sim.py`: Mean-field simulation script for verifying the theoretical upper bounds of the scheduling algorithms.
*   `run_all_baselines.sh`
    *   The fully automated shell script used to deploy, execute, and collect data for all baselines (B1-B4) and our proposed mechanisms.

## Experimental Setup & Reproducibility

The automated script `run_all_baselines.sh` orchestrates a swarm of 8 nodes (1 Ego-receiver, 7 Incast-transmitters) to evaluate the following configurations:

1.  **B1 (Native Fast DDS):** Unmodified ROS 2 DDS environment.
2.  **B2 (App-layer QoS):** Evaluates traditional application-layer history cache dropping (`--ros-args -p qos_history_depth:=1`).
3.  **B3 (S.A. AQM):** Evaluates traditional network-layer Active Queue Management using Linux `fq_codel`.
4.  **B4 (AF_XDP):** Evaluates early-stage kernel bypass filtering via eBPF XDP hooks.
5.  **Ours (Intercept):** Proposed TC eBPF framework operating under standard conditions (\rho \leq 1.0). Replaces delayed payload with forged RTPS GAP tokens.
6.  **Ours (Physical Veto):** Proposed TC eBPF framework operating under saturation limits (\rho \geq 1.0). Bypasses EVT dropping rules to maintain safety invariants.

### Execution

To run the full suite of experiments and collect latency data:

bash run_all_baselines.sh

To regenerate the CDF plots based on the collected `.csv` data:

cd analysis
python3 plot_cdf_general.py

## System Requirements
*   **OS:** Ubuntu 22.04 LTS (Kernel 5.15+ for eBPF support)
*   **Middleware:** ROS 2 Humble Hawksbill with eProsima Fast DDS
*   **Dependencies:** `bcc-tools`, `python3-bpfcc`, `iproute2`, `matplotlib`, `numpy`
