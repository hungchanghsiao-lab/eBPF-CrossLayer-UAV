#!/bin/bash
set -e
echo "========================================================"
echo "🛡️ ARM64 10 節點純 UDP 壓測 (徹底繞過 IAP 限制版) 🛡️"
echo "========================================================"

cat << 'SHOOTER' > incast_shooter_max.py
import socket, time
UDP_IP = "10.148.0.3"
UDP_PORT = 5005
MESSAGE = b"X" * 4000
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
start = time.time()
while time.time() - start < 30:
    try:
        sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))
        time.sleep(0.002)
    except: pass
SHOOTER

cat << 'ECHO' > echo_server.py
import socket, time
UDP_IP = "0.0.0.0"
UDP_PORT = 5006
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.settimeout(1.0)
start = time.time()
while time.time() - start < 40:
    try:
        data, addr = sock.recvfrom(1024)
        sock.sendto(data, addr)
    except: pass
ECHO

cat << 'LOGGER' > latency_logger.py
import socket, time, sys
OUTPUT_FILE = sys.argv[1]
UDP_IP = "10.148.0.3"
UDP_PORT = 5006
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.5)
latencies = []
print("等待 3 秒讓風暴發酵...")
time.sleep(3)
for i in range(1000):
    start = time.time()
    try:
        sock.sendto(b"PING", (UDP_IP, UDP_PORT))
        sock.recvfrom(1024)
        latencies.append((time.time() - start) * 1000 / 2.0)
    except: pass
    time.sleep(0.01)
with open(OUTPUT_FILE, 'w') as f:
    for lat in latencies: f.write(f"data: {lat:.6f}\n")
LOGGER

# 將 Node-0 的複雜指令全部封裝成腳本
cat << 'NODE0' > run_node0.sh
#!/bin/bash
sudo apt-get update >/dev/null 2>&1 || true
sudo apt-get install -y tmux cpulimit >/dev/null 2>&1 || true
sudo pkill -f echo_server.py || true
sudo pkill -f ebpf_tc_loader.py || true
tmux kill-server 2>/dev/null || true
tmux new-session -d -s server 'python3 ~/echo_server.py'
sudo tmux new-session -d -s ebpf 'python3 ~/ebpf_tc_loader.py --rho 0.8 --limit 0.1'
sleep 2
BPF_PID=$(pgrep -f ebpf_tc_loader.py | head -n 1)
if [ ! -z "$BPF_PID" ]; then
    sudo tmux new-session -d -s cpulimit "cpulimit -p $BPF_PID -l 50"
fi
NODE0

# 將僚機的指令封裝成腳本
cat << 'SHOOTER_SH' > run_shooter.sh
#!/bin/bash
tmux kill-server 2>/dev/null || true
tmux new-session -d -s shooter 'python3 ~/incast_shooter_max.py'
SHOOTER_SH

echo "🌐 傳送實體腳本至 10 台機器..."
for i in {1..9}; do
    gcloud compute scp incast_shooter_max.py run_shooter.sh uav-arm-node-$i:~ --zone="asia-southeast1-b" --quiet
done
gcloud compute scp latency_logger.py uav-arm-node-1:~ --zone="asia-southeast1-b" --quiet
gcloud compute scp echo_server.py run_node0.sh uav-arm-node-0:~ --zone="asia-southeast1-b" --quiet

echo -e "\n🛡️ [1/3] 觸發 Node-0 執行 eBPF 防禦..."
# 完美繞過 IAP：利用 nohup 完全切斷 I/O，讓腳本在背景執行，SSH 瞬間乾淨退出！
gcloud compute ssh uav-arm-node-0 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_node0.sh </dev/null >/dev/null 2>&1 &"
echo "⏳ 等待 5 秒讓 Node-0 準備防禦..."
sleep 5

echo -e "\n🔥 [2/3] 觸發 9 台僚機風暴與 Node-1 測速..."
for i in {2..9}; do
    gcloud compute ssh uav-arm-node-$i --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 &"
done

# Node-1 需要等待測速完成，因此不放背景
gcloud compute ssh uav-arm-node-1 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 & python3 ~/latency_logger.py ~/exp_results_arm10_intercept.csv"

echo -e "\n📥 [3/3] 下載測速結果..."
gcloud compute scp uav-arm-node-1:~/exp_results_arm10_intercept.csv ./ --zone="asia-southeast1-b" --quiet || echo "⚠️ 無法抓取結果"
echo "🎉 完美的 10 節點 ARM 極限壓測完成！"
wc -l exp_results_arm10_intercept.csv || true
