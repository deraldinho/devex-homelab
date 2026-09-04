#include <chrono>
#include <cstdlib>
#include <future>
#include <iostream>
#include <string>
#include <thread>

#include "atlas/node_agent/local_bridge.hpp"

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

using namespace atlas::node_agent;
using namespace std::chrono_literals;

namespace {
std::string endpoint() {
#ifdef _WIN32
  return "\\\\.\\pipe\\atlas-node-agent-test-" + std::to_string(GetCurrentProcessId());
#else
  return "/tmp/atlas-node-agent-test-" + std::to_string(getpid()) + ".sock";
#endif
}
void test_local_bridge_round_trip() {
  const auto ep = endpoint();
  auto server = make_local_bridge_server(ep, 256);
  auto future = std::async(std::launch::async, [&] { return server->receive_once(2s); });
  std::this_thread::sleep_for(50ms);
  auto sent = send_local_message(ep, "ATLAS/1|l2jtoren|e1|recuperacao|recovery|ok", 2s);
  auto received = future.get();
  const bool exact = received.message &&
      *received.message == "ATLAS/1|l2jtoren|e1|recuperacao|recovery|ok";
  if (!sent.ok || !exact) {
    std::cerr << "roundtrip sent=" << sent.ok
              << " send_error=" << sent.error
              << " recv_error=" << received.error
              << " recv=" << (received.message ? *received.message : "<none>") << '\n';
    std::exit(EXIT_FAILURE);
  }
}
void test_local_bridge_rejects_oversize_message() {
  const auto ep = endpoint() + "-oversize";
  auto server = make_local_bridge_server(ep, 16);
  auto future = std::async(std::launch::async, [&] { return server->receive_once(2s); });
  std::this_thread::sleep_for(50ms);
  auto sent = send_local_message(ep, std::string(32, 'x'), 2s);
  auto received = future.get();
  if (!sent.ok || received.message || received.error != "message_too_large") {
    std::cerr << "oversize sent=" << sent.ok
              << " send_error=" << sent.error
              << " recv_error=" << received.error << '\n';
    std::exit(EXIT_FAILURE);
  }
}

}  // namespace

int main() {
  test_local_bridge_round_trip();
  test_local_bridge_rejects_oversize_message();
  std::cout << "ATLAS_NODE_AGENT_LOCAL_BRIDGE_PASS\n";
  return EXIT_SUCCESS;
}
