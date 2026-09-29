#!/usr/bin/env python3
import time, ctypes, argparse
from bcc import BPF
import pyroute2

parser = argparse.ArgumentParser()
parser.add_argument('--rho', type=float, default=1.0, help="Saturation ratio (e.g., 1.0 for Veto)")
parser.add_argument('--limit', type=int, default=2, help="EVT Cutoff Limit in ms")
args = parser.parse_args()

print(f"[TC Guard] Initiating test (Rho = {args.rho}, Limit = {args.limit}ms)...") 
b = BPF(src_file="tc_rho_kern.c")
func = b.load_func("tc_scheduler", BPF.SCHED_CLS)

ip = pyroute2.IPRoute()
idx = ip.link_lookup(ifname="ens4")[0]
try: ip.tc("add", "clsact", idx)
except Exception: pass
ip.tc("add-filter", "bpf", idx, ":1", fd=func.fd, name=func.name, parent="ffff:fff2", classid=1, direct_action=True)

b.get_table("cross_layer_params")[ctypes.c_int(1)] = ctypes.c_uint64(args.limit * 65536) 
b.get_table("cross_layer_params")[ctypes.c_int(2)] = ctypes.c_uint64(int(args.rho * 100))
b.get_table("mock_delay_map")[ctypes.c_int(0)] = ctypes.c_uint64(20)

try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    ip.tc("del", "clsact", idx)
    print("\n[TC Guard] eBPF detached.")