cat << 'C_EOF' > tc_rho_kern.c
#include <uapi/linux/bpf.h>
#include <uapi/linux/pkt_cls.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>

BPF_ARRAY(cross_layer_params, u64, 3); // idx 0: delay, idx 1: limit, idx 2: rho
BPF_ARRAY(mock_delay_map, u64, 1);

int tc_scheduler(struct __sk_buff *skb) {
    void *data_end = (void *)(long)skb->data_end;
    void *data = (void *)(long)skb->data;
    struct ethhdr *eth = data;
    
    if ((void *)(eth + 1) > data_end) return TC_ACT_OK;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return TC_ACT_OK;
    
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return TC_ACT_OK;
    if (ip->protocol != 17) return TC_ACT_OK; 
    
    int key_delay = 0, key_limit = 1, key_rho = 2;
    u64 *k_evt = cross_layer_params.lookup(&key_limit);
    u64 *k_rho = cross_layer_params.lookup(&key_rho);
    u64 *current_delay = mock_delay_map.lookup(&key_delay);

    if (!k_evt || !k_rho || !current_delay) return TC_ACT_OK;

    // 🚀 核心邏輯：物理否決權 (Collision Saturation Veto)
    // 當 rho >= 100 (對應 1.0) 時，代表碰撞風險飽和，強制放行所有封包！
    if (*k_rho >= 100) {
        return TC_ACT_OK; 
    }

    u64 delay_scaled = (*current_delay) << 16; 
    if (delay_scaled > *k_evt) {
        return TC_ACT_SHOT; // 丟棄
    }
    return TC_ACT_OK;
}
C_EOF

cat << 'PY_EOF' > ebpf_tc_loader.py
#!/usr/bin/env python3
import time, ctypes
from bcc import BPF
import pyroute2

print("🛡️ [TC 守衛上線] 啟動極端情境 (Rho = 1.2) 測試...")
b = BPF(src_file="tc_rho_kern.c")
func = b.load_func("tc_scheduler", BPF.SCHED_CLS)

ip = pyroute2.IPRoute()
idx = ip.link_lookup(ifname="ens4")[0]
try: ip.tc("add", "clsact", idx)
except Exception: pass
ip.tc("add-filter", "bpf", idx, ":1", fd=func.fd, name=func.name, parent="ffff:fff2", classid=1, direct_action=True)

b.get_table("cross_layer_params")[ctypes.c_int(1)] = ctypes.c_uint64(2 * 65536) # 2.0ms 極限
b.get_table("cross_layer_params")[ctypes.c_int(2)] = ctypes.c_uint64(120)       # 寫入 Rho = 1.2 (120)
b.get_table("mock_delay_map")[ctypes.c_int(0)] = ctypes.c_uint64(20)

try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    ip.tc("del", "clsact", idx)
PY_EOF
chmod +x ebpf_tc_loader.py
