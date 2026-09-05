#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <optional>
#include <thread>
#include <vector>

#include "atlas/node_agent/grpc_stream_transport.hpp"

using namespace atlas::node_agent;
using namespace std::chrono_literals;

namespace {
void require(bool value, const char* message) {
  if (!value) { std::cerr << message << '\n'; std::exit(EXIT_FAILURE); }
}
TlsCredentials server_creds(const std::filesystem::path& dir) {
  return {dir / "ca.crt.pem", dir / "server.crt.pem", dir / "server.key.pem"};
}
TlsCredentials x99_creds(const std::filesystem::path& dir) {
  return {dir / "ca.crt.pem", dir / "client.crt.pem", dir / "client.key.pem"};
}
TlsCredentials core_creds(const std::filesystem::path& dir) {
  return {dir / "ca.crt.pem", dir / "core.crt.pem", dir / "core.key.pem"};
}
RemoteEnvelope event(std::uint64_t sequence, std::string id) {
  return RemoteEnvelope{1, "x99", "proj", std::move(id), "servico_degradado",
                        Severity::warning, 1, sequence,
                        "2026-09-04T23:00:00Z", "payload"};
}

void test_grpc_stream_roundtrip(const std::filesystem::path& dir) {
  GrpcStreamServer server({"127.0.0.1:39446", 4, 512, 2000ms, "x99"}, server_creds(dir));
  std::optional<GrpcReceiveResult> received;
  std::thread listener([&] { received = server.receive_batch_once(); });
  std::this_thread::sleep_for(250ms);

  GrpcStreamClient client({"127.0.0.1:39446", 4, 512, 2000ms, "atlas-server"}, x99_creds(dir));
  auto sent = client.send_batch({event(1, "e1"), event(2, "e2")});
  listener.join();

  require(sent.ok && sent.accepted_messages == 2, "gRPC mTLS stream send failed");
  require(received.has_value() && received->ok, "gRPC mTLS server rejected valid batch");
  require(received->peer_node_id == "x99", "gRPC peer identity mismatch");
  require(received->events.size() == 2, "gRPC stream changed batch size");
  const auto& roundtripped = received->events[1];
  require(roundtripped.protocol_version == 1, "gRPC stream changed protocol version");
  require(roundtripped.node_id == "x99", "gRPC stream changed node id");
  require(roundtripped.project_id == "proj", "gRPC stream changed project id");
  require(roundtripped.event_id == "e2", "gRPC stream changed event id/order");
  require(roundtripped.event_type == "servico_degradado", "gRPC stream dropped event type");
  require(roundtripped.severity == Severity::warning, "gRPC stream changed severity");
  require(roundtripped.session_generation == 1 && roundtripped.sequence == 2,
          "gRPC stream changed session position");
  require(roundtripped.occurred_at == "2026-09-04T23:00:00Z", "gRPC stream changed occurrence time");
  require(roundtripped.payload == "payload", "gRPC stream changed payload");
}

void test_grpc_rejects_authenticated_wrong_node(const std::filesystem::path& dir) {
  GrpcStreamServer server({"127.0.0.1:39448", 4, 512, 2000ms, "x99"}, server_creds(dir));
  std::optional<GrpcReceiveResult> received;
  std::thread listener([&] { received = server.receive_batch_once(); });
  std::this_thread::sleep_for(250ms);

  GrpcStreamClient client({"127.0.0.1:39448", 4, 512, 2000ms, "atlas-server"}, core_creds(dir));
  auto sent = client.send_batch({event(1, "e-core")});
  listener.join();

  require(!sent.ok && sent.reason == "peer_identity_mismatch",
          "gRPC must reject authenticated foreign node");
  require(received.has_value() && !received->ok &&
              received->reason == "peer_identity_mismatch",
          "server must report peer identity mismatch");
}

void test_grpc_batch_bound_is_enforced(const std::filesystem::path& dir) {
  GrpcStreamClient client({"127.0.0.1:39447", 1, 512, 100ms, "atlas-server"}, x99_creds(dir));
  auto sent = client.send_batch({event(1, "e1"), event(2, "e2")});
  require(!sent.ok && sent.reason == "batch_too_large", "gRPC batch bound was not enforced");
}

void test_grpc_server_payload_bound_is_enforced(const std::filesystem::path& dir) {
  GrpcStreamServer server({"127.0.0.1:39449", 4, 4, 2000ms, "x99"}, server_creds(dir));
  std::optional<GrpcReceiveResult> received;
  std::thread listener([&] { received = server.receive_batch_once(); });
  std::this_thread::sleep_for(250ms);

  GrpcStreamClient client({"127.0.0.1:39449", 4, 512, 2000ms, "atlas-server"}, x99_creds(dir));
  auto sent = client.send_batch({event(1, "e-payload")});
  listener.join();

  require(!sent.ok && sent.reason == "payload_too_large",
          "gRPC server payload bound was not enforced");
  require(received.has_value() && !received->ok && received->reason == "payload_too_large",
          "server must report payload bound rejection");
}

}  // namespace

int main(int argc, char** argv) {
  require(argc == 2, "expected test PKI directory");
  const std::filesystem::path dir(argv[1]);
  test_grpc_stream_roundtrip(dir);
  test_grpc_rejects_authenticated_wrong_node(dir);
  test_grpc_batch_bound_is_enforced(dir);
  test_grpc_server_payload_bound_is_enforced(dir);
  std::cout << "ATLAS_NODE_AGENT_GRPC_MTLS_PASS\n";
  return EXIT_SUCCESS;
}
