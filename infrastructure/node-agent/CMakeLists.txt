cmake_minimum_required(VERSION 3.25)
project(atlas_node_agent VERSION 0.1.0 LANGUAGES CXX)

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

find_package(Threads REQUIRED)
if(WIN32)
  target_sources(atlas_node_agent_core PRIVATE src/local_bridge_windows.cpp)
else()
  target_sources(atlas_node_agent_core PRIVATE src/local_bridge_linux.cpp)
endif()

if(BUILD_TESTING)
  add_executable(atlas-node-agent-bridge-tests tests/bridge_tests.cpp)
  target_link_libraries(atlas-node-agent-bridge-tests PRIVATE atlas_node_agent_core Threads::Threads)
  add_test(NAME atlas-node-agent-bridge-tests COMMAND atlas-node-agent-bridge-tests)
endif()

target_sources(atlas_node_agent_core PRIVATE src/config.cpp src/runtime.cpp)
if(BUILD_TESTING)
  add_executable(atlas-node-agent-runtime-tests tests/runtime_tests.cpp)
  target_link_libraries(atlas-node-agent-runtime-tests PRIVATE atlas_node_agent_core)
  add_test(NAME atlas-node-agent-runtime-tests COMMAND atlas-node-agent-runtime-tests)
endif()

add_executable(atlas-node-agent src/main.cpp)
target_link_libraries(atlas-node-agent PRIVATE atlas_node_agent_core)

if(BUILD_TESTING)
  add_test(NAME atlas-node-agent-cli-vitals COMMAND atlas-node-agent --vitals .)
  set_tests_properties(atlas-node-agent-cli-vitals PROPERTIES PASS_REGULAR_EXPRESSION "ATLAS_NODE_AGENT_VITALS")
  add_test(NAME atlas-node-agent-cli-validate COMMAND atlas-node-agent --validate
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/agent.conf"
    "ATLAS/1|proj|e1|recuperacao|recovery|ok")
  set_tests_properties(atlas-node-agent-cli-validate PROPERTIES PASS_REGULAR_EXPRESSION "accepted=true")
endif()

if(BUILD_TESTING)
  add_executable(atlas-node-agent-security-retry-tests tests/security_retry_tests.cpp)
  target_link_libraries(atlas-node-agent-security-retry-tests PRIVATE atlas_node_agent_core)
  add_test(NAME atlas-node-agent-security-retry-tests COMMAND atlas-node-agent-security-retry-tests)
endif()

install(TARGETS atlas-node-agent RUNTIME DESTINATION bin)
install(FILES config/agent.conf.example DESTINATION share/atlas-node-agent)

if(BUILD_TESTING)
  add_executable(atlas-node-agent-remote-contract-tests tests/remote_contract_tests.cpp)
  target_link_libraries(atlas-node-agent-remote-contract-tests PRIVATE atlas_node_agent_core)
  add_test(NAME atlas-node-agent-remote-contract-tests COMMAND atlas-node-agent-remote-contract-tests)
endif()

target_sources(atlas_node_agent_core PRIVATE
  src/remote_envelope.cpp
  src/session_guard.cpp
)

if(BUILD_TESTING)
  add_executable(atlas-node-agent-vital-transport-tests tests/vital_transport_tests.cpp)
  target_link_libraries(atlas-node-agent-vital-transport-tests PRIVATE atlas_node_agent_core Threads::Threads)
endif()

include(FetchContent)
set(ENABLE_PROGRAMS OFF CACHE BOOL "" FORCE)
set(ENABLE_TESTING OFF CACHE BOOL "" FORCE)
set(MBEDTLS_FATAL_WARNINGS OFF CACHE BOOL "" FORCE)
FetchContent_Declare(mbedtls
  URL https://github.com/Mbed-TLS/mbedtls/releases/download/mbedtls-3.6.7/mbedtls-3.6.7.tar.bz2
  URL_HASH SHA256=a7e8bcbec0e6f761b4af24f25677626b35f762f68eef79c08677a363212d11f6
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(mbedtls)

target_sources(atlas_node_agent_core PRIVATE src/vital_transport.cpp)
target_link_libraries(atlas_node_agent_core PRIVATE mbedtls mbedx509 mbedcrypto)

if(BUILD_TESTING)
  find_program(ATLAS_TEST_OPENSSL NAMES openssl openssl.exe
    HINTS "C:/Program Files/Git/usr/bin" "C:/Program Files (x86)/Git/usr/bin")
  if(NOT ATLAS_TEST_OPENSSL)
    message(FATAL_ERROR "OpenSSL executable is required to generate ephemeral mTLS test credentials")
  endif()
  set(ATLAS_TEST_PKI_DIR "${CMAKE_CURRENT_BINARY_DIR}/atlas-test-pki")
  add_test(NAME atlas-node-agent-generate-test-pki
    COMMAND ${CMAKE_COMMAND}
      -DOPENSSL_EXECUTABLE=${ATLAS_TEST_OPENSSL}
      -DOUT_DIR=${ATLAS_TEST_PKI_DIR}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/generate_test_pki.cmake)
  set_tests_properties(atlas-node-agent-generate-test-pki PROPERTIES FIXTURES_SETUP atlas_test_pki)
  add_test(NAME atlas-node-agent-vital-transport-tests
    COMMAND atlas-node-agent-vital-transport-tests ${ATLAS_TEST_PKI_DIR})
  set_tests_properties(atlas-node-agent-vital-transport-tests PROPERTIES FIXTURES_REQUIRED atlas_test_pki)
endif()

option(ATLAS_ENABLE_GRPC "Build gRPC transport" ON)
if(ATLAS_ENABLE_GRPC)
if(BUILD_TESTING)
  add_executable(atlas-node-agent-grpc-stream-tests tests/grpc_stream_tests.cpp)
  target_link_libraries(atlas-node-agent-grpc-stream-tests PRIVATE atlas_node_agent_core Threads::Threads)
endif()

find_package(Protobuf CONFIG REQUIRED)
find_package(gRPC CONFIG REQUIRED)

set(ATLAS_GRPC_GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${ATLAS_GRPC_GEN_DIR}")
set(ATLAS_GRPC_PROTO "${CMAKE_CURRENT_SOURCE_DIR}/proto/atlas_transport.proto")
add_custom_command(
  OUTPUT
    "${ATLAS_GRPC_GEN_DIR}/atlas_transport.pb.cc"
    "${ATLAS_GRPC_GEN_DIR}/atlas_transport.pb.h"
    "${ATLAS_GRPC_GEN_DIR}/atlas_transport.grpc.pb.cc"
    "${ATLAS_GRPC_GEN_DIR}/atlas_transport.grpc.pb.h"
  COMMAND $<TARGET_FILE:protobuf::protoc>
  ARGS
    --cpp_out=${ATLAS_GRPC_GEN_DIR}
    --grpc_out=${ATLAS_GRPC_GEN_DIR}
    -I ${CMAKE_CURRENT_SOURCE_DIR}/proto
    --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>
    ${ATLAS_GRPC_PROTO}
  DEPENDS ${ATLAS_GRPC_PROTO} protobuf::protoc gRPC::grpc_cpp_plugin
  VERBATIM)

add_library(atlas_node_agent_grpc_proto
  "${ATLAS_GRPC_GEN_DIR}/atlas_transport.pb.cc"
  "${ATLAS_GRPC_GEN_DIR}/atlas_transport.grpc.pb.cc")
target_include_directories(atlas_node_agent_grpc_proto PUBLIC "${ATLAS_GRPC_GEN_DIR}")
target_link_libraries(atlas_node_agent_grpc_proto PUBLIC gRPC::grpc++ protobuf::libprotobuf)
add_library(atlas_node_agent_grpc_transport src/grpc_stream_transport.cpp)
target_include_directories(atlas_node_agent_grpc_transport PUBLIC include)
target_link_libraries(atlas_node_agent_grpc_transport
  PUBLIC atlas_node_agent_core atlas_node_agent_grpc_proto gRPC::grpc++)

if(BUILD_TESTING)
  target_link_libraries(atlas-node-agent-grpc-stream-tests PRIVATE atlas_node_agent_grpc_transport)
  add_test(NAME atlas-node-agent-grpc-stream-tests
    COMMAND atlas-node-agent-grpc-stream-tests ${ATLAS_TEST_PKI_DIR})
  set_tests_properties(atlas-node-agent-grpc-stream-tests PROPERTIES FIXTURES_REQUIRED atlas_test_pki)
endif()
endif()
