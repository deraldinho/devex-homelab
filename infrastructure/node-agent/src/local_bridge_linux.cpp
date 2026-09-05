#ifndef _WIN32

#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <cerrno>
#include <chrono>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>

#include "atlas/node_agent/local_bridge.hpp"

namespace atlas::node_agent {
namespace {

sockaddr_un make_address(const std::string& endpoint) {
  if (endpoint.empty() || endpoint.size() >= sizeof(sockaddr_un::sun_path))
    throw std::invalid_argument("invalid unix socket endpoint");
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  std::memcpy(address.sun_path, endpoint.c_str(), endpoint.size() + 1);
  return address;
}
class UnixLocalBridge final : public LocalBridgeServer {
 public:
  UnixLocalBridge(std::string endpoint, std::size_t max_message_bytes)
      : endpoint_(std::move(endpoint)), max_message_bytes_(max_message_bytes) {
    if (max_message_bytes_ == 0) throw std::invalid_argument("max_message_bytes must be > 0");
    fd_ = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd_ < 0) throw std::runtime_error("socket failed");
    unlink(endpoint_.c_str());
    auto address = make_address(endpoint_);
    if (bind(fd_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0 || listen(fd_, 4) != 0) {
      close(fd_);
      unlink(endpoint_.c_str());
      throw std::runtime_error("bind/listen failed");
    }
  }

  ~UnixLocalBridge() override {
    if (fd_ >= 0) close(fd_);
    unlink(endpoint_.c_str());
  }

  const std::string& endpoint() const noexcept override { return endpoint_; }

  ReceiveResult receive_once(std::chrono::milliseconds timeout) override {
    pollfd poll_state{fd_, POLLIN, 0};
    const int ready = poll(&poll_state, 1, static_cast<int>(timeout.count()));
    if (ready == 0) return {std::nullopt, "timeout"};
    if (ready < 0) return {std::nullopt, "poll_failed"};

    const int client = accept(fd_, nullptr, nullptr);
    if (client < 0) return {std::nullopt, "accept_failed"};
    std::vector<char> buffer(max_message_bytes_ + 1);
    const auto count = recv(client, buffer.data(), buffer.size(), 0);
    close(client);
    if (count < 0) return {std::nullopt, "read_failed"};
    if (static_cast<std::size_t>(count) > max_message_bytes_)
      return {std::nullopt, "message_too_large"};
    return {std::string(buffer.data(), static_cast<std::size_t>(count)), ""};
  }

 private:
  std::string endpoint_;
  std::size_t max_message_bytes_;
  int fd_{-1};
};

}  // namespace
std::unique_ptr<LocalBridgeServer> make_local_bridge_server(
    std::string endpoint, std::size_t max_message_bytes) {
  return std::make_unique<UnixLocalBridge>(std::move(endpoint), max_message_bytes);
}

SendResult send_local_message(
    const std::string& endpoint,
    const std::string& message,
    std::chrono::milliseconds timeout) {
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  int fd = -1;
  auto address = make_address(endpoint);
  while (std::chrono::steady_clock::now() < deadline) {
    fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return {false, "socket_failed"};
    if (connect(fd, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == 0) break;
    const int error = errno;
    close(fd);
    fd = -1;
    if (error != ENOENT && error != ECONNREFUSED) return {false, "connect_failed"};
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  if (fd < 0) return {false, "timeout"};

  const auto written = send(fd, message.data(), message.size(), 0);
  close(fd);
  if (written < 0 || static_cast<std::size_t>(written) != message.size())
    return {false, "write_failed"};
  return {true, ""};
}

}  // namespace atlas::node_agent

#endif
