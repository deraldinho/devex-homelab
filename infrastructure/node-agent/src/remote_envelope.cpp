#include "atlas/node_agent/remote_envelope.hpp"

#include <stdexcept>
#include <utility>

namespace atlas::node_agent {
namespace {

bool invalid_field(const std::string& value) {
  return value.empty() || value.find('\r') != std::string::npos ||
         value.find('\n') != std::string::npos || value.find('|') != std::string::npos;
}

}  // namespace

RemotePolicySet::RemotePolicySet(std::vector<RemoteNodePolicy> policies) {
  for (auto& policy : policies) {
    if (policy.node_id.empty() || policy.max_payload_bytes == 0 ||
        policy.allowed_projects.empty()) {
      throw std::invalid_argument("invalid remote node policy");
    }
    auto [it, inserted] = policies_.emplace(policy.node_id, std::move(policy));
    if (!inserted) throw std::invalid_argument("duplicate remote node policy");
  }
}

const RemoteNodePolicy* RemotePolicySet::find(const std::string& node_id) const {
  const auto it = policies_.find(node_id);
  return it == policies_.end() ? nullptr : &it->second;
}

RemoteValidationResult validate_remote_envelope(
    const RemoteEnvelope& envelope,
    const RemotePolicySet& policies,
    const std::string& authenticated_node_id) {
  if (envelope.protocol_version != 1) return {false, "unsupported_version"};
  if (invalid_field(envelope.node_id) || invalid_field(envelope.project_id) ||
      invalid_field(envelope.event_id) || invalid_field(envelope.event_type) ||
      invalid_field(envelope.occurred_at)) {
    return {false, "invalid_field"};
  }
  if (envelope.session_generation == 0 || envelope.sequence == 0)
    return {false, "invalid_session_position"};
  const auto* policy = policies.find(authenticated_node_id);
  if (!policy) return {false, "unknown_authenticated_node"};
  if (envelope.node_id != authenticated_node_id)
    return {false, "node_identity_mismatch"};
  if (!policy->allowed_projects.contains(envelope.project_id))
    return {false, "unauthorized_project"};
  if (envelope.payload.size() > policy->max_payload_bytes)
    return {false, "payload_too_large"};
  return {true, ""};
}

}  // namespace atlas::node_agent
