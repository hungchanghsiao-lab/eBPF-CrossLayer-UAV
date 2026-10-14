#!/bin/bash
PROJECT="${GCP_PROJECT:-anonymous-uav-cps-testbed}"
ZONE="${GCP_ZONE:-us-central1-a}"
NODE0_IP="10.148.0.25"

run_exp() {
  EXP=$1
  EBPF_CMD=$2
  APP_ARGS=$3

  echo "========================================================"
  echo "[INFO] Running Experiment: $EXP (8-node Incast)..."
  echo "========================================================"

  echo "[1/4] Cleaning environment (Removing TC, XDP, and Root AQM)..."
  for i in {0..7}; do
    gcloud compute ssh uav-arm-node-$i --project=$PROJECT --zone=$ZONE --ssh-flag="-o ControlMaster=no" --command="
      sudo pkill -9 -f cross_layer; sudo pkill -9 -f fastdds
      IFACE=\$(ip -br link show | grep -v lo | grep UP | awk '{print \$1}' | head -n 1)
      sudo tc qdisc del dev \$IFACE clsact 2>/dev/null || true
      sudo tc qdisc del dev \$IFACE root 2>/dev/null || true
      sudo ip link set dev \$IFACE xdp off 2>/dev/null || true
    " --quiet 2>/dev/null
    sleep 1
  done
  sleep 2

  echo "[2/4] Starting Node-0 Receiver (Deploying $EXP mechanisms)..."
  gcloud compute ssh uav-arm-node-0 --project=$PROJECT --zone=$ZONE --ssh-flag="-o ControlMaster=no" --command="
    source /opt/ros/humble/setup.bash
    nohup fastdds discovery -i 0 -l $NODE0_IP -p 11811 > /dev/null 2>&1 </dev/null &
    sleep 2
    
    $EBPF_CMD
    
    source ~/UAV-eBPF-CrossLayer-Artifact/ros2_workspace/install/setup.bash
    export ROS_DOMAIN_ID=42
    export ROS_DISCOVERY_SERVER=\"$NODE0_IP:11811\"
    
    rm -f /tmp/${EXP}_raw.log
    nohup timeout 45s ros2 run cross_layer_test ego_subscriber $APP_ARGS > /tmp/${EXP}_raw.log 2>&1 </dev/null &
  " --quiet 2>/dev/null
  sleep 3

  echo "[3/4] Launching 7 Transmitter Nodes (Incast Storm)..."
  for i in {1..7}; do
    gcloud compute ssh uav-arm-node-$i --project=$PROJECT --zone=$ZONE --ssh-flag="-o ControlMaster=no" --command="
      source /opt/ros/humble/setup.bash
      source ~/UAV-eBPF-CrossLayer-Artifact/ros2_workspace/install/setup.bash
      export ROS_DOMAIN_ID=42
      export ROS_DISCOVERY_SERVER=\"$NODE0_IP:11811\"
      nohup timeout 35s ros2 run cross_layer_test incast_publisher > /dev/null 2>&1 </dev/null &
    " --quiet 2>/dev/null
    sleep 1
  done

  echo "[4/4] Generating Incast Storm (Waiting for 45s)..."
  sleep 45

  echo "[INFO] Extracting latencies to CSV..."
  gcloud compute ssh uav-arm-node-0 --project=$PROJECT --zone=$ZONE --ssh-flag="-o ControlMaster=no" --command="
    grep -E 'LATENCY_DATA:|Latency:' /tmp/${EXP}_raw.log | grep -oE '[0-9]+\.[0-9]+' > ~/UAV-eBPF-CrossLayer-Artifact/data/exp_results_arm10_${EXP}.csv
    echo \"[SUCCESS] Extracted \$(wc -l < ~/UAV-eBPF-CrossLayer-Artifact/data/exp_results_arm10_${EXP}.csv) rows for $EXP!\"
  " 2>/dev/null
}

# 1. B1 Baseline (Native Fast DDS)
run_exp "b1" "" ""

# 2. B2 (App-layer Dyn. QoS) - Simulate App-layer drop via history depth
run_exp "b2" "" "--ros-args -p qos_history_depth:=1"

# 3. B3 (AoI/S.A. AQM) - Linux FQ-CoDel Active Queue Management
run_exp "b3" "
  IFACE=\$(ip -br link show | grep -v lo | grep UP | awk '{print \$1}' | head -n 1)
  sudo tc qdisc add dev \$IFACE root fq_codel target 5ms interval 100ms
" ""

# 4. B4 (AF_XDP) - XDP Interceptor (Ablation Study)
run_exp "b4" "
  cd ~/UAV-eBPF-CrossLayer-Artifact/ablation_study
  IFACE=\$(ip -br link show | grep -v lo | grep UP | awk '{print \$1}' | head -n 1)
  sudo nohup python3 ebpf_xdp_loader.py --limit 0.1 > /dev/null 2>&1 </dev/null &
  sleep 2
" ""

# 5. Ours Intercept (TC eBPF GAP Token, rho = 0.9 < 1.0)
run_exp "intercept" "
  cd ~/UAV-eBPF-CrossLayer-Artifact/ebpf_guard
  IFACE=\$(ip -br link show | grep -v lo | grep UP | awk '{print \$1}' | head -n 1)
  sudo nohup python3 ebpf_tc_loader.py --iface \$IFACE --rho 0.9 --limit 0.1 > /dev/null 2>&1 </dev/null &
  sleep 2
" ""

# 6. Ours Veto (TC eBPF Saturation Veto, rho = 1.2 >= 1.0)
run_exp "veto" "
  cd ~/UAV-eBPF-CrossLayer-Artifact/ebpf_guard
  IFACE=\$(ip -br link show | grep -v lo | grep UP | awk '{print \$1}' | head -n 1)
  sudo nohup python3 ebpf_tc_loader.py --iface \$IFACE --rho 1.2 --limit 0.1 > /dev/null 2>&1 </dev/null &
  sleep 2
" ""

echo "[INFO] All 6 baselines completed."