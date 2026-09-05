#ifdef _WIN32

#define NOMINMAX
#include <windows.h>

#include <memory>
#include <stdexcept>

#include "atlas/node_agent/vitals.hpp"

namespace atlas::node_agent {
namespace {

std::uint64_t filetime_value(const FILETIME& value) {
  ULARGE_INTEGER result{};
  result.LowPart = value.dwLowDateTime;
  result.HighPart = value.dwHighDateTime;
  return result.QuadPart;
}

class WindowsSystemProbe final : public SystemProbe {
 public:
  CpuTimes read_cpu_times() override {
    FILETIME idle{}, kernel{}, user{};
    if (!GetSystemTimes(&idle, &kernel, &user))
      throw std::runtime_error("GetSystemTimes failed");
    return {filetime_value(kernel) + filetime_value(user), filetime_value(idle)};
  }
  MemoryInfo read_memory() override {
    MEMORYSTATUSEX status{};
    status.dwLength = sizeof(status);
    if (!GlobalMemoryStatusEx(&status))
      throw std::runtime_error("GlobalMemoryStatusEx failed");
    return {status.ullTotalPhys, status.ullAvailPhys};
  }

  DiskInfo read_disk(const std::string& path) override {
    ULARGE_INTEGER available{}, total{}, total_free{};
    if (!GetDiskFreeSpaceExA(path.c_str(), &available, &total, &total_free))
      throw std::runtime_error("GetDiskFreeSpaceEx failed");
    return {total.QuadPart, available.QuadPart};
  }
};

}  // namespace

std::unique_ptr<SystemProbe> make_native_system_probe() {
  return std::make_unique<WindowsSystemProbe>();
}

}  // namespace atlas::node_agent

#endif
