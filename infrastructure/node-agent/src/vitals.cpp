#include "atlas/node_agent/vitals.hpp"

#include <stdexcept>

namespace atlas::node_agent {

VitalsCollector::VitalsCollector(std::unique_ptr<SystemProbe> probe, std::string disk_path)
    : probe_(std::move(probe)), disk_path_(std::move(disk_path)) {
  if (!probe_) throw std::invalid_argument("probe is required");
  if (disk_path_.empty()) throw std::invalid_argument("disk path is required");
}

HostVitals VitalsCollector::collect(std::string captured_at) {
  const CpuTimes cpu = probe_->read_cpu_times();
  const MemoryInfo memory = probe_->read_memory();
  const DiskInfo disk = probe_->read_disk(disk_path_);

  std::optional<double> busy;
  if (previous_cpu_ && cpu.total >= previous_cpu_->total && cpu.idle >= previous_cpu_->idle) {
    const auto total_delta = cpu.total - previous_cpu_->total;
    const auto idle_delta = cpu.idle - previous_cpu_->idle;
    if (total_delta > 0 && idle_delta <= total_delta) {
      busy = static_cast<double>(total_delta - idle_delta) / static_cast<double>(total_delta);
    }
  }
  previous_cpu_ = cpu;
  return HostVitals{
      std::move(captured_at), busy,
      memory.total_bytes, memory.available_bytes,
      disk.total_bytes, disk.available_bytes};
}

}  // namespace atlas::node_agent
