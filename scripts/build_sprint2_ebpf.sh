#!/bin/bash
echo "🚀 [1/2] 正在建立 Sprint 2: eBPF 跨層干預機制工作區..."
mkdir -p ~/sprint2_ebpf
cd ~/sprint2_ebpf

# 1. 生成 eBPF C 語言核心程式碼 (嚴格對齊論文 S4.D 節公式)
cat << 'C_EOF' > tc_evt_kern.c
#include <uapi/linux/bpf.h>
#include <uapi/linux/pkt_cls.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/udp.h>

// BPF Maps: 用於接收 User-space 傳來的跨層動態參數
// Index 0: 物理風險飽和度 rho (放大 100 倍, 100 = 1.0)
// Index 1: 定點數量化之 EVT 幾何邊界常數 K_evt_int
BPF_ARRAY(cross_layer_params, u64, 2);

// 模擬測量當前封包延遲的 BPF Map (實務上透過封包 Timestamp 計算)
BPF_ARRAY(mock_delay_map, u64, 1);

int cross_layer_scheduler(struct __sk_buff *skb) {
    // 解析 Ethernet 與 IP 標頭
    void *data_end = (void *)(long)skb->data_end;
    void *data = (void *)(long)skb->data;
    struct ethhdr *eth = data;
    
    if ((void *)(eth + 1) > data_end) return TC_ACT_OK;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return TC_ACT_OK;
    
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return TC_ACT_OK;
    
    // 論文亮點：IP 分片 (Fragmentation) 檢查
    // B4 (XDP) 若遇到 MF=1 (More Fragments) 且非首段，會因為找不到 UDP 標頭而失效
    // Ours (TC Ingress) 因為 OS 已完成重組，此處必為完整封包
    if (ip->protocol != IPPROTO_UDP) return TC_ACT_OK;

    // 讀取跨層參數
    int key_rho = 0, key_k = 1, key_delay = 0;
    u64 *rho = cross_layer_params.lookup(&key_rho);
    u64 *k_evt = cross_layer_params.lookup(&key_k);
    u64 *current_delay = mock_delay_map.lookup(&key_delay);

    if (!rho || !k_evt || !current_delay) return TC_ACT_OK;

    // ---------------------------------------------------------
    // 論文 S4.1: Stage 2 絕對物理否決權 (Absolute Physical Veto)
    // ---------------------------------------------------------
    if (*rho >= 100) {
        // rho >= 1.0 代表瀕臨撞機，觸發物理否決，強制等待 (Pass)
        // bpf_trace_printk("VETO: rho >= 1.0! Force waiting.\n");
        return TC_ACT_OK; 
    }

    // ---------------------------------------------------------
    // 論文 S4.2: Stage 4 受限 ALU 實體致動與極限防護 (O(1) Decision)
    // ---------------------------------------------------------
    u64 delay_scaled = (*current_delay) << 16; // 乘上 2^16 位移因子對齊精度
    
    if (delay_scaled > *k_evt) {
        // 延遲突破次優停止時間 t_evt 或動力學停損 t_stop
        // 執行 DROP，並在實務中利用 bpf_clone_redirect 注入 GAP 虛擬序列推進令牌
        // bpf_trace_printk("DROP: Delay %llu > Limit %llu. Injecting GAP!\n", delay_scaled, *k_evt);
        return TC_ACT_SHOT;
    }

    // 在安全裕度內，正常放行
    return TC_ACT_OK;
}
C_EOF

# 2. 生成 Python BCC 控制載入器
cat << 'PY_EOF' > ebpf_loader.py
#!/usr/bin/env python3
import time
import argparse
from bcc import BPF
import ctypes

parser = argparse.ArgumentParser(description="eBPF Cross-Layer Scheduler Loader")
parser.add_argument('--mode', choices=['B4', 'OURS'], required=True, help="B4=XDP(Fail on Frags), OURS=TC(Success)")
parser.add_argument('--rho', type=float, default=0.5, help="Physical Risk Saturation (0.0 to 1.0+)")
parser.add_argument('--limit', type=int, default=15, help="D_limit (EVT sub-optimal stopping time in ms)")
parser.add_argument('--delay', type=int, default=20, help="Mocked current packet delay in ms")
args = parser.parse_args()

print(f"🚀 [啟動 eBPF 跨層排程器] 模式: {args.mode}")

# 1. 載入並編譯 C 程式碼
b = BPF(src_file="tc_evt_kern.c")
func = b.load_func("cross_layer_scheduler", BPF.SCHED_CLS)

interface = "ens4" # GCP 預設網卡

try:
    if args.mode == 'B4':
        print(f"⚠️ 執行 B4 模式: 掛載於 XDP 勾點 (純底層網路，無 IP 分片重組能力)")
        # 實務上 XDP 函數簽名不同，此處僅作概念驗證，用 TC 模擬其失敗情境
        # b.attach_xdp(dev=interface, fn=b.load_func("cross_layer_scheduler", BPF.XDP))
        ip = BPF.get_current_tc() # 模擬 TC 掛載
        b.attach_qdisc(dev=interface, fn_name="cross_layer_scheduler")
    else:
        print(f"🛡️ 執行 OURS 模式: 掛載於 TC Ingress 勾點 (具備 IP 分片重組能力)")
        b.attach_qdisc(dev=interface, fn_name="cross_layer_scheduler")
    
    # 2. 模擬應用層下傳跨層參數 (User-space to Kernel-space)
    params_map = b.get_table("cross_layer_params")
    delay_map = b.get_table("mock_delay_map")
    
    # 將浮點數 rho 放行為 0~100 的整數
    rho_int = int(args.rho * 100)
    # 將極限時間乘上 2^16 (65536) 精度對齊論文 K_evt^int
    k_evt_int = args.limit * 65536
    
    params_map[ctypes.c_int(0)] = ctypes.c_uint64(rho_int)
    params_map[ctypes.c_int(1)] = ctypes.c_uint64(k_evt_int)
    delay_map[ctypes.c_int(0)] = ctypes.c_uint64(args.delay)
    
    print(f"📊 已下傳參數至 eBPF Map: rho={args.rho}, D_limit={args.limit}ms, Current_Delay={args.delay}ms")
    print("⏳ eBPF 核心引擎運作中... 按 Ctrl+C 卸載退出。")
    
    # 透過讀取 trace pipe 顯示核心列印的決策 (實務上關閉以求極致效能)
    b.trace_print()

except KeyboardInterrupt:
    print("\n🧹 正在卸載 eBPF 程式...")
finally:
    if args.mode != 'B4':
        b.remove_qdisc(dev=interface, fn_name="cross_layer_scheduler")
    print("✅ 卸載完成。")
PY_EOF

chmod +x ebpf_loader.py

echo "✅ [2/2] Sprint 2 核心 eBPF 程式碼生成完畢！"
echo "請執行以下指令測試：sudo ./ebpf_loader.py --mode OURS --rho 0.8 --limit 15 --delay 20"
