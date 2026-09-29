#!/bin/bash
# Ensure clean environment
export ROS_DOMAIN_ID=42
export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_unicast.xml
sudo pkill -f ebpf_tc_loader.py
rm -f exp_results_rho_raw.txt exp_results_rho_veto.csv

echo "[1/3] Launching 9-node Incast storm from teammates..."
for i in {1..9}; do
    gcloud compute ssh teammate-$i --zone="asia-east1-b" --quiet --command="export ROS_DOMAIN_ID=42; export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_unicast.xml; source ~/ros2_ws/install/setup.bash; nohup ros2 run cross_layer_test incast_publisher --ros-args -p teammate_id:=\"TM_$i\" > /dev/null 2>&1 & disown"
done

echo "Waiting 10 seconds for ROS 2 underlying discovery and network congestion..."
sleep 10

echo "[2/3] Starting eBPF guard and capturing 20 seconds of data in the storm..."
sudo ../ebpf_guard/ebpf_tc_loader.py --rho 1.0 &
sleep 2

source ~/ros2_ws/install/setup.bash
timeout 20 ros2 run cross_layer_test ego_subscriber --ros-args -p qos_mode:="rho_veto"

echo "[3/3] Experiment finished. Cleaning data and stopping teammates..."
sudo pkill -f ebpf_tc_loader.py
grep "Latency" exp_results_rho_veto_raw.txt | sed -r "s/\x1B\[[0-9;]*[mK]//g" > exp_results_rho_veto.csv

for i in {1..9}; do
    gcloud compute ssh teammate-$i --zone="asia-east1-b" --quiet --command="sudo pkill -9 incast_publisher"
done

wc -l exp_results_rho_veto.csv
echo "Experiment completed. Please download exp_results_rho_veto.csv to your local machine."