#pragma once

#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>
#include <unordered_map>
#include <unordered_set>

#include "atlas/node_agent/remote_envelope.hpp"

namespace atlas::node_agent {

struct SessionDecision {
  bool accepted;
  std::string reason;
};

class SessionGuard {
 public:
  SessionGuard(std::size_t max_sessions, std::size_t max_event_ids);
  SessionDecision accept(const RemoteEnvelope& envelope, RemoteChannel channel);
  std::size_t tracked_sessions() const noexcept;
  std::size_t tracked_event_ids() const noexcept;

 private:
  struct Position {
    std::uint64_t generation;
    std::uint64_t sequence;
  };

  std::size_t max_sessions_;
  std::size_t max_event_ids_;
  std::unordered_map<std::string, Position> positions_;
  std::deque<std::string> session_order_;
  std::unordered_set<std::string> event_ids_;
  std::deque<std::string> event_order_;
};

}  // namespace atlas::node_agent
