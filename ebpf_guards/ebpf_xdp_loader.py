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
