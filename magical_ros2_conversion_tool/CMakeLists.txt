cmake_minimum_required(VERSION 2.8.3)
project(magical_ros2_conversion_tool)

find_package(catkin REQUIRED
    COMPONENTS ros_introspection roscompile tf2_ros
)
catkin_python_setup()

catkin_package(
    CATKIN_DEPENDS ros_introspection roscompile tf2_ros
)

catkin_install_python(
    PROGRAMS scripts/ros2_conversion
    DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)