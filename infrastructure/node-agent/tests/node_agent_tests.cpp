#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "atlas/node_agent/model.hpp"
#include "atlas/node_agent/bounded_queue.hpp"

using namespace atlas::node_agent;

namespace {
int failures = 0;

void check(bool condition, const char* message) {
  if (!condition) {
    ++failures;
    std::cerr << "FAIL: " << message << '\n';
  }
}

ProjectPolicy policy() {
  return ProjectPolicy{
      "l2jtoren", 32,
      {"pressao_cpu", "latencia_elevada", "servico_degradado",
       "servico_indisponivel", "recuperacao"}};
}
void test_parse_accepts_authorized_event() {
  PolicySet policies({policy()});
  auto result = parse_local_event(
      "ATLAS/1|l2jtoren|evt-1|servico_degradado|warning|login lento",
      policies);
  check(result.event.has_value(), "authorized event must be accepted");
  check(result.event->project_id == "l2jtoren", "project id preserved");
  check(result.event->event_id == "evt-1", "event id preserved");
  check(result.event->severity == Severity::warning, "severity parsed");
}

void test_parse_rejects_version_project_type_and_size() {
  PolicySet policies({policy()});
  check(!parse_local_event("ATLAS/2|l2jtoren|e|recuperacao|recovery|ok", policies).event,
        "unsupported version rejected");
  check(!parse_local_event("ATLAS/1|unknown|e|recuperacao|recovery|ok", policies).event,
        "unknown project rejected");
  check(!parse_local_event("ATLAS/1|l2jtoren|e|raw_log|info|ok", policies).event,
        "unauthorized event type rejected");
  std::string payload(33, 'x');
  check(!parse_local_event("ATLAS/1|l2jtoren|e|recuperacao|recovery|" + payload, policies).event,
        "oversized payload rejected");
}

void test_parse_rejects_delimiter_injection_and_empty_ids() {
  PolicySet policies({policy()});
  check(!parse_local_event("ATLAS/1|l2jtoren||recuperacao|recovery|ok", policies).event,
        "empty event id rejected");
  check(!parse_local_event("ATLAS/1|l2jtoren|e|recuperacao|recovery|ok\nextra", policies).event,
        "newline injection rejected");
}
LocalEvent event(std::string id, Severity severity) {
  return LocalEvent{"l2jtoren", std::move(id), "servico_degradado", severity, "x"};
}

void test_bounded_queue_prioritizes_critical_and_recovery() {
  BoundedPriorityQueue queue(3);
  check(queue.push(event("i1", Severity::info)).accepted, "info accepted");
  check(queue.push(event("w1", Severity::warning)).accepted, "warning accepted");
  check(queue.push(event("i2", Severity::info)).accepted, "second info accepted");
  auto critical = queue.push(event("c1", Severity::critical));
  check(critical.accepted && critical.evicted_event_id == "i1",
        "critical evicts oldest lowest priority");
  auto recovery = queue.push(event("r1", Severity::recovery));
  check(recovery.accepted && recovery.evicted_event_id == "i2",
        "recovery outranks informational event");
  check(queue.size() == 3, "queue remains bounded");
}

void test_bounded_queue_deduplicates_event_id() {
  BoundedPriorityQueue queue(2);
  check(queue.push(event("same", Severity::warning)).accepted, "first event accepted");
  auto duplicate = queue.push(event("same", Severity::critical));
  check(!duplicate.accepted && duplicate.reason == "duplicate_event_id",
        "duplicate id rejected idempotently");
  check(queue.size() == 1, "duplicate does not grow queue");
}

void test_bounded_queue_rejects_lower_priority_when_full() {
  BoundedPriorityQueue queue(2);
  queue.push(event("c1", Severity::critical));
  queue.push(event("c2", Severity::critical));
  auto result = queue.push(event("i1", Severity::info));
  check(!result.accepted && result.reason == "queue_preserves_higher_priority",
        "low priority cannot evict critical events");
  check(queue.size() == 2, "full critical queue remains bounded");
}
}  // namespace

int main() {
  test_parse_accepts_authorized_event();
  test_parse_rejects_version_project_type_and_size();
  test_parse_rejects_delimiter_injection_and_empty_ids();
  test_bounded_queue_prioritizes_critical_and_recovery();
  test_bounded_queue_deduplicates_event_id();
  test_bounded_queue_rejects_lower_priority_when_full();
  if (failures != 0) {
    std::cerr << failures << " test assertion(s) failed\n";
    return EXIT_FAILURE;
  }
  std::cout << "ATLAS_NODE_AGENT_MODEL_QUEUE_PASS\n";
  return EXIT_SUCCESS;
}

// Vitals tests are appended after the model/queue suite.
