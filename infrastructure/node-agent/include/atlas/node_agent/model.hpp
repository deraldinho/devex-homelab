#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace atlas::node_agent {

enum class Severity { info = 0, warning = 1, recovery = 2, critical = 3 };

struct LocalEvent {
  std::string project_id;
  std::string event_id;
  std::string event_type;
  Severity severity;
  std::string payload;
};

struct ProjectPolicy {
  std::string project_id;
  std::size_t max_payload_bytes;
  std::unordered_set<std::string> allowed_event_types;
};
class PolicySet {
 public:
  explicit PolicySet(std::vector<ProjectPolicy> policies);
  const ProjectPolicy* find(const std::string& project_id) const;

 private:
  std::unordered_map<std::string, ProjectPolicy> policies_;
};

struct ParseResult {
  std::optional<LocalEvent> event;
  std::string error;
};

ParseResult parse_local_event(const std::string& line, const PolicySet& policies);
const char* severity_name(Severity severity);

}  // namespace atlas::node_agent
