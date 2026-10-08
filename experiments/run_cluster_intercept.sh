#!/bin/bash
set -e
echo "========================================================"
echo "🛡️ ARM64 10-Node Pure UDP Stress Test (IAP Bypass Version) 🛡️"
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
print("Waiting 3 seconds for the storm to build up...")
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

# Encapsulate complex commands for Node-0 into a script
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

# Encapsulate commands for shooter nodes into a script
cat << 'SHOOTER_SH' > run_shooter.sh
#!/bin/bash
tmux kill-server 2>/dev/null || true
tmux new-session -d -s shooter 'python3 ~/incast_shooter_max.py'
SHOOTER_SH

echo "🌐 Transferring scripts to 10 machines..."
for i in {1..9}; do
    gcloud compute scp incast_shooter_max.py run_shooter.sh uav-arm-node-$i:~ --zone="asia-southeast1-b" --quiet
done
gcloud compute scp latency_logger.py uav-arm-node-1:~ --zone="asia-southeast1-b" --quiet
gcloud compute scp echo_server.py run_node0.sh uav-arm-node-0:~ --zone="asia-southeast1-b" --quiet

echo -e "\n🛡️ [1/3] Triggering eBPF defense on Node-0..."
# IAP Bypass: Use nohup to detach I/O and run in background, allowing SSH to exit cleanly!
gcloud compute ssh uav-arm-node-0 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_node0.sh </dev/null >/dev/null 2>&1 &"
echo "⏳ Waiting 5 seconds for Node-0 to initialize defense..."
sleep 5

echo -e "\n🔥 [2/3] Triggering 9-node Incast storm and Node-1 latency logger..."
for i in {2..9}; do
    gcloud compute ssh uav-arm-node-$i --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 &"
done

# Node-1 needs to wait for latency logging to finish, so it runs in foreground
gcloud compute ssh uav-arm-node-1 --zone="asia-southeast1-b" --quiet --command="nohup bash ~/run_shooter.sh </dev/null >/dev/null 2>&1 & python3 ~/latency_logger.py ~/exp_results_arm10_intercept.csv"

echo -e "\n📥 [3/3] Downloading latency results..."
gcloud compute scp uav-arm-node-1:~/exp_results_arm10_intercept.csv ./ --zone="asia-southeast1-b" --quiet || echo "⚠️ Failed to fetch results"
echo "🎉 10-Node ARM Extreme Stress Test Completed Successfully!"
wc -l exp_results_arm10_intercept.csv || true
