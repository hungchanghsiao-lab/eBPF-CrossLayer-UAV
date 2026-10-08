#!/usr/bin/env python3
import time, ctypes, argparse
from bcc import BPF

parser = argparse.ArgumentParser()
parser.add_argument('--limit', type=float, default=0.1, help="EVT Cutoff Limit")
args = parser.parse_args()

print(f"[XDP Guard] Enabling SKB Mode for Ablation Study (Limit = {args.limit}ms)...")
b = BPF(src_file="xdp_b4_kern.c")
func = b.load_func("b4_xdp_scheduler", BPF.XDP)

# Cloud virtual NICs typically require flags=2 (SKB Mode) for XDP attachment
b.attach_xdp(dev="ens4", fn=func, flags=2) 

limit_int = int(args.limit * 65536)
b.get_table("cross_layer_params")[ctypes.c_int(1)] = ctypes.c_uint64(limit_int)
b.get_table("mock_delay_map")[ctypes.c_int(0)] = ctypes.c_uint64(20)

try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    print("\nDetaching XDP Guard...")
    b.remove_xdp(dev="ens4", flags=2)
