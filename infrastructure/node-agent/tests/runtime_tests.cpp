#include <cstdlib>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>

#include "atlas/node_agent/config.hpp"
#include "atlas/node_agent/runtime.hpp"

using namespace atlas::node_agent;

namespace {
int failures = 0;
void check(bool condition, const char* message) {
  if (!condition) { ++failures; std::cerr << "FAIL: " << message << '\n'; }
}

class FakeProbe final : public SystemProbe {
 public:
  CpuTimes read_cpu_times() override { return {100, 20}; }
  MemoryInfo read_memory() override { return {1000, 500}; }
  DiskInfo read_disk(const std::string&) override { return {2000, 1000}; }
};

AgentConfig config(std::size_t capacity = 2) {
  return AgentConfig{1, capacity, 128, ".",
      {ProjectPolicy{"proj", 32, {"servico_degradado", "recuperacao"}}}};
}
void test_config_loader_is_versioned_and_bounded() {
  const std::string path = "node-agent-test.conf";
  std::ofstream out(path);
  out << "schema_version=1\nqueue_capacity=3\nmax_message_bytes=64\ndisk_path=.\n";
  out << "project=proj|24|servico_degradado,recuperacao\n";
  out.close();
  auto loaded = load_agent_config(path);
  std::remove(path.c_str());
  check(loaded.schema_version == 1, "schema version loaded");
  check(loaded.queue_capacity == 3 && loaded.max_message_bytes == 64,
        "bounded capacities loaded");
  check(loaded.projects.size() == 1 && loaded.projects[0].max_payload_bytes == 24,
        "project policy loaded");
}

void test_runtime_validates_and_queues_events() {
  NodeAgentRuntime runtime(config(), std::make_unique<FakeProbe>());
  auto accepted = runtime.ingest_line("ATLAS/1|proj|e1|servico_degradado|warning|slow");
  check(accepted.accepted, "authorized semantic event accepted");
  auto invalid = runtime.ingest_line("ATLAS/1|proj|e2|raw_log|info|secret-ish");
  check(!invalid.accepted && invalid.reason == "unauthorized_event_type",
        "unauthorized type rejected");
  auto queued = runtime.pop_event();
  check(queued && queued->event_id == "e1", "accepted event queued for future transport");
}
void test_runtime_storm_remains_bounded_and_preserves_critical() {
  NodeAgentRuntime runtime(config(2), std::make_unique<FakeProbe>());
  runtime.ingest_line("ATLAS/1|proj|e1|servico_degradado|warning|a");
  runtime.ingest_line("ATLAS/1|proj|e2|servico_degradado|warning|b");
  auto critical = runtime.ingest_line("ATLAS/1|proj|e3|servico_degradado|critical|c");
  auto info = runtime.ingest_line("ATLAS/1|proj|e4|servico_degradado|info|d");
  check(critical.accepted && runtime.queue_size() == 2, "critical accepted without queue growth");
  check(!info.accepted, "lower priority storm event rejected when queue is stronger");
}

void test_runtime_collects_vitals_without_health_classification() {
  NodeAgentRuntime runtime(config(), std::make_unique<FakeProbe>());
  auto sample = runtime.collect_vitals("2026-09-04T21:45:00Z");
  check(sample.memory_total_bytes == 1000, "runtime exposes raw host vitals");
  check(!sample.cpu_busy_fraction.has_value(), "first CPU sample remains unknown fraction");
}

}  // namespace

int main() {
  test_config_loader_is_versioned_and_bounded();
  test_runtime_validates_and_queues_events();
  test_runtime_storm_remains_bounded_and_preserves_critical();
  test_runtime_collects_vitals_without_health_classification();
  if (failures != 0) return EXIT_FAILURE;
  std::cout << "ATLAS_NODE_AGENT_RUNTIME_PASS\n";
  return EXIT_SUCCESS;
}
