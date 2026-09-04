#include "atlas/node_agent/model.hpp"

#include <array>
#include <stdexcept>

namespace atlas::node_agent {
namespace {

std::vector<std::string> split_exact(const std::string& value, char delimiter) {
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

std::optional<Severity> parse_severity(const std::string& value) {
  if (value == "info") return Severity::info;
  if (value == "warning") return Severity::warning;
  if (value == "recovery") return Severity::recovery;
  if (value == "critical") return Severity::critical;
  return std::nullopt;
}
bool invalid_field(const std::string& value) {
  return value.empty() || value.find('|') != std::string::npos ||
         value.find('\r') != std::string::npos || value.find('\n') != std::string::npos;
}

}  // namespace

PolicySet::PolicySet(std::vector<ProjectPolicy> policies) {
  for (auto& policy : policies) {
    if (policy.project_id.empty() || policy.max_payload_bytes == 0) {
      throw std::invalid_argument("invalid project policy");
    }
    auto [it, inserted] = policies_.emplace(policy.project_id, std::move(policy));
    if (!inserted) throw std::invalid_argument("duplicate project policy");
  }
}

const ProjectPolicy* PolicySet::find(const std::string& project_id) const {
  const auto it = policies_.find(project_id);
  return it == policies_.end() ? nullptr : &it->second;
}

ParseResult parse_local_event(const std::string& line, const PolicySet& policies) {
  if (line.find('\r') != std::string::npos || line.find('\n') != std::string::npos)
    return {std::nullopt, "line_break_not_allowed"};
  auto parts = split_exact(line, '|');
  if (parts.size() != 6) return {std::nullopt, "invalid_field_count"};
  if (parts[0] != "ATLAS/1") return {std::nullopt, "unsupported_version"};
  for (std::size_t i = 1; i <= 4; ++i) {
    if (invalid_field(parts[i])) return {std::nullopt, "invalid_field"};
  }
  const auto* policy = policies.find(parts[1]);
  if (!policy) return {std::nullopt, "unknown_project"};
  if (!policy->allowed_event_types.contains(parts[3]))
    return {std::nullopt, "unauthorized_event_type"};
  auto severity = parse_severity(parts[4]);
  if (!severity) return {std::nullopt, "invalid_severity"};
  if (parts[5].size() > policy->max_payload_bytes)
    return {std::nullopt, "payload_too_large"};

  return {LocalEvent{parts[1], parts[2], parts[3], *severity, parts[5]}, ""};
}

const char* severity_name(Severity severity) {
  switch (severity) {
    case Severity::info: return "info";
    case Severity::warning: return "warning";
    case Severity::recovery: return "recovery";
    case Severity::critical: return "critical";
  }
  return "unknown";
}

}  // namespace atlas::node_agent
