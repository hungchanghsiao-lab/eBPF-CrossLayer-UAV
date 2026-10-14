#!/usr/bin/env python3
import time, math, ctypes, argparse
from bcc import BPF
import pyroute2

parser = argparse.ArgumentParser(description="TC eBPF Cross-Layer EVT Scheduler Loader")
parser.add_argument("--iface", type=str, default="ens4", help="Network interface name")
parser.add_argument("--rho", type=float, default=0.9, help="Physical risk saturation ratio rho")
parser.add_argument("--limit", type=float, default=0.1, help="EVT cutoff limit in ms")
parser.add_argument("--xi", type=float, default=0.5, help="GPD shape parameter xi")
parser.add_argument("--sigma", type=float, default=50.0, help="GPD scale parameter sigma (us)")
parser.add_argument("--mu", type=float, default=50.0, help="GPD threshold mu (us)")
args = parser.parse_args()

Q_BITS = 16
SCALE_Q = 1 << Q_BITS
XI_TH = 1e-4

print(f"🛡️ [TC eBPF Guard] Attaching to {args.iface} (rho={args.rho}, limit={args.limit}ms)...")
b = BPF(src_file="tc_rho_kern.c")
func = b.load_func("tc_scheduler", BPF.SCHED_CLS)

ip = pyroute2.IPRoute()
idx = ip.link_lookup(ifname=args.iface)[0]
try:
    ip.tc("add", "clsact", idx)
except Exception:
    pass
ip.tc("add-filter", "bpf", idx, ":1", fd=func.fd, name=func.name,
      parent="ffff:fff2", classid=1, direct_action=True)

# Stage 4: L'Hopital Limit & Q16.16 Fixed-Point Quantization (Eq. 18)
rho_scaled = int(args.rho * 100)
gamma_drop = min(max(1.0 - args.rho, 0.01), 0.99)

if abs(args.xi) > XI_TH:
    k_evt = ((1.0 - gamma_drop) ** (-args.xi) - 1.0) / args.xi
else:
    k_evt = -math.log(1.0 - gamma_drop)

k_evt_int = int(k_evt * SCALE_Q)
sigma_int = int(args.sigma * SCALE_Q)
xi_int    = int(args.xi * SCALE_Q)
mu_ns     = int(args.mu * 1000)
t_stop_ns = int(args.limit * 1_000_000)
d_max_ns  = int(args.limit * 1_000_000)

params_table = b.get_table("cross_layer_params")
params_table[ctypes.c_int(0)] = ctypes.c_uint64(rho_scaled)
params_table[ctypes.c_int(1)] = ctypes.c_uint64(k_evt_int)
params_table[ctypes.c_int(2)] = ctypes.c_uint64(sigma_int)
params_table[ctypes.c_int(3)] = ctypes.c_uint64(xi_int)
params_table[ctypes.c_int(4)] = ctypes.c_uint64(mu_ns)
params_table[ctypes.c_int(5)] = ctypes.c_uint64(t_stop_ns)
params_table[ctypes.c_int(6)] = ctypes.c_uint64(d_max_ns)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    ip.tc("del", "clsact", idx)
