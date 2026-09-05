#pragma once

#include <chrono>
#include <cstddef>
#include <string>
#include <vector>

#include "atlas/node_agent/remote_envelope.hpp"
#include "atlas/node_agent/vital_transport.hpp"

namespace atlas::node_agent {

struct GrpcStreamClientConfig {
  std::string target;
  std::size_t max_batch_messages;
  std::size_t max_payload_bytes;
  std::chrono::milliseconds timeout;
  std::string expected_server_name;
};

struct GrpcStreamServerConfig {
  std::string bind_address;
  std::size_t max_batch_messages;
  std::size_t max_payload_bytes;
  std::chrono::milliseconds timeout;
  std::string expected_peer_node_id;
};

struct GrpcSendResult {
  bool ok;
  std::string reason;
  std::size_t accepted_messages;
};

struct GrpcReceiveResult {
  bool ok;
  std::string reason;
  std::string peer_node_id;
  std::vector<RemoteEnvelope> events;
};

class GrpcStreamClient {
 public:
  GrpcStreamClient(GrpcStreamClientConfig config, TlsCredentials credentials);
  GrpcSendResult send_batch(const std::vector<RemoteEnvelope>& events) const;

 private:
  GrpcStreamClientConfig config_;
  TlsCredentials credentials_;
};

class GrpcStreamServer {
 public:
  GrpcStreamServer(GrpcStreamServerConfig config, TlsCredentials credentials);
  GrpcReceiveResult receive_batch_once() const;

 private:
  GrpcStreamServerConfig config_;
  TlsCredentials credentials_;
};

}  // namespace atlas::node_agent
