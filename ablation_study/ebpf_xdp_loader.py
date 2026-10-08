#!/usr/bin/env python3
import time, ctypes, argparse
from bcc import BPF

parser = argparse.ArgumentParser()
parser.add_argument('--limit', type=float, default=2.0, help="EVT Cutoff Limit in ms (e.g., 0.1 for strict cutoff)")
args = parser.parse_args()

print(f"[XDP Guard] Enabling SKB Mode for Ablation Study (Limit = {args.limit}ms)...")
print("[Warning] Expecting IP fragmentation leakage for Jumbo payloads at XDP layer.")

# Load eBPF C code
b = BPF(src_file="xdp_b4_kern.c")
func = b.load_func("b4_xdp_scheduler", BPF.XDP)

# Cloud NIC requires flags=2 (SKB Mode / Generic XDP) for XDP attachment
b.attach_xdp(dev="ens4", fn=func, flags=2) 

# Write parameters to BPF Maps (using int casting for float inputs)
b.get_table("cross_layer_params")[ctypes.c_int(1)] = ctypes.c_uint64(int(args.limit * 65536))
b.get_table("mock_delay_map")[ctypes.c_int(0)] = ctypes.c_uint64(20)

try:
    while True: 
        time.sleep(1)
except KeyboardInterrupt:
    b.remove_xdp(dev="ens4", flags=2)
    print("\n[XDP Guard] eBPF detached.")
