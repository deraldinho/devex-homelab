#include <chrono>
#include <cstdlib>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>

#include "atlas/node_agent/config.hpp"
#include "atlas/node_agent/local_bridge.hpp"
#include "atlas/node_agent/runtime.hpp"
#include "atlas/node_agent/vitals.hpp"

using namespace atlas::node_agent;

namespace {
std::string utc_now() {
  const auto now = std::chrono::system_clock::now();
  const std::time_t raw = std::chrono::system_clock::to_time_t(now);
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &raw);
#else
  gmtime_r(&raw, &tm);
#endif
  std::ostringstream out;
  out << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
  return out.str();
}
int vitals_command(const std::string& disk_path) {
  VitalsCollector collector(make_native_system_probe(), disk_path);
  const auto sample = collector.collect(utc_now());
  std::cout << "ATLAS_NODE_AGENT_VITALS"
            << " captured_at=" << sample.captured_at
            << " cpu_busy=";
  if (sample.cpu_busy_fraction) std::cout << *sample.cpu_busy_fraction;
  else std::cout << "unknown";
  std::cout << " memory_total=" << sample.memory_total_bytes
            << " memory_available=" << sample.memory_available_bytes
            << " disk_total=" << sample.disk_total_bytes
            << " disk_available=" << sample.disk_available_bytes << '\n';
  return EXIT_SUCCESS;
}

int validate_command(const std::string& config_path, const std::string& line) {
  auto config = load_agent_config(config_path);
  NodeAgentRuntime runtime(config, make_native_system_probe());
  const auto result = runtime.ingest_line(line);
  std::cout << "accepted=" << (result.accepted ? "true" : "false")
            << " reason=" << result.reason;
  if (result.evicted_event_id) std::cout << " evicted=" << *result.evicted_event_id;
  std::cout << '\n';
  return result.accepted ? EXIT_SUCCESS : EXIT_FAILURE;
}
int listen_once_command(
    const std::string& config_path,
    const std::string& endpoint,
    std::chrono::milliseconds timeout) {
  auto config = load_agent_config(config_path);
  NodeAgentRuntime runtime(config, make_native_system_probe());
  auto bridge = make_local_bridge_server(endpoint, config.max_message_bytes);
  auto received = bridge->receive_once(timeout);
  if (!received.message) {
    std::cout << "accepted=false reason=ipc_" << received.error << '\n';
    return EXIT_FAILURE;
  }
  const auto result = runtime.ingest_line(*received.message);
  std::cout << "accepted=" << (result.accepted ? "true" : "false")
            << " reason=" << result.reason;
  if (result.evicted_event_id) std::cout << " evicted=" << *result.evicted_event_id;
  std::cout << '\n';
  return result.accepted ? EXIT_SUCCESS : EXIT_FAILURE;
}

void usage() {
  std::cout << "atlas-node-agent --vitals <disk-path>\n"
            << "atlas-node-agent --validate <config> <message>\n"
            << "atlas-node-agent --listen-once <config> <endpoint> <timeout-ms>\n";
}
}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc == 3 && std::string(argv[1]) == "--vitals") {
      return vitals_command(argv[2]);
    }
    if (argc == 4 && std::string(argv[1]) == "--validate") {
      return validate_command(argv[2], argv[3]);
    }
    if (argc == 5 && std::string(argv[1]) == "--listen-once") {
      const auto timeout_ms = std::stoll(argv[4]);
      if (timeout_ms <= 0) throw std::runtime_error("timeout must be > 0");
      return listen_once_command(
          argv[2], argv[3], std::chrono::milliseconds(timeout_ms));
    }
    usage();
    return argc == 1 ? EXIT_SUCCESS : 2;
  } catch (const std::exception& exc) {
    std::cerr << "atlas-node-agent error: " << exc.what() << '\n';
    return 2;
  }
}
