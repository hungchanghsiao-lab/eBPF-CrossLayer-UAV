import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import genpareto

def calc_cvar_stats(data, percentile=95):
    """Calculate Conditional Value-at-Risk (CVaR) and its standard deviation for the tail."""
    data = np.array(data)
    threshold = np.percentile(data, percentile)
    tail = data[data > threshold]
    if len(tail) > 0:
        return np.mean(tail), np.std(tail)
    return threshold, 0.0

def main():
    # ==========================================
    # 1. Simulation Environment & Kinematic Parameters
    # ==========================================
    N_UAVs = 500
    STEPS = 60
    FRAGMENTS = 3

    D_safe = 10.0
    BASE_ERROR = 1.0
    PENALTY_DROP = 3.5
    WAIT_RATE = 0.052

    B3_STATIC_TTL = 25.0
    ABORT_THRESHOLD = D_safe * 0.95

    # B2 Application-Layer Specific Parameters
    B2_APP_TIMEOUT = 30.0  # App-layer timeout threshold to switch QoS
    B2_OVERHEAD = 2.0      # Context switch overhead for API calls (e.g., setsockopt)

    xi_values = np.linspace(0.1, 0.9, 9)

    avail_B1_rates = []
    avail_B2_rates = []
    avail_B3_rates = []
    avail_Ours_rates = []

    delays_B1_cvar = []
    delays_B2_cvar = []
    delays_B3_cvar = []
    delays_Ours_cvar = []

    # ==========================================
    # 2. Network Engine Sampling & Fragment Dependency
    # ==========================================
    xi_sample = 0.5
    samples_single = genpareto.rvs(c=xi_sample, loc=5.0, scale=10.0, size=100000, random_state=42)
    samples_frag_raw = genpareto.rvs(c=xi_sample, loc=5.0, scale=10.0, size=(FRAGMENTS, 100000), random_state=42)
    samples_fragmented = np.max(samples_frag_raw, axis=0)

    # ==========================================
    # 3. Monte Carlo & Fail-Safe Kinematic Simulation
    # ==========================================
    np.random.seed(42)
    for xi in xi_values:
        error_B1 = np.full(N_UAVs, BASE_ERROR)
        error_B2 = np.full(N_UAVs, BASE_ERROR)
        error_B3 = np.full(N_UAVs, BASE_ERROR)
        error_Ours = np.full(N_UAVs, BASE_ERROR)

        active_steps_B1 = np.zeros(N_UAVs)
        active_steps_B2 = np.zeros(N_UAVs)
        active_steps_B3 = np.zeros(N_UAVs)
        active_steps_Ours = np.zeros(N_UAVs)

        if np.isclose(xi, 0.9):
            history_B3_all = []
            history_Ours_all = []

        for step in range(STEPS):
            raw_delays = genpareto.rvs(c=xi, loc=5.0, scale=10.0, size=(FRAGMENTS, N_UAVs))
            delay_matrix = np.max(raw_delays, axis=0)

            # [Baseline 1] Native Reliable QoS (Deadlock)
            peak_B1 = np.minimum(error_B1 + (delay_matrix * WAIT_RATE)**1.5, ABORT_THRESHOLD)
            abort_B1 = peak_B1 >= ABORT_THRESHOLD
            active_steps_B1 += (~abort_B1).astype(int)
            error_B1 = np.where(abort_B1, BASE_ERROR, BASE_ERROR)
            if np.isclose(xi, 0.9) and np.any(~abort_B1):
                delays_B1_cvar.extend(delay_matrix[~abort_B1])

            # [Baseline 2] App-Layer Dynamic QoS (Trapped in User/Kernel Barrier)
            # B2 attempts to intervene upon timeout but cannot clear OS queues, 
            # suffering the full delay_matrix plus an API context switch overhead.
            b2_perceived_delay = np.where(delay_matrix > B2_APP_TIMEOUT, delay_matrix + B2_OVERHEAD, delay_matrix)
            peak_B2 = np.minimum(error_B2 + (b2_perceived_delay * WAIT_RATE)**1.5, ABORT_THRESHOLD)
            abort_B2 = peak_B2 >= ABORT_THRESHOLD
            active_steps_B2 += (~abort_B2).astype(int)
            error_B2 = np.where(abort_B2, BASE_ERROR, BASE_ERROR)
            if np.isclose(xi, 0.9) and np.any(~abort_B2):
                delays_B2_cvar.extend(b2_perceived_delay[~abort_B2])

            # [Baseline 3] Pure Network-Layer AQM (Blind Drop)
            drop_B3 = delay_matrix > B3_STATIC_TTL
            peak_B3 = np.where(drop_B3, error_B3 + PENALTY_DROP, np.minimum(error_B3 + (delay_matrix * WAIT_RATE)**1.5, ABORT_THRESHOLD))
            abort_B3 = peak_B3 >= ABORT_THRESHOLD
            active_steps_B3 += (~abort_B3).astype(int)
            error_B3 = np.where(abort_B3, BASE_ERROR, np.where(drop_B3, error_B3 + PENALTY_DROP, BASE_ERROR))
            if np.isclose(xi, 0.9) and np.any(~abort_B3):
                delays_B3_cvar.extend(np.where(drop_B3, B3_STATIC_TTL, delay_matrix)[~abort_B3])

            # [Ours] TC eBPF Cross-Layer Scheduler
            rho = np.clip(error_Ours / ABORT_THRESHOLD, 0.01, 0.99)
            gamma_drop = rho
            K_evt = np.where(xi > 1e-4, ((gamma_drop)**(-xi) - 1.0) / xi, -np.log(gamma_drop))
            dynamic_limit = 12.0 + K_evt * 18.0

            max_safe_delay = ((ABORT_THRESHOLD - error_Ours) ** (1/1.5)) / WAIT_RATE
            final_limit = np.minimum(dynamic_limit, max_safe_delay)

            veto_drop = (error_Ours + PENALTY_DROP) >= ABORT_THRESHOLD
            drop_Ours = (delay_matrix > final_limit) & (~veto_drop)

            peak_Ours = np.where(drop_Ours, error_Ours + PENALTY_DROP, np.minimum(error_Ours + (delay_matrix * WAIT_RATE)**1.5, ABORT_THRESHOLD))
            abort_Ours = peak_Ours >= ABORT_THRESHOLD
            active_steps_Ours += (~abort_Ours).astype(int)
            error_Ours = np.where(abort_Ours, BASE_ERROR, np.where(drop_Ours, error_Ours + PENALTY_DROP, BASE_ERROR))

            if np.isclose(xi, 0.9):
                if np.any(~abort_Ours):
                    delays_Ours_cvar.extend(np.where(drop_Ours, final_limit, delay_matrix)[~abort_Ours])
                history_B3_all.append(peak_B3)
                history_Ours_all.append(peak_Ours)

        if np.isclose(xi, 0.9):
            history_B3_all = np.array(history_B3_all)
            history_Ours_all = np.array(history_Ours_all)
            b3_crashes = np.sum(history_B3_all > ABORT_THRESHOLD, axis=0)
            ours_aborts = np.sum(history_Ours_all == ABORT_THRESHOLD, axis=0)
            candidates = np.where((b3_crashes > 0) & (ours_aborts > 0))[0]
            hero_id = candidates[0] if len(candidates) > 0 else 0
            history_B3 = history_B3_all[:, hero_id]
            history_Ours = history_Ours_all[:, hero_id]

        avail_B1_rates.append(np.mean(active_steps_B1 / STEPS) * 100)
        avail_B2_rates.append(np.mean(active_steps_B2 / STEPS) * 100)
        avail_B3_rates.append(np.mean(active_steps_B3 / STEPS) * 100)
        avail_Ours_rates.append(np.mean(active_steps_Ours / STEPS) * 100)

    cvar_B1, std_B1 = calc_cvar_stats(delays_B1_cvar)
    cvar_B2, std_B2 = calc_cvar_stats(delays_B2_cvar)
    cvar_B3, std_B3 = calc_cvar_stats(delays_B3_cvar)
    cvar_Ours, std_Ours = calc_cvar_stats(delays_Ours_cvar)

    # ==========================================
    # 4. Plotting & PDF Export
    # ==========================================
    plt.style.use('default')

    # -- Figure A: Network Delay CDF --
    fig0, ax0 = plt.subplots(figsize=(7, 4.5), dpi=150)
    def plot_cdf(data, ax, label, color, linestyle, linewidth):
        sorted_data = np.sort(data)
        y = np.arange(1, len(data) + 1) / len(data)
        ax.plot(sorted_data, y, label=label, color=color, linestyle=linestyle, linewidth=linewidth)

    plot_cdf(samples_single, ax0, 'Single Packet (No Frag.)', 'gray', '--', 2)
    plot_cdf(samples_fragmented, ax0, r'Fragmented Payload (3 Frags, $\max$)', 'black', '-', 2.5)
    ax0.set_xlabel('End-to-End Delay (ms)', fontsize=13)
    ax0.set_ylabel('Cumulative Probability (CDF)', fontsize=13)
    ax0.set_xlim(0, 150)
    ax0.set_ylim(0, 1.05)
    ax0.grid(True, linestyle='--', alpha=0.6)
    ax0.legend(loc='lower right', fontsize=11)
    ax0.annotate('Tail Degradation due to\nFragment Interleaving',
                 xy=(80, np.interp(80, np.sort(samples_fragmented), np.arange(1, 100001)/100000)),
                 xytext=(70, 0.6), arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=8), fontsize=11)
    plt.tight_layout()
    fig0.savefig('fig_a_network_cdf.pdf', format='pdf', bbox_inches='tight')

    # -- Figure B: Mission Availability --
    fig1, ax1 = plt.subplots(figsize=(7, 4.5), dpi=150)
    ax1.plot(xi_values, avail_B1_rates, 'r-o', linewidth=2.5, markersize=8, label='B1: Native Reliable QoS')
    ax1.plot(xi_values, avail_B2_rates, 'g:D', linewidth=2.5, markersize=7, alpha=0.8, label='B2: App-Layer QoS (HoL Blocked)')
    ax1.plot(xi_values, avail_B3_rates, 'b--^', linewidth=2.5, markersize=8, label='B3: AoI-Aware AQM')
    ax1.plot(xi_values, avail_Ours_rates, 'purple', linestyle='-', marker='s', linewidth=3.5, markersize=8, label='Ours: TC EVT Scheduler')
    ax1.set_xlabel(r'Network Heavy-Tail Interference Level ($\xi$)', fontsize=13)
    ax1.set_ylabel('Mission Availability / Non-Abort Rate (%)', fontsize=13)
    ax1.set_ylim(65, 105)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='lower left', fontsize=10)
    plt.tight_layout()
    fig1.savefig('fig_b_availability.pdf', format='pdf', bbox_inches='tight')

    # -- Figure C: Marginal Case Trajectory --
    fig2, ax2 = plt.subplots(figsize=(7, 4.5), dpi=150)
    time_steps = np.arange(20, 50)
    ax2.axhline(y=ABORT_THRESHOLD, color='red', linestyle='-', linewidth=3, alpha=0.5, label=r'Emergency Hover Limit (95% $D_{safe}$)')
    ax2.plot(time_steps, history_B3[20:50], 'b--^', linewidth=2.5, markersize=7, alpha=0.85, label=r'B3: EKF Error ($\epsilon_{pred}$)')
    ax2.plot(time_steps, history_Ours[20:50], 'purple', linestyle='-', marker='s', linewidth=2.5, markersize=7, alpha=0.9, label=r'Ours: EKF Error ($\epsilon_{pred}$)')

    ax2.set_xlabel('Simulation Time Steps', fontsize=13)
    ax2.set_ylabel(r'Prediction Error Ellipse $\epsilon_{pred}$ (m)', fontsize=13)
    ax2.set_ylim(0, 17.5)
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper left', fontsize=11)

    crash_idx = np.where(history_B3[20:50] > ABORT_THRESHOLD)[0]
    if len(crash_idx) > 0:
        c_step = time_steps[crash_idx[0]]
        c_val = history_B3[20:50][crash_idx[0]]
        ax2.annotate('Uncontrolled Crash\n(Blind Drop)', xy=(c_step, c_val), xytext=(c_step+2.5, 14.5),
                     arrowprops=dict(facecolor='red', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=0.15"),
                     fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", alpha=0.9))

    abort_idx = np.where(history_Ours[20:50] == ABORT_THRESHOLD)[0]
    if len(abort_idx) > 0:
        a_step = time_steps[abort_idx[0]]
        ax2.annotate('Fail-Safe Hover\n(Controlled)', xy=(a_step, ABORT_THRESHOLD), xytext=(a_step-12.5, 11.0),
                     arrowprops=dict(facecolor='purple', shrink=0.05, width=1.5, headwidth=8, connectionstyle="arc3,rad=-0.15"),
                     fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="purple", alpha=0.9))

    plt.tight_layout()
    fig2.savefig('fig_c_trajectory.pdf', format='pdf', bbox_inches='tight')

    # -- Figure D: CVaR Tail Risk Trade-off --
    fig3, ax3 = plt.subplots(figsize=(7, 4.5), dpi=150)
    cvars = [cvar_B1, cvar_B2, cvar_B3, cvar_Ours]
    stds = [std_B1, std_B2, std_B3, std_Ours]

    bars = ax3.bar(['B1\n(Native)', 'B2\n(App-layer)', 'B3\n(Blind-AQM)', 'Ours\n(Cross-Layer)'], cvars,
                   yerr=stds, capsize=8,
                   color=['red', 'green', 'blue', 'purple'], alpha=0.8, edgecolor='black', linewidth=1.5, width=0.6)

    ax3.set_ylabel(r'$CVaR_{95\%}$ Tail Latency (ms)', fontsize=13)
    y_max_limit = max(np.array(cvars) + np.array(stds))
    ax3.set_ylim(0, y_max_limit * 1.25)
    ax3.grid(axis='y', linestyle='--', alpha=0.6)

    for bar, std in zip(bars, stds):
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, yval + std + (y_max_limit*0.03),
                 f'{yval:.1f} ms', ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.tight_layout()
    fig3.savefig('fig_d_cvar_tradeoff.pdf', format='pdf', bbox_inches='tight')

    print("Simulation completed successfully. Plots have been saved as PDF files in the current directory.")
    
    # Display the plots if the environment supports it (e.g., local GUI)
    plt.show()

if __name__ == "__main__":
    main()