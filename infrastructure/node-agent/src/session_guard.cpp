#include "atlas/node_agent/session_guard.hpp"

#include <stdexcept>

namespace atlas::node_agent {

SessionGuard::SessionGuard(std::size_t max_sessions, std::size_t max_event_ids)
    : max_sessions_(max_sessions), max_event_ids_(max_event_ids) {
  if (max_sessions_ == 0 || max_event_ids_ == 0)
    throw std::invalid_argument("session guard bounds must be > 0");
}

SessionDecision SessionGuard::accept(
    const RemoteEnvelope& envelope,
    RemoteChannel channel) {
  (void)channel;
  if (envelope.session_generation == 0 || envelope.sequence == 0)
    return {false, "invalid_session_position"};
  if (event_ids_.contains(envelope.event_id))
    return {false, "duplicate_event_id"};

  auto it = positions_.find(envelope.node_id);
  if (it != positions_.end()) {
    if (envelope.session_generation < it->second.generation)
      return {false, "replayed_generation"};
    if (envelope.session_generation == it->second.generation &&
        envelope.sequence <= it->second.sequence)
      return {false, "replayed_sequence"};
  }

  if (it == positions_.end()) {
    if (positions_.size() == max_sessions_) {
      positions_.erase(session_order_.front());
      session_order_.pop_front();
    }
    session_order_.push_back(envelope.node_id);
    positions_.emplace(
        envelope.node_id,
        Position{envelope.session_generation, envelope.sequence});
  } else {
    it->second = Position{envelope.session_generation, envelope.sequence};
  }

  if (event_ids_.size() == max_event_ids_) {
    event_ids_.erase(event_order_.front());
    event_order_.pop_front();
  }
  event_ids_.insert(envelope.event_id);
  event_order_.push_back(envelope.event_id);
  return {true, ""};
}

std::size_t SessionGuard::tracked_sessions() const noexcept {
  return positions_.size();
}

std::size_t SessionGuard::tracked_event_ids() const noexcept {
  return event_ids_.size();
}

}  // namespace atlas::node_agent
