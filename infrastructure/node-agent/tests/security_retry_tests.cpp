#include <chrono>
#include <cstdlib>
#include <iostream>
#include <memory>

#include "atlas/node_agent/bounded_queue.hpp"
#include "atlas/node_agent/runtime.hpp"

using namespace atlas::node_agent;
using namespace std::chrono_literals;

namespace {
class FakeProbe final : public SystemProbe {
 public:
  CpuTimes read_cpu_times() override { return {100, 20}; }
  MemoryInfo read_memory() override { return {1000, 500}; }
  DiskInfo read_disk(const std::string&) override { return {2000, 1000}; }
};

AgentConfig config() {
  return AgentConfig{1, 4, 256, ".", {
      ProjectPolicy{"proj", 64, {"recuperacao"}},
      ProjectPolicy{"other", 64, {"recuperacao"}}}};
}
void test_project_identity_is_bound_to_local_endpoint() {
  NodeAgentRuntime runtime(config(), std::make_unique<FakeProbe>());
  auto ok = runtime.ingest_line_for_project(
      "proj", "ATLAS/1|proj|e1|recuperacao|recovery|ok");
  auto spoof = runtime.ingest_line_for_project(
      "proj", "ATLAS/1|other|e2|recuperacao|recovery|ok");
  auto unknown = runtime.ingest_line_for_project(
      "missing", "ATLAS/1|proj|e3|recuperacao|recovery|ok");
  if (!ok.accepted || spoof.accepted || spoof.reason != "project_identity_mismatch" ||
      unknown.accepted || unknown.reason != "unknown_authenticated_project") {
    std::cerr << "local project identity binding failed\n";
    std::exit(EXIT_FAILURE);
  }
}

void test_retry_backoff_is_progressive_and_capped() {
  RetryPolicy policy{100ms, 1600ms};
  if (retry_delay(1, policy) != 100ms || retry_delay(2, policy) != 200ms ||
      retry_delay(5, policy) != 1600ms || retry_delay(100, policy) != 1600ms) {
    std::cerr << "retry backoff contract failed\n";
    std::exit(EXIT_FAILURE);
  }
}

}  // namespace

int main() {
  test_project_identity_is_bound_to_local_endpoint();
  test_retry_backoff_is_progressive_and_capped();
  std::cout << "ATLAS_NODE_AGENT_IDENTITY_RETRY_PASS\n";
  return EXIT_SUCCESS;
}
