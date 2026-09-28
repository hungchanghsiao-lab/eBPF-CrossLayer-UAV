#!/bin/bash
echo "=== 階段一：安裝 ROS 2 與底層網路環境 ==="
sudo apt update && sudo apt install -y iproute2 iputils-ping tcpdump tmux htop git build-essential clang llvm libbpf-dev linux-tools-common linux-tools-generic linux-headers-$(uname -r) bpfcc-tools software-properties-common curl gnupg2 lsb-release python3-pip
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update && sudo apt install -y ros-humble-ros-base python3-colcon-common-extensions python3-rosdep
sudo rosdep init && rosdep update
pip3 install numpy scipy pandas

echo "=== 階段二：建立 ROS 2 工作區與程式碼 ==="
mkdir -p ~/ros2_ws/src/cross_layer_test/src
cd ~/ros2_ws/src/cross_layer_test

cat << 'INNER_EOF' > package.xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>cross_layer_test</name>
  <version>0.0.1</version>
  <description>Hybrid Evaluation Testbed</description>
  <maintainer email="anonymous@example.com">Anonymous</maintainer>
  <license>Apache-2.0</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <depend>rclcpp</depend>
  <depend>sensor_msgs</depend>
  <export><build_type>ament_cmake</build_type></export>
</package>
INNER_EOF

cat << 'INNER_EOF' > CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(cross_layer_test)
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -O3)
endif()
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
add_executable(incast_publisher src/incast_publisher.cpp)
ament_target_dependencies(incast_publisher rclcpp sensor_msgs)
add_executable(ego_subscriber src/ego_subscriber.cpp)
ament_target_dependencies(ego_subscriber rclcpp sensor_msgs)
install(TARGETS incast_publisher ego_subscriber DESTINATION lib/${PROJECT_NAME})
ament_package()
INNER_EOF

cat << 'INNER_EOF' > src/incast_publisher.cpp
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
            RCLCPP_INFO(this->get_logger(), "Sent 4000B PointCloud update from %s", teammate_id.c_str());
        });
    }
private:
    rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr publisher_;
    rclcpp::TimerBase::SharedPtr timer_;
};
int main(int argc, char **argv) { rclcpp::init(argc, argv); rclcpp::spin(std::make_shared<IncastPublisher>()); rclcpp::shutdown(); return 0; }
INNER_EOF

cat << 'INNER_EOF' > src/ego_subscriber.cpp
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <fstream>
class EgoSubscriber : public rclcpp::Node {
public:
    EgoSubscriber() : Node("ego_subscriber") {
        this->declare_parameter<std::string>("qos_mode", "B1");
        std::string mode = this->get_parameter("qos_mode").as_string();
        csv_filename_ = "exp_results_" + mode + ".csv";
        csv_file_.open(csv_filename_, std::ios::out | std::ios::trunc);
        csv_file_ << "timestamp,sender,latency_ms\n";
        rclcpp::QoS qos_profile(100);
        if (mode == "B1") { qos_profile.reliable(); } 
        else if (mode == "B2") { qos_profile.reliable(); qos_profile.lifespan(rclcpp::Duration(0, 50000000)); }
        subscriber_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
            "/slam_update", qos_profile,
            [this](const sensor_msgs::msg::PointCloud2::SharedPtr msg) {
                auto now = this->now();
                double latency_ms = (now - msg->header.stamp).seconds() * 1000.0;
                csv_file_ << now.seconds() << "," << msg->header.frame_id << "," << latency_ms << "\n";
                RCLCPP_INFO(this->get_logger(), "Received from %s | Latency: %.2f ms", msg->header.frame_id.c_str(), latency_ms);
            });
    }
    ~EgoSubscriber() { if (csv_file_.is_open()) csv_file_.close(); }
private:
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr subscriber_;
    std::ofstream csv_file_;
    std::string csv_filename_;
};
int main(int argc, char **argv) { rclcpp::init(argc, argv); rclcpp::spin(std::make_shared<EgoSubscriber>()); rclcpp::shutdown(); return 0; }
INNER_EOF

echo "=== 階段三：編譯 ROS 2 套件 ==="
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select cross_layer_test
echo "✅ 長機部署與編譯全部完成！"
