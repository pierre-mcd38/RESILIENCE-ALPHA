# CMakeLists.txt for JetBrains CLion + PlatformIO Integration
# Generated for PROJECT RESILIENCE-ALPHA (Workshop 2026-27 / M2)

cmake_minimum_required(VERSION 3.16)
project(esp8266_biometric_led C CXX)

set(CMAKE_CXX_STANDARD 17)

# PlatformIO integration
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

FILE(GLOB_RECURSE SRC_FILES
    "src/*.*"
    "include/*.*"
)

add_custom_target(
    PLATFORMIO_BUILD ALL
    COMMAND platformio -f -c clion run
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    SOURCES ${SRC_FILES}
)

add_custom_target(
    PLATFORMIO_UPLOAD
    COMMAND platformio -f -c clion run --target upload
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)

add_custom_target(
    PLATFORMIO_MONITOR
    COMMAND platformio -f -c clion device monitor
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)
