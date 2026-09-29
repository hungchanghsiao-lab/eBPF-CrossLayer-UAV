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
    
    // IP Fragmentation leak issue: XDP cannot parse subsequent fragments (offset > 0)
    // It is forced to pass them, leaking incomplete packets to the OS reassembly queue
    if (ip->frag_off & bpf_htons(0x1FFF)) return XDP_PASS;
    
    int key_delay = 0, key_limit = 1;
    u64 *k_evt = cross_layer_params.lookup(&key_limit);
    u64 *current_delay = mock_delay_map.lookup(&key_delay);
    
    if (!k_evt || !current_delay) return XDP_PASS;
    
    u64 delay_scaled = (*current_delay) << 16; 
    if (delay_scaled > *k_evt) { 
        return XDP_DROP; 
    }
    return XDP_PASS;
}