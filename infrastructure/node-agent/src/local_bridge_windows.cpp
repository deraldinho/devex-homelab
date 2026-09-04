#ifdef _WIN32

#define NOMINMAX
#include <windows.h>

#include <chrono>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>

#include "atlas/node_agent/local_bridge.hpp"

namespace atlas::node_agent {
namespace {

DWORD remaining_ms(std::chrono::steady_clock::time_point deadline) {
  const auto now = std::chrono::steady_clock::now();
  if (now >= deadline) return 0;
  const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(deadline - now).count();
  return static_cast<DWORD>(ms > MAXDWORD ? MAXDWORD : ms);
}

class WindowsLocalBridge final : public LocalBridgeServer {
 public:
  WindowsLocalBridge(std::string endpoint, std::size_t max_message_bytes)
      : endpoint_(std::move(endpoint)), max_message_bytes_(max_message_bytes) {
    if (endpoint_.rfind("\\\\.\\pipe\\", 0) != 0 || max_message_bytes_ == 0)
      throw std::invalid_argument("invalid named pipe configuration");
  }

  const std::string& endpoint() const noexcept override { return endpoint_; }

  ReceiveResult receive_once(std::chrono::milliseconds timeout) override {
    HANDLE pipe = CreateNamedPipeA(
        endpoint_.c_str(), PIPE_ACCESS_INBOUND | FILE_FLAG_OVERLAPPED,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        1, static_cast<DWORD>(max_message_bytes_ + 1),
        static_cast<DWORD>(max_message_bytes_ + 1), 0, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) return {std::nullopt, "pipe_create_failed"};

    const auto deadline = std::chrono::steady_clock::now() + timeout;
    OVERLAPPED connect_ov{};
    connect_ov.hEvent = CreateEventA(nullptr, TRUE, FALSE, nullptr);
    if (!connect_ov.hEvent) {
      CloseHandle(pipe);
      return {std::nullopt, "event_create_failed"};
    }
    bool connected = false;
    if (ConnectNamedPipe(pipe, &connect_ov)) {
      connected = true;
    } else {
      const DWORD error = GetLastError();
      if (error == ERROR_PIPE_CONNECTED) {
        connected = true;
      } else if (error == ERROR_IO_PENDING) {
        const DWORD wait = WaitForSingleObject(connect_ov.hEvent, remaining_ms(deadline));
        if (wait == WAIT_OBJECT_0) {
          DWORD transferred = 0;
          connected = GetOverlappedResult(pipe, &connect_ov, &transferred, FALSE) != FALSE;
        }
      }
    }
    if (!connected) {
      CancelIoEx(pipe, &connect_ov);
      CloseHandle(connect_ov.hEvent);
      CloseHandle(pipe);
      return {std::nullopt, "timeout"};
    }
    CloseHandle(connect_ov.hEvent);

    std::vector<char> buffer(max_message_bytes_ + 1);
    OVERLAPPED read_ov{};
    read_ov.hEvent = CreateEventA(nullptr, TRUE, FALSE, nullptr);
    if (!read_ov.hEvent) {
      DisconnectNamedPipe(pipe);
      CloseHandle(pipe);
      return {std::nullopt, "event_create_failed"};
    }
    DWORD bytes_read = 0;
    BOOL read_ok = ReadFile(
        pipe, buffer.data(), static_cast<DWORD>(buffer.size()), &bytes_read, &read_ov);
    if (!read_ok && GetLastError() == ERROR_IO_PENDING) {
      const DWORD wait = WaitForSingleObject(read_ov.hEvent, remaining_ms(deadline));
      if (wait == WAIT_OBJECT_0)
        read_ok = GetOverlappedResult(pipe, &read_ov, &bytes_read, FALSE);
    }
    if (!read_ok) CancelIoEx(pipe, &read_ov);
    CloseHandle(read_ov.hEvent);
    DisconnectNamedPipe(pipe);
    CloseHandle(pipe);

    if (!read_ok) return {std::nullopt, "timeout"};
    if (bytes_read > max_message_bytes_) return {std::nullopt, "message_too_large"};
    return {std::string(buffer.data(), bytes_read), ""};
  }

 private:
  std::string endpoint_;
  std::size_t max_message_bytes_;
};

}  // namespace
std::unique_ptr<LocalBridgeServer> make_local_bridge_server(
    std::string endpoint, std::size_t max_message_bytes) {
  return std::make_unique<WindowsLocalBridge>(std::move(endpoint), max_message_bytes);
}

SendResult send_local_message(
    const std::string& endpoint,
    const std::string& message,
    std::chrono::milliseconds timeout) {
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  HANDLE pipe = INVALID_HANDLE_VALUE;
  while (std::chrono::steady_clock::now() < deadline) {
    pipe = CreateFileA(endpoint.c_str(), GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
    if (pipe != INVALID_HANDLE_VALUE) break;
    const DWORD error = GetLastError();
    if (error != ERROR_PIPE_BUSY && error != ERROR_FILE_NOT_FOUND)
      return {false, "pipe_open_failed"};
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  if (pipe == INVALID_HANDLE_VALUE) return {false, "timeout"};
  DWORD written = 0;
  const BOOL ok = WriteFile(
      pipe, message.data(), static_cast<DWORD>(message.size()), &written, nullptr);
  CloseHandle(pipe);
  if (!ok || written != message.size()) return {false, "pipe_write_failed"};
  return {true, ""};
}

}  // namespace atlas::node_agent

#endif
