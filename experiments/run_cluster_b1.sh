#!/bin/bash
set -e
echo "========================================================"
echo "🔴 ARM64 10-Node - B1 Baseline (No eBPF Protection) 🔴"
echo "========================================================"

cat << 'NODE0' > run_node0_b1.sh
#!/bin/bash
sudo pkill -f ebpf_tc_loader.py || true
sudo pkill -f echo_server.py || true
tmux kill-server 2>/dev/null || true
tmux new-session -d -s server 'python3 ~/echo_server.py'
NODE0

gcloud compute scp run_node0_b1.sh uav-arm-node-0:~ --zone="asia-southeast1-b" --quiet

echo "🛡️ [1/3] Starting native echo server on Node-0 (No protection)..."
gcloud compute ssh uav-arm-node-0 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_node0_b1.sh </dev/null >/dev/null 2>&1 &"
sleep 5

echo "🔥 [2/3] Triggering 9-node Incast storm and Node-1 latency logger..."
for i in {2..9}; do
    gcloud compute ssh uav-arm-node-$i --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 &"
done

gcloud compute ssh uav-arm-node-1 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 & python3 ~/latency_logger.py ~/exp_results_arm10_b1.csv"

echo "📥 [3/3] Downloading B1 latency results..."
gcloud compute scp uav-arm-node-1:~/exp_results_arm10_b1.csv ./ --zone="asia-southeast1-b" --quiet || echo "⚠️ Failed to fetch results"
wc -l exp_results_arm10_b1.csv || true
