#!/bin/bash
export ROS_DOMAIN_ID=42
export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_unicast.xml

# Ensure clean environment
sudo pkill -f ebpf_xdp_loader.py
rm -f exp_results_B4_raw.txt exp_results_B4.csv

echo "[1/3] Starting XDP Guard..."
sudo ./ebpf_xdp_loader.py &
XDP_PID=$!
sleep 2

echo "[2/3] Starting ROS 2 receiver for B4 (XDP) mode..."
source ~/ros2_ws/install/setup.bash
timeout 15 ros2 run cross_layer_test ego_subscriber --ros-args -p qos_mode:="B4" > exp_results_B4_raw.txt 2>&1 &
ROS_PID=$!

echo "[3/3] Launching 9 teammate UAVs to initiate incast storm..."
for i in {1..9}; do
    gcloud compute ssh teammate-$i --zone="asia-east1-b" --quiet --command="export ROS_DOMAIN_ID=42; export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_unicast.xml; source ~/ros2_ws/install/setup.bash; nohup ros2 run cross_layer_test incast_publisher --ros-args -p teammate_id:=\"TM_$i\" > /dev/null 2>&1 & disown"
done

sleep 15
echo "Stopping experiment and cleaning data..."
kill $ROS_PID
sudo kill $XDP_PID
sudo pkill -f ebpf_xdp_loader.py

grep "Latency" exp_results_B4_raw.txt | sed -r "s/\x1B\[[0-9;]*[mK]//g" > exp_results_B4.csv

for i in {1..9}; do
    gcloud compute ssh teammate-$i --zone="asia-east1-b" --quiet --command="sudo pkill -9 incast_publisher"
done

echo "Experiment complete! B4 data saved to exp_results_B4.csv"