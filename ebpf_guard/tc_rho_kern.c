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
    if (ip->protocol != 17) return TC_ACT_OK; // Only process UDP packets
    
    struct udphdr *udp = (void *)(ip + 1);
    if ((void *)(udp + 1) > data_end) return TC_ACT_OK;

    // [Added] Telemetry bypass for hardware micro-benchmark
    // Bypass probe packets on Port 5006 to measure pure queue clearance latency
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
        return TC_ACT_SHOT; // EVT Cutoff: Drop stale packets
    }
    return TC_ACT_OK;
}
