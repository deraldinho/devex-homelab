cmake_minimum_required(VERSION 3.25)
project(atlas_node_agent VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

add_library(atlas_node_agent_core
  src/model.cpp
  src/bounded_queue.cpp
)
target_include_directories(atlas_node_agent_core PUBLIC include)

if(BUILD_TESTING)
  add_executable(atlas-node-agent-tests tests/node_agent_tests.cpp)
  target_link_libraries(atlas-node-agent-tests PRIVATE atlas_node_agent_core)
  add_test(NAME atlas-node-agent-tests COMMAND atlas-node-agent-tests)
endif()

target_sources(atlas_node_agent_core PRIVATE src/vitals.cpp)
if(BUILD_TESTING)
  add_executable(atlas-node-agent-vitals-tests tests/vitals_tests.cpp)
  target_link_libraries(atlas-node-agent-vitals-tests PRIVATE atlas_node_agent_core)
  add_test(NAME atlas-node-agent-vitals-tests COMMAND atlas-node-agent-vitals-tests)
endif()

if(WIN32)
  target_sources(atlas_node_agent_core PRIVATE src/platform_windows.cpp)
else()
  target_sources(atlas_node_agent_core PRIVATE src/platform_linux.cpp)
endif()

if(BUILD_TESTING)
  add_executable(atlas-node-agent-native-probe-tests tests/native_probe_tests.cpp)
  target_link_libraries(atlas-node-agent-native-probe-tests PRIVATE atlas_node_agent_core)
  add_test(NAME atlas-node-agent-native-probe-tests COMMAND atlas-node-agent-native-probe-tests)
endif()
