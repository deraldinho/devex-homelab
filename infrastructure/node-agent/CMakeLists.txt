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
