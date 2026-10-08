import socket
import time
import sys
import csv

if len(sys.argv) < 2:
    print("Usage: python3 latency_logger.py <output_csv_filename>")
    sys.exit(1)

OUTPUT_FILE = sys.argv[1]
# Change this IP to the internal IP of Node-0 (Leader)
UDP_IP = "10.148.0.3"
UDP_PORT = 5006
NUM_PACKETS = 1000

print(f"Shooting telemetry probes to {UDP_IP}:{UDP_PORT}...")
print(f"Saving results to {OUTPUT_FILE} (Sending {NUM_PACKETS} packets)...")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.5)

latencies = []

for i in range(NUM_PACKETS):
    send_time = time.time()
    msg = f"{send_time}".encode()
    sock.sendto(msg, (UDP_IP, UDP_PORT))
    
    try:
        data, addr = sock.recvfrom(1024)
        recv_time = time.time()
        orig_time = float(data.decode())
        latency_ms = (recv_time - orig_time) * 1000
        latencies.append(latency_ms)
    except socket.timeout:
        # Timeout caused by eBPF drops or queue overflow
        pass
    
    time.sleep(0.01) # Control telemetry frequency to avoid interfering with the main incast storm

# Write successful latency data to CSV
with open(OUTPUT_FILE, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Packet_Index", "Latency_ms"])
    for idx, lat in enumerate(latencies):
        writer.writerow([idx, lat])

print(f"Telemetry complete! {len(latencies)}/{NUM_PACKETS} packets recorded successfully.")