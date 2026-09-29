#!/bin/bash
export ROS_DOMAIN_ID=42
export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_unicast.xml

echo "[1/3] Ensuring clean environment (No eBPF Guards)..."
sudo pkill -f ebpf_tc_loader.py
sudo pkill -f ebpf_xdp_loader.py
sudo tc qdisc del dev ens4 clsact 2>/dev/null
rm -f exp_results_B2_raw.txt exp_results_B2.csv

echo "[2/3] Starting ROS 2 receiver for B2 (Application-Layer QoS Lifespan) mode..."
source ~/ros2_ws/install/setup.bash
# Launching with B2 mode activates the 50ms lifespan QoS profile
timeout 20 ros2 run cross_layer_test ego_subscriber --ros-args -p qos_mode:="B2" > exp_results_B2_raw.txt 2>&1 &
ROS_PID=$!

echo "[3/3] Launching 9 teammate UAVs to initiate incast storm..."
for i in {1..9}; do
    gcloud compute ssh teammate-$i --zone="asia-east1-b" --quiet --command="export ROS_DOMAIN_ID=42; export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_unicast.xml; source ~/ros2_ws/install/setup.bash; nohup ros2 run cross_layer_test incast_publisher --ros-args -p teammate_id:=\"TM_$i\" > /dev/null 2>&1 & disown"
done

sleep 20
echo "Stopping experiment and cleaning data..."
kill $ROS_PID

grep "Latency" exp_results_B2_raw.txt | sed -r "s/\x1B\[[0-9;]*[mK]//g" > exp_results_B2.csv

for i in {1..9}; do
    gcloud compute ssh teammate-$i --zone="asia-east1-b" --quiet --command="sudo pkill -9 incast_publisher"
done

wc -l exp_results_B2.csv
echo "Experiment complete! B2 data saved to exp_results_B2.csv"