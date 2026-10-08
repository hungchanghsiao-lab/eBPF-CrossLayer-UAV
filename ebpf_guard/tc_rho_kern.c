#include <uapi/linux/bpf.h>
#include <uapi/linux/pkt_cls.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/udp.h>

BPF_ARRAY(cross_layer_params, u64, 3);
BPF_ARRAY(mock_delay_map, u64, 1);

int tc_scheduler(struct __sk_buff *skb) {
    void *data_end = (void *)(long)skb->data_end;
    void *data = (void *)(long)skb->data;
    struct ethhdr *eth = data;
    
    if ((void *)(eth + 1) > data_end) return TC_ACT_OK;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return TC_ACT_OK;
    
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return TC_ACT_OK;
    if (ip->protocol != 17) return TC_ACT_OK; // 只處理 UDP
    
    struct udphdr *udp = (void *)(ip + 1);
    if ((void *)(udp + 1) > data_end) return TC_ACT_OK;

    // [新增] 針對硬體微型測試 (Micro-benchmark) 的遙測通道
    // 放行 Port 5006 的探測封包，以純粹測量佇列清空後的真實延遲
    if (udp->dest == bpf_htons(5006)) return TC_ACT_OK;
    
    int key_delay = 0, key_limit = 1, key_rho = 2;
    u64 *k_evt = cross_layer_params.lookup(&key_limit);
    u64 *k_rho = cross_layer_params.lookup(&key_rho);
    u64 *current_delay = mock_delay_map.lookup(&key_delay);

    if (!k_evt || !k_rho || !current_delay) return TC_ACT_OK;

    // Saturation Veto: Forced Release
    if (*k_rho >= 100) {
        return TC_ACT_OK; 
    }

    // Perfect Intercept: O(1) Hard Boundary
    u64 delay_scaled = (*current_delay) << 16; 
    if (delay_scaled > *k_evt) {
        return TC_ACT_SHOT; // EVT Cutoff: 丟棄過期封包
    }
    return TC_ACT_OK;
}
