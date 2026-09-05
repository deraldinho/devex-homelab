#pragma once

#include <cstddef>
#include <string>
#include <vector>

#include "atlas/node_agent/model.hpp"

namespace atlas::node_agent {

struct AgentConfig {
  int schema_version;
  std::size_t queue_capacity;
  std::size_t max_message_bytes;
  std::string disk_path;
  std::vector<ProjectPolicy> projects;
};

AgentConfig load_agent_config(const std::string& path);

}  // namespace atlas::node_agent
