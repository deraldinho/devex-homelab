#include "atlas/node_agent/grpc_stream_transport.hpp"

#include <condition_variable>
#include <fstream>
#include <memory>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <utility>

#include <grpc/grpc_security_constants.h>
#include <grpcpp/grpcpp.h>
#include <grpcpp/security/credentials.h>
#include <grpcpp/security/server_credentials.h>

#include "atlas_transport.grpc.pb.h"

namespace atlas::node_agent {
namespace {
using ProtoEnvelope = atlas::node_agent::v1::RemoteEnvelopeMessage;
using ProtoAck = atlas::node_agent::v1::PushAck;
using ProtoService = atlas::node_agent::v1::AtlasOperational;

std::string read_text(const std::filesystem::path& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) throw std::runtime_error("cannot_read_tls_file:" + path.string());
  return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

ProtoEnvelope to_proto(const RemoteEnvelope& event) {
  ProtoEnvelope message;
  message.set_protocol_version(event.protocol_version);
  message.set_node_id(event.node_id);
  message.set_project_id(event.project_id);
  message.set_event_id(event.event_id);
  message.set_event_type(event.event_type);
  message.set_severity(static_cast<std::uint32_t>(event.severity));
  message.set_session_generation(event.session_generation);
  message.set_sequence(event.sequence);
  message.set_occurred_at(event.occurred_at);
  message.set_payload(event.payload);
  return message;
}
std::optional<RemoteEnvelope> from_proto(const ProtoEnvelope& message) {
  if (message.severity() > static_cast<std::uint32_t>(Severity::critical)) return std::nullopt;
  return RemoteEnvelope{message.protocol_version(), message.node_id(), message.project_id(),
                        message.event_id(), message.event_type(),
                        static_cast<Severity>(message.severity()),
                        message.session_generation(), message.sequence(),
                        message.occurred_at(), message.payload()};
}

std::shared_ptr<grpc::ChannelCredentials> client_credentials(const TlsCredentials& credentials) {
  grpc::SslCredentialsOptions options;
  options.pem_root_certs = read_text(credentials.ca_cert);
  options.pem_private_key = read_text(credentials.private_key);
  options.pem_cert_chain = read_text(credentials.certificate);
  return grpc::SslCredentials(options);
}

std::shared_ptr<grpc::ServerCredentials> server_credentials(const TlsCredentials& credentials) {
  grpc::SslServerCredentialsOptions options(
      GRPC_SSL_REQUEST_AND_REQUIRE_CLIENT_CERTIFICATE_AND_VERIFY);
  options.pem_root_certs = read_text(credentials.ca_cert);
  grpc::SslServerCredentialsOptions::PemKeyCertPair pair;
  pair.private_key = read_text(credentials.private_key);
  pair.cert_chain = read_text(credentials.certificate);
  options.pem_key_cert_pairs.push_back(std::move(pair));
  return grpc::SslServerCredentials(options);
}

std::string authenticated_common_name(const grpc::ServerContext& context) {
  const auto auth = context.auth_context();
  if (!auth || !auth->IsPeerAuthenticated()) return {};
  const auto values = auth->FindPropertyValues(GRPC_X509_CN_PROPERTY_NAME);
  if (values.empty()) return {};
  return std::string(values.front().data(), values.front().length());
}
class OneBatchService final : public ProtoService::Service {
 public:
  explicit OneBatchService(GrpcStreamServerConfig config) : config_(std::move(config)) {}

  grpc::Status Push(grpc::ServerContext* context,
                    grpc::ServerReader<ProtoEnvelope>* reader,
                    ProtoAck* ack) override {
    GrpcReceiveResult result{false, "", authenticated_common_name(*context), {}};
    if (result.peer_node_id != config_.expected_peer_node_id) {
      result.reason = "peer_identity_mismatch";
      ack->set_accepted(false);
      ack->set_reason(result.reason);
      publish(std::move(result));
      return grpc::Status::OK;
    }

    ProtoEnvelope message;
    while (reader->Read(&message)) {
      if (result.events.size() >= config_.max_batch_messages) {
        result.reason = "batch_too_large";
        ack->set_accepted(false);
        ack->set_reason(result.reason);
        publish(std::move(result));
        return grpc::Status::OK;
      }
      if (message.payload().size() > config_.max_payload_bytes) {
        result.reason = "payload_too_large";
        ack->set_accepted(false);
        ack->set_reason(result.reason);
        publish(std::move(result));
        return grpc::Status::OK;
      }
      if (message.node_id() != result.peer_node_id) {
        result.reason = "message_identity_mismatch";
        ack->set_accepted(false);
        ack->set_reason(result.reason);
        publish(std::move(result));
        return grpc::Status::OK;
      }
      auto event = from_proto(message);
      if (!event) {
        result.reason = "invalid_envelope";
        ack->set_accepted(false);
        ack->set_reason(result.reason);
        publish(std::move(result));
        return grpc::Status::OK;
      }
      result.events.push_back(std::move(*event));
    }
    result.ok = true;
    ack->set_accepted(true);
    ack->set_received(static_cast<std::uint32_t>(result.events.size()));
    publish(std::move(result));
    return grpc::Status::OK;
  }

  std::optional<GrpcReceiveResult> wait_for_result(std::chrono::milliseconds timeout) {
    std::unique_lock lock(mutex_);
    if (!cv_.wait_for(lock, timeout, [&] { return result_.has_value(); })) return std::nullopt;
    return std::move(result_);
  }

 private:
  void publish(GrpcReceiveResult result) {
    {
      std::lock_guard lock(mutex_);
      result_ = std::move(result);
    }
    cv_.notify_one();
  }

  GrpcStreamServerConfig config_;
  std::mutex mutex_;
  std::condition_variable cv_;
  std::optional<GrpcReceiveResult> result_;
};

}  // namespace

GrpcStreamClient::GrpcStreamClient(GrpcStreamClientConfig config, TlsCredentials credentials)
    : config_(std::move(config)), credentials_(std::move(credentials)) {
  if (config_.target.empty() || config_.max_batch_messages == 0 || config_.max_payload_bytes == 0 ||
      config_.timeout.count() <= 0 || config_.expected_server_name.empty())
    throw std::invalid_argument("invalid grpc client config");
}
GrpcSendResult GrpcStreamClient::send_batch(const std::vector<RemoteEnvelope>& events) const {
  if (events.size() > config_.max_batch_messages) return {false, "batch_too_large", 0};
  for (const auto& event : events) {
    if (event.payload.size() > config_.max_payload_bytes) return {false, "payload_too_large", 0};
  }
  grpc::ChannelArguments args;
  args.SetSslTargetNameOverride(config_.expected_server_name);
  auto channel = grpc::CreateCustomChannel(config_.target, client_credentials(credentials_), args);
  auto stub = ProtoService::NewStub(channel);
  grpc::ClientContext context;
  context.set_deadline(std::chrono::system_clock::now() + config_.timeout);
  ProtoAck ack;
  auto writer = stub->Push(&context, &ack);
  for (const auto& event : events) {
    auto message = to_proto(event);
    if (!writer->Write(message)) {
      writer->WritesDone();
      const auto status = writer->Finish();
      return {false, status.ok() ? "stream_closed" : status.error_message(), 0};
    }
  }
  writer->WritesDone();
  const auto status = writer->Finish();
  if (!status.ok()) return {false, status.error_message(), 0};
  if (!ack.accepted()) return {false, ack.reason(), ack.received()};
  return {true, "", ack.received()};
}

GrpcStreamServer::GrpcStreamServer(GrpcStreamServerConfig config, TlsCredentials credentials)
    : config_(std::move(config)), credentials_(std::move(credentials)) {
  if (config_.bind_address.empty() || config_.max_batch_messages == 0 ||
      config_.max_payload_bytes == 0 || config_.timeout.count() <= 0 ||
      config_.expected_peer_node_id.empty())
    throw std::invalid_argument("invalid grpc server config");
}
GrpcReceiveResult GrpcStreamServer::receive_batch_once() const {
  OneBatchService service(config_);
  grpc::ServerBuilder builder;
  int selected_port = 0;
  builder.AddListeningPort(config_.bind_address, server_credentials(credentials_), &selected_port);
  builder.RegisterService(&service);
  auto server = builder.BuildAndStart();
  if (!server || selected_port == 0) return {false, "grpc_bind_failed", {}, {}};

  auto result = service.wait_for_result(config_.timeout);
  server->Shutdown(std::chrono::system_clock::now() + std::chrono::milliseconds(100));
  if (!result) return {false, "grpc_receive_timeout", {}, {}};
  return std::move(*result);
}

}  // namespace atlas::node_agent
