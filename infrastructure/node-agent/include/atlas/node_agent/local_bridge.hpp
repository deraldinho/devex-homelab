#pragma once

#include <chrono>
#include <cstddef>
#include <memory>
#include <optional>
#include <string>

namespace atlas::node_agent {

struct ReceiveResult {
  std::optional<std::string> message;
  std::string error;
};

struct SendResult {
  bool ok;
  std::string error;
};

class LocalBridgeServer {
 public:
  virtual ~LocalBridgeServer() = default;
  virtual ReceiveResult receive_once(std::chrono::milliseconds timeout) = 0;
  virtual const std::string& endpoint() const noexcept = 0;
};
std::unique_ptr<LocalBridgeServer> make_local_bridge_server(
    std::string endpoint, std::size_t max_message_bytes);

SendResult send_local_message(
    const std::string& endpoint,
    const std::string& message,
    std::chrono::milliseconds timeout);

}  // namespace atlas::node_agent
