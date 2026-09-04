#include "atlas/node_agent/bounded_queue.hpp"

#include <algorithm>
#include <stdexcept>

namespace atlas::node_agent {
namespace {
int priority(Severity severity) {
  return static_cast<int>(severity);
}
}  // namespace

BoundedPriorityQueue::BoundedPriorityQueue(std::size_t capacity)
    : capacity_(capacity) {
  if (capacity_ == 0) throw std::invalid_argument("queue capacity must be > 0");
}

QueuePushResult BoundedPriorityQueue::push(const LocalEvent& event) {
  if (queued_ids_.contains(event.event_id)) {
    ++metrics_.deduplicated;
    return {false, std::nullopt, "duplicate_event_id"};
  }
  if (queue_.size() < capacity_) {
    queue_.push_back(event);
    queued_ids_.insert(event.event_id);
    ++metrics_.accepted;
    return {true, std::nullopt, ""};
  }
  auto lowest = queue_.begin();
  for (auto it = queue_.begin(); it != queue_.end(); ++it) {
    if (priority(it->severity) < priority(lowest->severity)) lowest = it;
  }
  if (priority(event.severity) <= priority(lowest->severity)) {
    ++metrics_.dropped;
    return {false, std::nullopt, "queue_preserves_higher_priority"};
  }

  const std::string evicted = lowest->event_id;
  queued_ids_.erase(lowest->event_id);
  queue_.erase(lowest);
  queue_.push_back(event);
  queued_ids_.insert(event.event_id);
  ++metrics_.accepted;
  ++metrics_.dropped;
  return {true, evicted, "evicted_lower_priority"};
}

std::optional<LocalEvent> BoundedPriorityQueue::pop() {
  if (queue_.empty()) return std::nullopt;
  LocalEvent result = queue_.front();
  queue_.pop_front();
  queued_ids_.erase(result.event_id);
  return result;
}
std::size_t BoundedPriorityQueue::size() const noexcept { return queue_.size(); }
std::size_t BoundedPriorityQueue::capacity() const noexcept { return capacity_; }
QueueMetrics BoundedPriorityQueue::metrics() const noexcept { return metrics_; }

}  // namespace atlas::node_agent
