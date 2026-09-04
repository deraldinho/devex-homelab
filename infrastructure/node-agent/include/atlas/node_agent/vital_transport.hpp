#pragma once

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>

namespace atlas::node_agent {

struct TlsCredentials {
  std::filesystem::path ca_cert;
  std::filesystem::path certificate;
  std::filesystem::path private_key;
};

struct VitalClientConfig {
  std::string host;
  std::uint16_t port;
  std::size_t max_frame_bytes;
  std::chrono::milliseconds timeout;
  std::string expected_server_name{"atlas-server"};
};

struct VitalServerConfig {
  std::string bind_host;
  std::uint16_t port;
  std::size_t max_frame_bytes;
  std::chrono::milliseconds timeout;
  std::string expected_peer_node_id;
};

struct VitalSendResult {
  bool ok;
  std::string reason;
};

struct VitalReceiveResult {
  bool ok;
  std::string reason;
  std::string peer_node_id;
  std::string frame;
};

class VitalClient {
 public:
  VitalClient(VitalClientConfig config, TlsCredentials credentials);
  VitalSendResult send_frame(const std::string& frame) const;

 private:
  VitalClientConfig config_;
  TlsCredentials credentials_;
};

class VitalServer {
 public:
  VitalServer(VitalServerConfig config, TlsCredentials credentials);
  VitalReceiveResult receive_once() const;

 private:
  VitalServerConfig config_;
  TlsCredentials credentials_;
};

}  // namespace atlas::node_agent
