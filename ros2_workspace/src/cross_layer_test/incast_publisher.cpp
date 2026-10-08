#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
using namespace std::chrono_literals;

class IncastPublisher : public rclcpp::Node {
public:
    IncastPublisher() : Node("incast_publisher") {
        this->declare_parameter<std::string>("teammate_id", "teammate_X");
        std::string teammate_id = this->get_parameter("teammate_id").as_string();
        
        rclcpp::QoS qos_profile(10);
        qos_profile.reliable();
        
        publisher_ = this->create_publisher<sensor_msgs::msg::PointCloud2>("/slam_update", qos_profile);
        timer_ = this->create_wall_timer(100ms, [this, teammate_id]() {
            auto msg = sensor_msgs::msg::PointCloud2();
            msg.header.stamp = this->now();
            msg.header.frame_id = teammate_id;
            msg.data = std::vector<uint8_t>(4000, 0xFF); 
            publisher_->publish(msg);
            
            // Commented out to prevent I/O latency and terminal overflow
            // RCLCPP_INFO(this->get_logger(), "Sent 4000B from %s", teammate_id.c_str());
        });
    }
private:
    rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr publisher_;
    rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char **argv) { 
    rclcpp::init(argc, argv); 
    rclcpp::spin(std::make_shared<IncastPublisher>()); 
    rclcpp::shutdown(); 
    return 0; 
}