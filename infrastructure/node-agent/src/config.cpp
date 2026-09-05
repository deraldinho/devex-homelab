#include "atlas/node_agent/config.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

namespace atlas::node_agent {
namespace {

std::vector<std::string> split(const std::string& value, char delimiter) {
  std::vector<std::string> parts;
  std::size_t start = 0;
  while (true) {
    const auto pos = value.find(delimiter, start);
    if (pos == std::string::npos) {
      parts.push_back(value.substr(start));
      break;
    }
    parts.push_back(value.substr(start, pos - start));
    start = pos + 1;
  }
  return parts;
}

std::size_t parse_size(const std::string& value, const char* name) {
  if (value.empty()) throw std::runtime_error(std::string(name) + " is empty");
  std::size_t consumed = 0;
  const auto parsed = std::stoull(value, &consumed);
  if (consumed != value.size() || parsed == 0) throw std::runtime_error(std::string(name) + " invalid");
  return static_cast<std::size_t>(parsed);
}
ProjectPolicy parse_project(const std::string& value) {
  const auto parts = split(value, '|');
  if (parts.size() != 3 || parts[0].empty()) throw std::runtime_error("invalid project policy");
  std::unordered_set<std::string> types;
  for (const auto& type : split(parts[2], ',')) {
    if (type.empty()) throw std::runtime_error("empty event type");
    types.insert(type);
  }
  if (types.empty()) throw std::runtime_error("project must allow at least one event type");
  return ProjectPolicy{parts[0], parse_size(parts[1], "project max payload"), std::move(types)};
}

}  // namespace

AgentConfig load_agent_config(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open agent config");

  AgentConfig config{0, 0, 0, {}, {}};
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') continue;
    const auto pos = line.find('=');
    if (pos == std::string::npos) throw std::runtime_error("invalid config line");
    const auto key = line.substr(0, pos);
    const auto value = line.substr(pos + 1);
    if (key == "schema_version") config.schema_version = static_cast<int>(parse_size(value, "schema_version"));
    else if (key == "queue_capacity") config.queue_capacity = parse_size(value, "queue_capacity");
    else if (key == "max_message_bytes") config.max_message_bytes = parse_size(value, "max_message_bytes");
    else if (key == "disk_path") config.disk_path = value;
    else if (key == "project") config.projects.push_back(parse_project(value));
    else throw std::runtime_error("unknown config key: " + key);
  }

  if (config.schema_version != 1) throw std::runtime_error("schema_version must be 1");
  if (config.queue_capacity == 0 || config.max_message_bytes == 0)
    throw std::runtime_error("bounded capacities are required");
  if (config.disk_path.empty()) throw std::runtime_error("disk_path is required");
  PolicySet validate_duplicates(config.projects);
  (void)validate_duplicates;
  return config;
}

}  // namespace atlas::node_agent
