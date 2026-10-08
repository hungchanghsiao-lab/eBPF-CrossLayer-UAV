#include <uapi/linux/bpf.h>
#include <linux/in.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/udp.h>

BPF_ARRAY(cross_layer_params, u64, 2);
BPF_ARRAY(mock_delay_map, u64, 1);

int b4_xdp_scheduler(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_PASS;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return XDP_PASS;

    // B4 Ablation: Fragment Leakage Demonstration
    // XDP is positioned below the IP stack and lacks defragmentation semantics.
    // It can only parse L4 headers in the initial fragment. Subsequent orphans leak through.
    if (ip->protocol == IPPROTO_UDP) {
        struct udphdr *udp = (void *)ip + (ip->ihl * 4);
        if ((void *)(udp + 1) <= data_end) {
            if (udp->dest == bpf_htons(5006)) return XDP_PASS; // Bypass probe channel
            // Trigger drop logic here would only drop the first fragment,
            // corrupting the jumbo payload but wasting bandwidth on leaked fragments.
        }
    }
    return XDP_PASS;
}
