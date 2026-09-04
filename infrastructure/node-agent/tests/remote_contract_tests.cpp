#include <cstdlib>
#include <iostream>
#include <string>

#include "atlas/node_agent/remote_envelope.hpp"
#include "atlas/node_agent/session_guard.hpp"

using namespace atlas::node_agent;

namespace {
int failures = 0;

void expect(bool condition, const char* message) {
  if (!condition) {
    std::cerr << message << '\n';
    ++failures;
  }
}

RemotePolicySet policies() {
  return RemotePolicySet({
      RemoteNodePolicy{"x99", 64, {"proj-a", "proj-b"}},
      RemoteNodePolicy{"core", 64, {"proj-core"}},
  });
}

RemoteEnvelope envelope(std::string event_id, std::uint64_t generation,
                        std::uint64_t sequence) {
  return RemoteEnvelope{1, "x99", "proj-a", std::move(event_id),
                        "recuperacao", Severity::recovery, generation,
                        sequence, "2026-09-04T22:30:00Z", "ok"};
}
void test_identity_and_bounds() {
  auto policy = policies();
  auto valid = validate_remote_envelope(envelope("e1", 1, 1), policy, "x99");
  expect(valid.accepted, "authorized node/project should pass");

  auto spoof_node = validate_remote_envelope(envelope("e2", 1, 2), policy, "core");
  expect(!spoof_node.accepted && spoof_node.reason == "node_identity_mismatch",
         "authenticated node must match envelope node");

  auto wrong_project = envelope("e3", 1, 3);
  wrong_project.project_id = "proj-core";
  auto project_result = validate_remote_envelope(wrong_project, policy, "x99");
  expect(!project_result.accepted && project_result.reason == "unauthorized_project",
         "node must not represent foreign project");

  auto oversized = envelope("e4", 1, 4);
  oversized.payload = std::string(65, 'x');
  auto size_result = validate_remote_envelope(oversized, policy, "x99");
  expect(!size_result.accepted && size_result.reason == "payload_too_large",
         "payload must be bounded by node policy");
}

void test_session_replay_and_cross_channel_dedupe() {
  SessionGuard guard(4, 8);
  auto first = guard.accept(envelope("same", 7, 10), RemoteChannel::vital_tcp);
  expect(first.accepted, "first event should pass");

  auto duplicate = guard.accept(envelope("same", 7, 11), RemoteChannel::grpc_stream);
  expect(!duplicate.accepted && duplicate.reason == "duplicate_event_id",
         "same event across channels must deduplicate");

  auto replay_sequence = guard.accept(envelope("e12", 7, 10), RemoteChannel::vital_tcp);
  expect(!replay_sequence.accepted && replay_sequence.reason == "replayed_sequence",
         "sequence must increase within a generation");

  auto older_generation = guard.accept(envelope("e13", 6, 99), RemoteChannel::https_transaction);
  expect(!older_generation.accepted && older_generation.reason == "replayed_generation",
         "older generation must be rejected");

  auto newer_generation = guard.accept(envelope("e14", 8, 1), RemoteChannel::grpc_stream);
  expect(newer_generation.accepted, "newer generation may restart sequence");
}

}  // namespace

int main() {
  test_identity_and_bounds();
  test_session_replay_and_cross_channel_dedupe();
  if (failures != 0) return EXIT_FAILURE;
  std::cout << "ATLAS_NODE_AGENT_REMOTE_CONTRACT_PASS\n";
  return EXIT_SUCCESS;
}
