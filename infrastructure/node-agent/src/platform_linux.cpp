#ifndef _WIN32

#include <sys/statvfs.h>

#include <fstream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>

#include "atlas/node_agent/vitals.hpp"

namespace atlas::node_agent {
namespace {

class LinuxSystemProbe final : public SystemProbe {
 public:
  CpuTimes read_cpu_times() override {
    std::ifstream input("/proc/stat");
    std::string label;
    std::uint64_t user{}, nice{}, system{}, idle{}, iowait{}, irq{}, softirq{}, steal{};
    if (!(input >> label >> user >> nice >> system >> idle >> iowait >> irq >> softirq >> steal) || label != "cpu")
      throw std::runtime_error("cannot read /proc/stat");
    const auto total = user + nice + system + idle + iowait + irq + softirq + steal;
    return {total, idle + iowait};
  }
  MemoryInfo read_memory() override {
    std::ifstream input("/proc/meminfo");
    std::string key, unit;
    std::uint64_t value{}, total{}, available{};
    while (input >> key >> value >> unit) {
      if (key == "MemTotal:") total = value * 1024;
      if (key == "MemAvailable:") available = value * 1024;
    }
    if (total == 0) throw std::runtime_error("cannot read /proc/meminfo");
    return {total, available};
  }

  DiskInfo read_disk(const std::string& path) override {
    struct statvfs stats {};
    if (statvfs(path.c_str(), &stats) != 0)
      throw std::runtime_error("statvfs failed");
    const auto block_size = static_cast<std::uint64_t>(stats.f_frsize);
    return {block_size * stats.f_blocks, block_size * stats.f_bavail};
  }
};

}  // namespace

std::unique_ptr<SystemProbe> make_native_system_probe() {
  return std::make_unique<LinuxSystemProbe>();
}

}  // namespace atlas::node_agent

#endif
