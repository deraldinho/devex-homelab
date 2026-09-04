#include "atlas/node_agent/runtime.hpp"

namespace atlas::node_agent {

NodeAgentRuntime::NodeAgentRuntime(AgentConfig config, std::unique_ptr<SystemProbe> probe)
    : policies_(config.projects),
      queue_(config.queue_capacity),
      vitals_(std::move(probe), config.disk_path),
      max_message_bytes_(config.max_message_bytes) {}

IngestResult NodeAgentRuntime::ingest_line(const std::string& line) {
  if (line.size() > max_message_bytes_)
    return {false, "message_too_large", std::nullopt};
  auto parsed = parse_local_event(line, policies_);
  if (!parsed.event) return {false, parsed.error, std::nullopt};
  auto pushed = queue_.push(*parsed.event);
  return {pushed.accepted, pushed.reason, pushed.evicted_event_id};
}

std::optional<LocalEvent> NodeAgentRuntime::pop_event() {
  return queue_.pop();
}

HostVitals NodeAgentRuntime::collect_vitals(std::string captured_at) {
  return vitals_.collect(std::move(captured_at));
}
std::size_t NodeAgentRuntime::queue_size() const noexcept {
  return queue_.size();
}

std::size_t NodeAgentRuntime::max_message_bytes() const noexcept {
  return max_message_bytes_;
}

}  // namespace atlas::node_agent
