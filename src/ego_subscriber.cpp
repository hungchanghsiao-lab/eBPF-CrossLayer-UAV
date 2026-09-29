#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <fstream>

class EgoSubscriber : public rclcpp::Node {
public:
    EgoSubscriber() : Node("ego_subscriber") {
        this->declare_parameter<std::string>("qos_mode", "B1");
        std::string mode = this->get_parameter("qos_mode").as_string();
        
        csv_filename_ = "exp_results_" + mode + "_raw.txt";
        csv_file_.open(csv_filename_, std::ios::out | std::ios::trunc);
        
        rclcpp::QoS qos_profile(100);
        
        // Dynamic QoS setup based on experimental mode
        if (mode == "B2") {
            qos_profile.reliable();
            // B2 Baseline: Application-layer lifespan limited to 50ms (50,000,000 ns)
            qos_profile.lifespan(rclcpp::Duration(0, 50000000));
        } else {
            // B1 (Native) or OURS (eBPF-handled) modes use standard reliable QoS
            qos_profile.reliable();
        }
        
        subscriber_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
            "/slam_update", qos_profile,
            [this](const sensor_msgs::msg::PointCloud2::SharedPtr msg) {
                auto now = this->now();
                double latency_ms = (now - msg->header.stamp).seconds() * 1000.0;
                
                // Write directly in specific format for easier grep parsing
                csv_file_ << "Latency: " << latency_ms << " ms\n";
            });
    }
    ~EgoSubscriber() { if (csv_file_.is_open()) csv_file_.close(); }
private:
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr subscriber_;
    std::ofstream csv_file_;
    std::string csv_filename_;
};

int main(int argc, char **argv) { 
    rclcpp::init(argc, argv); 
    rclcpp::spin(std::make_shared<EgoSubscriber>()); 
    rclcpp::shutdown(); 
    return 0; 
}