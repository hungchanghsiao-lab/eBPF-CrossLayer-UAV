#!/usr/bin/env python3
import time, ctypes
from bcc import BPF
import pyroute2

print("🛡️ [TC] Rho >= 1.0...")
b = BPF(src_file="tc_rho_kern.c")
func = b.load_func("tc_scheduler", BPF.SCHED_CLS)

ip = pyroute2.IPRoute()
idx = ip.link_lookup(ifname="ens4")[0]
try: ip.tc("add", "clsact", idx)
except Exception: pass
ip.tc("add-filter", "bpf", idx, ":1", fd=func.fd, name=func.name, parent="ffff:fff2", classid=1, direct_action=True)

b.get_table("cross_layer_params")[ctypes.c_int(1)] = ctypes.c_uint64(2 * 65536) # 2.0ms bound
b.get_table("cross_layer_params")[ctypes.c_int(2)] = ctypes.c_uint64(100)       # write  Rho >= 1.0 (100)
b.get_table("mock_delay_map")[ctypes.c_int(0)] = ctypes.c_uint64(20)

try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    ip.tc("del", "clsact", idx)
