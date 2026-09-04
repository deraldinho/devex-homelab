#pragma once

#include <chrono>
#include <cstddef>
#include <deque>
#include <optional>
#include <string>
#include <unordered_set>

#include "atlas/node_agent/model.hpp"

namespace atlas::node_agent {

struct QueuePushResult {
  bool accepted;
  std::optional<std::string> evicted_event_id;
  std::string reason;
};

struct QueueMetrics {
  std::size_t accepted{};
  std::size_t dropped{};
  std::size_t deduplicated{};
};

struct RetryPolicy {
  std::chrono::milliseconds initial_delay;
  std::chrono::milliseconds max_delay;
};

std::chrono::milliseconds retry_delay(std::size_t failure_count, RetryPolicy policy);

class BoundedPriorityQueue {
 public:
  explicit BoundedPriorityQueue(std::size_t capacity);
  QueuePushResult push(const LocalEvent& event);
  std::optional<LocalEvent> pop();
  std::size_t size() const noexcept;
  std::size_t capacity() const noexcept;
  QueueMetrics metrics() const noexcept;

 private:
  std::size_t capacity_;
  std::deque<LocalEvent> queue_;
  std::unordered_set<std::string> queued_ids_;
  QueueMetrics metrics_;
};

}  // namespace atlas::node_agent
