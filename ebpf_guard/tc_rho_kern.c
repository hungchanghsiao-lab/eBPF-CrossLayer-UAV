#include <uapi/linux/bpf.h>
#include <uapi/linux/pkt_cls.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/udp.h>
#include <linux/in.h>
#include <linux/stddef.h>

#define IP_MF_FLAG     0x2000
#define IP_OFFSET_MASK 0x1FFF
#define RTPS_MAGIC_LE  0x53505452 /* "RTPS" in Little-Endian */

#define ACT_PASS 0
#define ACT_DROP 1

/* Key structure for Stateful IP Fragment Tracking (Map F) */
struct frag_key_t {
    __be32 saddr;
    __be16 ip_id;
    __u16  pad;
};

/*
 * Map F: Stateful LRU Hash Map for tracking fragmented jumbo payloads
 * Map M: Per-topic state array (index 0: n_drop counter, index 1: baseline_ts_ns)
 * cross_layer_params: Fixed-point parameters packed by user-space daemon
 *   [0]: rho_scaled (0..100+, where >= 100 triggers Absolute Physical Veto)
 *   [1]: K_evt_int  (Q16.16 fixed-point geometric boundary constant)
 *   [2]: sigma_int  (Q16.16 quantized GPD scale parameter, in us)
 *   [3]: xi_int     (Q16.16 quantized GPD shape parameter)
 *   [4]: mu_ns      (GPD threshold mu, in ns)
 *   [5]: t_stop_ns  (Kinematic stop-loss ceiling t_stop, in ns)
 *   [6]: d_max_ns   (Hard control deadline D_max - tau_proc, in ns)
 */
BPF_LRU_HASH(frag_track_map, struct frag_key_t, u8, 4096);
BPF_ARRAY(state_map, u64, 4);
BPF_ARRAY(cross_layer_params, u64, 8);

int tc_scheduler(struct __sk_buff *skb) {
    void *data = (void *)(long)skb->data;
    void *data_end = (void *)(long)skb->data_end;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return TC_ACT_OK;
    if (eth->h_proto != bpf_htons(ETH_P_IP)) return TC_ACT_OK;

    struct iphdr *ip = (struct iphdr *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return TC_ACT_OK;
    if (ip->protocol != IPPROTO_UDP) return TC_ACT_OK;

    /* Extract IP fragmentation fields */
    __u16 frag_off = bpf_ntohs(ip->frag_off);
    __u16 frag_offset = frag_off & IP_OFFSET_MASK;

    struct frag_key_t fkey = {};
    fkey.saddr = ip->saddr;
    fkey.ip_id = ip->id;

    /* Algorithm 1 (Lines 1-3): Subsequent Orphan Fragment O(1) Lookup */
    if (frag_offset > 0) {
        u8 *cached_act = frag_track_map.lookup(&fkey);
        if (cached_act && *cached_act == ACT_DROP) {
            return TC_ACT_SHOT;
        }
        return TC_ACT_OK;
    }

    /* Initial Fragment (frag_offset == 0): Parse L4 UDP & RTPS Headers */
    struct udphdr *udp = (struct udphdr *)(ip + 1);
    if ((void *)(udp + 1) > data_end) return TC_ACT_OK;

    /* Require at least 24 bytes of UDP payload (20B RTPS Header + 4B Submessage) */
    int payload_offset = sizeof(*eth) + sizeof(*ip) + sizeof(*udp);
    if ((void *)(udp + 1) + 24 > data_end) return TC_ACT_OK;

    __u32 rtps_magic = 0;
    if (bpf_skb_load_bytes(skb, payload_offset, &rtps_magic, sizeof(rtps_magic)) < 0)
        return TC_ACT_OK;

    /* Verify RTPS protocol magic or control-critical data stream (T_cont) */
    int idx_ndrop = 0, idx_base_ts = 1;
    u64 *n_drop_ptr = state_map.lookup(&idx_ndrop);
    u64 *base_ts_ptr = state_map.lookup(&idx_base_ts);
    if (!n_drop_ptr || !base_ts_ptr) return TC_ACT_OK;

    /* Stage 1 & 2: Physical Risk Saturation & Absolute Veto (Eq. 12) */
    int idx_rho = 0, idx_kevt = 1, idx_sigma = 2, idx_xi = 3;
    int idx_mu = 4, idx_tstop = 5, idx_dmax = 6;

    u64 *rho_ptr   = cross_layer_params.lookup(&idx_rho);
    u64 *kevt_ptr  = cross_layer_params.lookup(&idx_kevt);
    u64 *sigma_ptr = cross_layer_params.lookup(&idx_sigma);
    u64 *xi_ptr    = cross_layer_params.lookup(&idx_xi);
    u64 *mu_ptr    = cross_layer_params.lookup(&idx_mu);
    u64 *tstop_ptr = cross_layer_params.lookup(&idx_tstop);
    u64 *dmax_ptr  = cross_layer_params.lookup(&idx_dmax);

    if (!rho_ptr || !kevt_ptr || !sigma_ptr || !xi_ptr ||
        !mu_ptr || !tstop_ptr || !dmax_ptr) {
        return TC_ACT_OK;
    }

    /* Trigger Absolute Physical Veto when rho >= 1.0 (scaled >= 100) */
    if (*rho_ptr >= 100) {
        u8 pass_act = ACT_PASS;
        frag_track_map.update(&fkey, &pass_act, BPF_ANY);
        return TC_ACT_OK;
    }

    /* Stage 3 & 4: Lock-free Elapsed Wait Time & Fixed-Point EVT Bound (Eq. 19) */
    u64 now_ns = bpf_ktime_get_ns();
    u64 prev_ready_ns = *base_ts_ptr;
    u64 t_wait_ns = 0;

    if (prev_ready_ns > 0 && now_ns > prev_ready_ns) {
        t_wait_ns = now_ns - prev_ready_ns;
    }
    /* Update rolling baseline timestamp for lock-free residency tracking */
    state_map.update(&idx_base_ts, &now_ns, BPF_ANY);

    u64 d_max_ns  = *dmax_ptr;
    u64 t_stop_ns = *tstop_ptr;
    u64 mu_ns     = *mu_ptr;
    u64 delta_d_ns = (d_max_ns > t_wait_ns) ? (d_max_ns - t_wait_ns) : 0;

    /* Evaluate binary decision a_k(t) in 64-bit fixed-point space (Q = 16) */
    u8 a_k = ACT_PASS;
    if (t_wait_ns >= t_stop_ns) {
        a_k = ACT_DROP; /* Kinematic stop-loss ceiling breached */
    } else if (t_wait_ns >= mu_ns) {
        u64 excess_us = (t_wait_ns - mu_ns) / 1000;
        u64 delta_d_us = delta_d_ns / 1000;
        u64 term_linear_q16 = *sigma_ptr + ((*xi_ptr * excess_us) >> 16);
        u64 evt_bound_q16 = (*kevt_ptr * term_linear_q16) >> 16;

        if ((delta_d_us << 16) <= evt_bound_q16) {
            a_k = ACT_DROP; /* Fixed-point EVT bound triggered */
        }
    }

    if (a_k == ACT_DROP) {
        u8 drop_act = ACT_DROP;
        frag_track_map.update(&fkey, &drop_act, BPF_ANY);

        /* Clone sk_buff to synthesize lightweight RTPS GAP Token */
        int ret = bpf_clone_redirect(skb, skb->ifindex, BPF_F_INGRESS);
        if (ret == 0) {
            int submsg_offset = payload_offset + 20; /* Skip 20B RTPS Header */
            __be16 old_submsg = 0;

            if (bpf_skb_load_bytes(skb, submsg_offset, &old_submsg, sizeof(old_submsg)) == 0) {
                __be16 new_submsg = old_submsg;
                /* Mutate Submessage ID to GAP (0x08) with Little-Endian Flags (0x03) */
                ((char *)&new_submsg)[0] = 0x08;
                ((char *)&new_submsg)[1] = 0x03;

                bpf_skb_store_bytes(skb, submsg_offset, &new_submsg, sizeof(new_submsg), 0);

                int l4_csum_off = sizeof(*eth) + sizeof(*ip) + offsetof(struct udphdr, check);
                bpf_l4_csum_replace(skb, l4_csum_off, old_submsg, new_submsg, sizeof(new_submsg));
            }

            /* Clear IP_MF flag on cloned token so it bypasses IP defragmentation */
            if (frag_off & IP_MF_FLAG) {
                __be16 old_frag = bpf_htons(frag_off);
                __be16 new_frag = bpf_htons(frag_off & ~IP_MF_FLAG);
                int frag_off_offset = sizeof(*eth) + offsetof(struct iphdr, frag_off);
                int l3_csum_off = sizeof(*eth) + offsetof(struct iphdr, check);
                bpf_skb_store_bytes(skb, frag_off_offset, &new_frag, sizeof(new_frag), 0);
                bpf_l3_csum_replace(skb, l3_csum_off, old_frag, new_frag, sizeof(new_frag));
            }
        }

        u64 next_drop = *n_drop_ptr + 1;
        state_map.update(&idx_ndrop, &next_drop, BPF_ANY);
        return TC_ACT_SHOT; /* Drop stale jumbo payload */
    }

    /* Healthy observation within safe waiting interval */
    u8 pass_act = ACT_PASS;
    frag_track_map.update(&fkey, &pass_act, BPF_ANY);
    u64 zero = 0;
    state_map.update(&idx_ndrop, &zero, BPF_ANY);
    return TC_ACT_OK;
}