#pragma once

#include <cstddef>
#include <memory>
#include <optional>
#include <string>

#include "atlas/node_agent/bounded_queue.hpp"
#include "atlas/node_agent/config.hpp"
#include "atlas/node_agent/vitals.hpp"

namespace atlas::node_agent {

struct IngestResult {
  bool accepted;
  std::string reason;
  std::optional<std::string> evicted_event_id;
};

class NodeAgentRuntime {
 public:
  NodeAgentRuntime(AgentConfig config, std::unique_ptr<SystemProbe> probe);

  IngestResult ingest_line(const std::string& line);
  std::optional<LocalEvent> pop_event();
  HostVitals collect_vitals(std::string captured_at);
  std::size_t queue_size() const noexcept;
  std::size_t max_message_bytes() const noexcept;
 private:
  PolicySet policies_;
  BoundedPriorityQueue queue_;
  VitalsCollector vitals_;
  std::size_t max_message_bytes_;
};

}  // namespace atlas::node_agent
