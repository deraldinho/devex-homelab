#include <cstdlib>
#include <iostream>
#include <memory>

#include "atlas/node_agent/vitals.hpp"

using namespace atlas::node_agent;

namespace {
int failures = 0;
void check(bool condition, const char* message) {
  if (!condition) { ++failures; std::cerr << "FAIL: " << message << '\n'; }
}

class FakeProbe final : public SystemProbe {
 public:
  CpuTimes cpu{100, 40};
  MemoryInfo memory{1000, 400};
  DiskInfo disk{2000, 500};
  CpuTimes read_cpu_times() override { return cpu; }
  MemoryInfo read_memory() override { return memory; }
  DiskInfo read_disk(const std::string&) override { return disk; }
};
void test_first_sample_has_no_cpu_fraction() {
  auto probe = std::make_unique<FakeProbe>();
  VitalsCollector collector(std::move(probe), "C:\\");
  auto sample = collector.collect("2026-09-04T21:30:00Z");
  check(!sample.cpu_busy_fraction.has_value(), "first CPU sample is baseline only");
  check(sample.memory_total_bytes == 1000 && sample.memory_available_bytes == 400,
        "memory values preserved");
  check(sample.disk_total_bytes == 2000 && sample.disk_available_bytes == 500,
        "disk values preserved");
}

void test_second_sample_derives_cpu_fraction_without_thresholds() {
  auto probe = std::make_unique<FakeProbe>();
  auto* raw = probe.get();
  VitalsCollector collector(std::move(probe), "C:\\");
  collector.collect("2026-09-04T21:30:00Z");
  raw->cpu = CpuTimes{200, 70};
  auto sample = collector.collect("2026-09-04T21:30:01Z");
  check(sample.cpu_busy_fraction.has_value(), "second sample derives CPU busy fraction");
  check(*sample.cpu_busy_fraction > 0.69 && *sample.cpu_busy_fraction < 0.71,
        "CPU busy fraction is delta based");
}

void test_invalid_counter_regression_does_not_invent_cpu() {
  auto probe = std::make_unique<FakeProbe>();
  auto* raw = probe.get();
  VitalsCollector collector(std::move(probe), "/");
  collector.collect("2026-09-04T21:30:00Z");
  raw->cpu = CpuTimes{90, 30};
  auto sample = collector.collect("2026-09-04T21:30:01Z");
  check(!sample.cpu_busy_fraction.has_value(), "counter regression yields unknown CPU fraction");
}
}  // namespace

int main() {
  test_first_sample_has_no_cpu_fraction();
  test_second_sample_derives_cpu_fraction_without_thresholds();
  test_invalid_counter_regression_does_not_invent_cpu();
  if (failures != 0) return EXIT_FAILURE;
  std::cout << "ATLAS_NODE_AGENT_VITALS_PASS\n";
  return EXIT_SUCCESS;
}
