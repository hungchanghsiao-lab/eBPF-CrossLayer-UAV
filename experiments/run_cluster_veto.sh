#!/bin/bash
set -e
echo "========================================================"
echo "🟢 ARM64 10-Node - Physical Veto Group (ρ = 1.2) 🟢"
echo "========================================================"

cat << 'NODE0' > run_node0_veto.sh
#!/bin/bash
sudo pkill -f echo_server.py || true
sudo pkill -f ebpf_tc_loader.py || true
tmux kill-server 2>/dev/null || true
tmux new-session -d -s server 'python3 ~/echo_server.py'
sudo tmux new-session -d -s ebpf 'python3 ~/ebpf_tc_loader.py --rho 1.2 --limit 0.1'
sleep 2
BPF_PID=$(pgrep -f ebpf_tc_loader.py | head -n 1)
if [ ! -z "$BPF_PID" ]; then
    sudo tmux new-session -d -s cpulimit "cpulimit -p $BPF_PID -l 50"
fi
NODE0

gcloud compute scp run_node0_veto.sh uav-arm-node-0:~ --zone="asia-southeast1-b" --quiet

echo "🛡️ [1/3] Starting eBPF defense on Node-0 (Veto Mode)..."
gcloud compute ssh uav-arm-node-0 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_node0_veto.sh </dev/null >/dev/null 2>&1 &"
sleep 5

echo "🔥 [2/3] Triggering 9-node Incast storm and Node-1 latency logger..."
for i in {2..9}; do
    gcloud compute ssh uav-arm-node-$i --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 &"
done

gcloud compute ssh uav-arm-node-1 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 & python3 ~/latency_logger.py ~/exp_results_arm10_veto.csv"

echo "📥 [3/3] Downloading Veto latency results..."
gcloud compute scp uav-arm-node-1:~/exp_results_arm10_veto.csv ./ --zone="asia-southeast1-b" --quiet || echo "⚠️ Failed to fetch results"
wc -l exp_results_arm10_veto.csv || true
