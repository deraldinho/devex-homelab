#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <thread>

#include "atlas/node_agent/vital_transport.hpp"

using namespace atlas::node_agent;
using namespace std::chrono_literals;

namespace {
TlsCredentials server_creds(const std::filesystem::path& dir) {
  return {dir / "ca.crt.pem", dir / "server.crt.pem", dir / "server.key.pem"};
}
TlsCredentials client_creds(const std::filesystem::path& dir) {
  return {dir / "ca.crt.pem", dir / "client.crt.pem", dir / "client.key.pem"};
}
void require(bool value, const char* message) {
  if (!value) { std::cerr << message << '\n'; std::exit(EXIT_FAILURE); }
}
void test_mutual_tls_roundtrip(const std::filesystem::path& dir) {
  VitalServer server({"127.0.0.1", 39443, 512, 1500ms, "x99"}, server_creds(dir));
  std::optional<VitalReceiveResult> received;
  std::thread listener([&] { received = server.receive_once(); });
  std::this_thread::sleep_for(100ms);
  VitalClient client({"127.0.0.1", 39443, 512, 1500ms}, client_creds(dir));
  auto sent = client.send_frame("ATLAS/2|x99|proj|g1|1|e1|critical|down");
  listener.join();
  require(sent.ok, "mTLS client failed to send valid frame");
  require(received.has_value() && received->ok, "mTLS server rejected valid client");
  require(received->peer_node_id == "x99", "peer certificate identity was not bound");
}

void test_oversized_frame_is_rejected(const std::filesystem::path& dir) {
  VitalClient client({"127.0.0.1", 39444, 8, 100ms}, client_creds(dir));
  auto sent = client.send_frame("123456789");
  require(!sent.ok && sent.reason == "frame_too_large", "oversized vital frame was not rejected locally");
}
TlsCredentials core_creds(const std::filesystem::path& dir) {
  return {dir / "ca.crt.pem", dir / "core.crt.pem", dir / "core.key.pem"};
}

void test_peer_identity_mismatch_is_rejected(const std::filesystem::path& dir) {
  VitalServer server({"127.0.0.1", 39445, 512, 1500ms, "x99"}, server_creds(dir));
  std::optional<VitalReceiveResult> received;
  std::thread listener([&] { received = server.receive_once(); });
  std::this_thread::sleep_for(100ms);
  VitalClient client({"127.0.0.1", 39445, 512, 1500ms}, core_creds(dir));
  auto sent = client.send_frame("ATLAS/2|core|proj|g1|1|e2|critical|down");
  listener.join();
  require(sent.ok, "valid mTLS core client failed transport handshake");
  require(received.has_value() && !received->ok &&
              received->reason == "peer_identity_mismatch",
          "server accepted certificate for wrong node identity");
}

}  // namespace

int main(int argc, char** argv) {
  require(argc == 2, "expected test PKI directory");
  const std::filesystem::path dir(argv[1]);
  test_mutual_tls_roundtrip(dir);
  test_oversized_frame_is_rejected(dir);
  test_peer_identity_mismatch_is_rejected(dir);
  std::cout << "ATLAS_NODE_AGENT_VITAL_MTLS_PASS\n";
  return EXIT_SUCCESS;
}
