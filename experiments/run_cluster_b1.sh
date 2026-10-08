#!/bin/bash
set -e
echo "========================================================"
echo "🔴 ARM64 10 節點 - B1 基準組 (無 eBPF 防護版) 🔴"
echo "========================================================"

cat << 'NODE0' > run_node0_b1.sh
#!/bin/bash
sudo pkill -f ebpf_tc_loader.py || true
sudo pkill -f echo_server.py || true
tmux kill-server 2>/dev/null || true
tmux new-session -d -s server 'python3 ~/echo_server.py'
NODE0

gcloud compute scp run_node0_b1.sh uav-arm-node-0:~ --zone="asia-southeast1-b" --quiet

echo "🛡️ [1/3] Node-0 啟動原生回音伺服器 (無防護)..."
gcloud compute ssh uav-arm-node-0 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_node0_b1.sh </dev/null >/dev/null 2>&1 &"
sleep 5

echo "🔥 [2/3] 觸發 9 台僚機風暴與 Node-1 測速..."
for i in {2..9}; do
    gcloud compute ssh uav-arm-node-$i --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 &"
done

gcloud compute ssh uav-arm-node-1 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 & python3 ~/latency_logger.py ~/exp_results_arm10_b1.csv"

echo "📥 [3/3] 下載 B1 測速結果..."
gcloud compute scp uav-arm-node-1:~/exp_results_arm10_b1.csv ./ --zone="asia-southeast1-b" --quiet || echo "⚠️ 無法抓取結果"
wc -l exp_results_arm10_b1.csv || true
