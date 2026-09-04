#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "atlas/node_agent/model.hpp"

namespace atlas::node_agent {

enum class RemoteChannel {
  vital_tcp,
  grpc_stream,
  https_transaction,
};

struct RemoteEnvelope {
  std::uint32_t protocol_version;
  std::string node_id;
  std::string project_id;
  std::string event_id;
  std::string event_type;
  Severity severity;
  std::uint64_t session_generation;
  std::uint64_t sequence;
  std::string occurred_at;
  std::string payload;
};

struct RemoteNodePolicy {
  std::string node_id;
  std::size_t max_payload_bytes;
  std::unordered_set<std::string> allowed_projects;
};

class RemotePolicySet {
 public:
  explicit RemotePolicySet(std::vector<RemoteNodePolicy> policies);
  const RemoteNodePolicy* find(const std::string& node_id) const;

 private:
  std::unordered_map<std::string, RemoteNodePolicy> policies_;
};

struct RemoteValidationResult {
  bool accepted;
  std::string reason;
};

RemoteValidationResult validate_remote_envelope(
    const RemoteEnvelope& envelope,
    const RemotePolicySet& policies,
    const std::string& authenticated_node_id);

}  // namespace atlas::node_agent
