#!/usr/bin/env python3
import time, ctypes, argparse
from bcc import BPF
import pyroute2

parser = argparse.ArgumentParser()
parser.add_argument('--rho', type=float, default=1.0, help="Saturation ratio (e.g., 1.2 for Veto, 0.8 for Intercept)")
parser.add_argument('--limit', type=float, default=2.0, help="EVT Cutoff Limit in ms (e.g., 0.1 for strict cutoff)")
args = parser.parse_args()

print(f"[TC Guard] Initiating cross-layer scheduler (Rho = {args.rho}, Limit = {args.limit}ms)...") 

# 載入 eBPF C 程式碼
b = BPF(src_file="tc_rho_kern.c")
func = b.load_func("tc_scheduler", BPF.SCHED_CLS)

# 掛載到網卡 (預設為 ens4，請依環境修改)
ip = pyroute2.IPRoute()
idx = ip.link_lookup(ifname="ens4")[0]
try: 
    ip.tc("add", "clsact", idx)
except Exception: 
    pass
ip.tc("add-filter", "bpf", idx, ":1", fd=func.fd, name=func.name, parent="ffff:fff2", classid=1, direct_action=True)

# 寫入參數至 BPF Maps (注意 int 強制轉型，解決 float 報錯)
b.get_table("cross_layer_params")[ctypes.c_int(1)] = ctypes.c_uint64(int(args.limit * 65536)) 
b.get_table("cross_layer_params")[ctypes.c_int(2)] = ctypes.c_uint64(int(args.rho * 100))
# 模擬封包在 OS 佇列中經歷的延遲 (寫死 20ms 以觸發 > 0.1ms 的截斷)
b.get_table("mock_delay_map")[ctypes.c_int(0)] = ctypes.c_uint64(20)

try:
    while True: 
        time.sleep(1)
except KeyboardInterrupt:
    ip.tc("del", "clsact", idx)
    print("\n[TC Guard] eBPF detached.")
