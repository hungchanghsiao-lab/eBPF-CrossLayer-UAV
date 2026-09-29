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