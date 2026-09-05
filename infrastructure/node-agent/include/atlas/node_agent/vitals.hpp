#pragma once

#include <cstdint>
#include <memory>
#include <optional>
#include <string>

namespace atlas::node_agent {

struct CpuTimes {
  std::uint64_t total;
  std::uint64_t idle;
};

struct MemoryInfo {
  std::uint64_t total_bytes;
  std::uint64_t available_bytes;
};

struct DiskInfo {
  std::uint64_t total_bytes;
  std::uint64_t available_bytes;
};

struct HostVitals {
  std::string captured_at;
  std::optional<double> cpu_busy_fraction;
  std::uint64_t memory_total_bytes;
  std::uint64_t memory_available_bytes;
  std::uint64_t disk_total_bytes;
  std::uint64_t disk_available_bytes;
};

class SystemProbe {
 public:
  virtual ~SystemProbe() = default;
  virtual CpuTimes read_cpu_times() = 0;
  virtual MemoryInfo read_memory() = 0;
  virtual DiskInfo read_disk(const std::string& path) = 0;
};

class VitalsCollector {
 public:
  VitalsCollector(std::unique_ptr<SystemProbe> probe, std::string disk_path);
  HostVitals collect(std::string captured_at);

 private:
  std::unique_ptr<SystemProbe> probe_;
  std::string disk_path_;
  std::optional<CpuTimes> previous_cpu_;
};

std::unique_ptr<SystemProbe> make_native_system_probe();

}  // namespace atlas::node_agent
