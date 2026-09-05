#include <cstdlib>
#include <iostream>

#include "atlas/node_agent/vitals.hpp"

using namespace atlas::node_agent;

int main() {
  auto probe = make_native_system_probe();
  auto cpu = probe->read_cpu_times();
  auto memory = probe->read_memory();
#ifdef _WIN32
  auto disk = probe->read_disk("C:\\");
#else
  auto disk = probe->read_disk("/");
#endif
  if (cpu.total < cpu.idle || memory.total_bytes == 0 || disk.total_bytes == 0) {
    std::cerr << "invalid native vitals\n";
    return EXIT_FAILURE;
  }
  std::cout << "ATLAS_NODE_AGENT_NATIVE_VITALS_PASS\n";
  return EXIT_SUCCESS;
}
