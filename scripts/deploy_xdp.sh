cat << 'C_EOF' > xdp_b4_kern.c
#include <uapi/linux/bpf.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
BPF_ARRAY(cross_layer_params, u64, 2);
BPF_ARRAY(mock_delay_map, u64, 1);
int b4_xdp_scheduler(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_PASS;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return XDP_PASS;
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return XDP_PASS;
    if (ip->protocol != 17) return XDP_PASS; 
    int key_delay = 0, key_limit = 1;
    u64 *k_evt = cross_layer_params.lookup(&key_limit);
    u64 *current_delay = mock_delay_map.lookup(&key_delay);
    if (!k_evt || !current_delay) return XDP_PASS;
    u64 delay_scaled = (*current_delay) << 16; 
    if (delay_scaled > *k_evt) { return XDP_DROP; }
    return XDP_PASS;
}
C_EOF

cat << 'PY_EOF' > ebpf_xdp_loader.py
#!/usr/bin/env python3
import time, ctypes
from bcc import BPF
print("🛡️ [XDP 守衛上線] 啟用 SKB Mode...")
b = BPF(src_file="xdp_b4_kern.c")
func = b.load_func("b4_xdp_scheduler", BPF.XDP)
b.attach_xdp(dev="ens4", fn=func, flags=2) # 關鍵修正: 雲端網卡需指定 flags=2 (SKB Mode)
b.get_table("cross_layer_params")[ctypes.c_int(1)] = ctypes.c_uint64(2 * 65536)
b.get_table("mock_delay_map")[ctypes.c_int(0)] = ctypes.c_uint64(20)
try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    b.remove_xdp(dev="ens4", flags=2)
PY_EOF
chmod +x ebpf_xdp_loader.py
